from __future__ import annotations

import os
from pathlib import Path

# FAISS/SentenceTransformer inference is latency-bound here; a single BLAS thread
# avoids the large per-request native workspaces that can crash long-lived Windows
# processes after several consecutive documents.
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from openai import OpenAI

from backend.app.config import ApiConfig, SUPPORTED_MODELS
from backend.app.schemas import ApiKeyUpdate, ConnectionTest, ModelSelection
from backend.app.services.extraction_service import extract_to_csv
from backend.app.services.home_service import get_home_stats
from backend.app.services.job_service import job_service
from backend.app.services.reasoning_service import reason_to_txt
from backend.app.services.settings_service import settings_service
from backend.app.services.upload_service import save_upload
from entract.config import BASE_URL


app = FastAPI(
    title="SafeON API",
    version="1.0.0",
    description="施工现场安全知识抽取与知识推理接口",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ApiConfig().frontend_origin, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def require_model() -> tuple[str, str]:
    model = settings_service.selected_model
    metadata = SUPPORTED_MODELS[model]
    if not metadata["available"]:
        raise api_error(409, "MODEL_NOT_IMPLEMENTED", "Qwen3-8B 为预留接口，请切换至 DeepSeek 模型。")
    api_key = settings_service.get_api_key(model)
    if metadata["requires_api_key"] and not api_key:
        raise api_error(409, "API_KEY_REQUIRED", "当前模型尚未配置 API Key，请先前往设置。")
    return model, api_key or ""


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "SafeON API", "version": app.version}


@app.get("/api/v1/home/stats")
def home_stats() -> dict:
    try:
        return get_home_stats()
    except Exception as error:
        raise api_error(503, "GRAPH_UNAVAILABLE", f"知识图谱暂不可用：{error}") from error


@app.get("/api/v1/settings")
def get_settings() -> dict:
    return settings_service.public_settings()


@app.put("/api/v1/settings/model")
def select_model(payload: ModelSelection) -> dict:
    try:
        settings_service.select_model(payload.model)
    except ValueError as error:
        raise api_error(400, "INVALID_MODEL", str(error)) from error
    return settings_service.public_settings()


@app.put("/api/v1/settings/api-key")
def save_api_key(payload: ApiKeyUpdate) -> dict:
    try:
        settings_service.save_api_key(payload.model, payload.api_key)
    except ValueError as error:
        raise api_error(400, "INVALID_API_KEY", str(error)) from error
    return settings_service.public_settings()


@app.delete("/api/v1/settings/api-key/{model}")
def delete_api_key(model: str) -> dict:
    if model not in SUPPORTED_MODELS:
        raise api_error(404, "MODEL_NOT_FOUND", "模型不存在。")
    settings_service.delete_api_key(model)
    return settings_service.public_settings()


@app.post("/api/v1/settings/test")
def test_connection(payload: ConnectionTest) -> dict:
    model = payload.model or settings_service.selected_model
    if model not in SUPPORTED_MODELS:
        raise api_error(400, "INVALID_MODEL", "模型不存在。")
    if not SUPPORTED_MODELS[model]["available"]:
        raise api_error(409, "MODEL_NOT_IMPLEMENTED", "Qwen3-8B 接口尚未接入。")
    api_key = (payload.api_key or "").strip() or settings_service.get_api_key(model)
    if not api_key:
        raise api_error(409, "API_KEY_REQUIRED", "请输入 API Key。")
    try:
        client = OpenAI(api_key=api_key, base_url=BASE_URL, timeout=30)
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "仅回复 OK"}],
            max_tokens=8,
            temperature=0,
        )
    except Exception as error:
        raise api_error(502, "MODEL_CONNECTION_FAILED", f"模型连接失败：{error}") from error
    return {"ok": True, "message": "连接成功", "model": model}


def submit_job(job_type: str, input_path: Path, model: str, api_key: str) -> dict:
    worker = extract_to_csv if job_type == "extraction" else reason_to_txt

    def runner(job_id: str) -> None:
        try:
            output_path, result = worker(
                input_path,
                model,
                api_key,
                job_id,
                lambda **values: job_service.update(job_id, **values),
            )
            job_service.update(
                job_id,
                status="completed",
                progress=100,
                stage_message="处理完成，可以下载结果文件",
                result=result,
                output_path=str(output_path),
                download_url=f"/api/v1/jobs/{job_id}/download",
            )
        except Exception as error:
            job_service.update(
                job_id,
                status="failed",
                stage_message="处理失败",
                error={"code": "PROCESSING_FAILED", "message": str(error)},
            )

    return job_service.create(job_type, runner)


@app.post("/api/v1/extraction/jobs")
async def create_extraction_job(file: UploadFile = File(...)) -> dict:
    model, api_key = require_model()
    try:
        input_path = await save_upload(file, {".pdf", ".docx"})
    except ValueError as error:
        raise api_error(400, "INVALID_UPLOAD", str(error)) from error
    return submit_job("extraction", input_path, model, api_key)


@app.post("/api/v1/reasoning/jobs")
async def create_reasoning_job(file: UploadFile = File(...)) -> dict:
    model, api_key = require_model()
    try:
        input_path = await save_upload(file, {".pdf", ".docx", ".jpg", ".jpeg", ".png"})
    except ValueError as error:
        raise api_error(400, "INVALID_UPLOAD", str(error)) from error
    return submit_job("reasoning", input_path, model, api_key)


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = job_service.get(job_id)
    if not job:
        raise api_error(404, "JOB_NOT_FOUND", "任务不存在或服务已重启。")
    job.pop("output_path", None)
    return job


@app.get("/api/v1/jobs/{job_id}/download")
def download_job(job_id: str):
    job = job_service.get(job_id)
    if not job:
        raise api_error(404, "JOB_NOT_FOUND", "任务不存在或服务已重启。")
    if job["status"] != "completed" or not job.get("output_path"):
        raise api_error(409, "JOB_NOT_READY", "任务尚未完成。")
    path = Path(job["output_path"])
    if not path.is_file():
        raise api_error(410, "RESULT_EXPIRED", "结果文件不存在。")
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")
