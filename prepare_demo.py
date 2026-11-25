"""Generate small, fictional SafeON inputs and retrieval data; no credentials needed."""
import argparse
import csv
import json
from pathlib import Path

from neo4j_transfer import canonical, graph_signature

ROOT = Path(__file__).resolve().parent
MODEL_ID = "BAAI/bge-small-zh-v1.5"
FACTORS = [
    ("高处作业人员未系挂安全带", "Human_Factor", "较大风险", "高处作业"),
    ("临时配电箱箱门损坏", "Physical_Factor", "一般风险", "临时用电"),
    ("作业通道积水", "Environmental_Factor", "一般风险", "通用安全管理"),
    ("未记录班前安全交底", "Management_Factor", "一般风险", "通用安全管理"),
]


def graph():
    nodes, edges = [], []
    def node(id_, label, **props):
        nodes.append({"id": id_, "labels": [label], "props": props})
    node("doc", "Document", Document_Name="SafeON 合成演示手册")
    projects = {name: f"project{i}" for i, name in enumerate(sorted({f[-1] for f in FACTORS}))}
    for name, id_ in projects.items():
        node(id_, "Project", Project_Name=name)
    for i, (name, label, level, project) in enumerate(FACTORS, 1):
        id_ = f"factor{i}"
        node(id_, label, Cause_Name=name, Type=label, Cause_Level=level)
        edges += [{"start": "doc", "end": id_, "type": "INVOLVE", "props": {"Source": str(i)}},
                  {"start": projects[project], "end": id_, "type": "INCLUDE", "props": {}}]
    path = ROOT / "knowledge" / "neo4j"
    path.mkdir(parents=True, exist_ok=True)
    for name, records in [("nodes", nodes), ("relationships", edges)]:
        (path / f"{name}.jsonl").write_text("".join(canonical(r)+"\n" for r in records), encoding="utf-8")
    manifest = {"format": 1, "source_database": "synthetic", **graph_signature(nodes, edges)}
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"演示图谱：{manifest['nodes']} 个节点 / {manifest['relationships']} 条关系")


def examples():
    from docx import Document
    from PIL import Image, ImageDraw, ImageFont
    import os
    target = ROOT / "demo_generated"
    target.mkdir(exist_ok=True)
    doc = Document()
    doc.add_heading("SafeON 合成巡检记录", 0)
    doc.add_paragraph("演示项目在高处作业区域发现作业人员未系挂安全带；临时配电箱箱门损坏，作业通道有积水。")
    doc.save(target / "模拟巡检记录.docx")
    im = Image.new("RGB", (1000, 360), "white")
    font = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc"
    message = "SafeON 合成巡检记录\n\n高处作业人员未系挂安全带\n\n临时配电箱箱门损坏"
    if font.is_file():
        f = ImageFont.truetype(str(font), 36)
    else:
        message = "SafeON Fictional Inspection\n\nWorker without a safety harness at height.\n\nTemporary electrical enclosure is damaged."
        f = ImageFont.load_default(size=30)
    ImageDraw.Draw(im).multiline_text((45, 40), message, font=f, fill="black", spacing=12)
    im.save(target / "模拟巡检记录.jpg", quality=95)


def vector():
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    local = ROOT / "models" / "bge-small-zh-v1.5"
    model = SentenceTransformer(str(local) if (local / "modules.json").is_file() else MODEL_ID, device="cpu")
    names = [f[0] for f in FACTORS]
    embeddings = np.asarray(model.encode(names, normalize_embeddings=True), dtype="float32")
    if not (local / "modules.json").is_file():
        model.save(str(local))
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    target = ROOT / "knowledge" / "faiss"
    target.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(target / "fused_cause_faiss.index"))
    with (target / "fused_cause_mapping.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["faiss_id", "Cause_Name"])
        writer.writerows(enumerate(names))
    print(f"演示向量库：{len(names)} 条 / {index.d} 维")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-vector", action="store_true", help="Generate only the graph and fictional files")
    opts = parser.parse_args()
    graph()
    examples()
    if not opts.skip_vector:
        vector()
