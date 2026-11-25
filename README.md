# SafeON · 施工安全知识智能研判平台

从施工文档与巡检图片识别危险因素，定位到文献页码，并生成可下载的整改建议。

| 功能 | 输入 | 输出 |
| --- | --- | --- |
| 平台总览与模型配置 | Neo4j 知识库、模型设置 | 实体与关系规模、风险分布、模型连接状态 |
| 知识抽取与图谱展示 | PDF、Word | 危险因素、项目、风险等级与来源页码；交互图谱及 CSV |
| 风险研判与整改建议 | PDF、Word、JPG、PNG | 按风险排序的清单、依据文献与页码、整改措施与 TXT 报告 |

## 工作流程

```mermaid
flowchart LR
  A["施工文档 / 巡检图片"] --> B["文本解析 / PaddleOCR"]
  B --> C["FAISS 向量检索"]
  B --> D["Neo4j 图谱检索"]
  C --> E["RRF 候选融合"]
  D --> E
  E --> F["LangGraph：风险研判 → 整改生成"]
  F --> G["可追溯风险卡片 / TXT"]
```

抽取流程与在线研判独立：抽取结果可导出 CSV，并在页面预览关系图；它不会自动写入现有知识库。风险研判把检索依据和生成的整改措施分开呈现，结果需结合现场实际复核。

## 本地运行（Windows x64）

需要 Python 3.10、Node.js 22（至少 22.13）和 Neo4j Desktop。接下来的示例用**合成数据**，不用原项目的知识库。Neo4j Desktop 内启动本地实例，为本项目创建一个空的 `safeon` 数据库。若只能使用默认的 `neo4j` 库，必须使用独立且空的新实例。

在仓库根目录打开 PowerShell：

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm.cmd --prefix Front-end ci

# 生成演示图谱、FAISS 索引和合成示例。首跑下载 BGE 模型权重。
.\.venv\Scripts\python.exe -X utf8 prepare_demo.py

# Neo4j 密码不回显，存入当前 Windows 用户的凭据库。
.\.venv\Scripts\python.exe -X utf8 safeon.py configure
.\.venv\Scripts\python.exe -X utf8 safeon.py import-neo4j
```

导入器只接受空库，拒绝覆盖已有数据。不要使用系统数据库，也不要清空现有库来做演示。

分别在两个终端启动：

```powershell
# 终端 A
.\.venv\Scripts\python.exe -X utf8 safeon.py backend

# 终端 B
npm.cmd --prefix Front-end run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

打开 [SafeON 前端](http://127.0.0.1:5173/)，或访问 [后端健康检查](http://127.0.0.1:8000/api/v1/health)。可在模型设置页输入自己的 DeepSeek API Key，完成连接测试后，上传生成的 `demo_generated/模拟巡检记录.docx` 查看抽取和研判。也可用同目录的 JPG 验证图片研判；PaddleOCR 第一次运行会下载它的模型文件。首页和本地健康检查不需要 DeepSeek Key。Qwen3-8B 是预留项。

## 代码结构与数据边界

- `Front-end/`：React 前端，开发环境代理到本地后端。
- `backend/`：FastAPI 接口、任务处理、模型设置。
- `agent/`：上传文件解析、PaddleOCR、FAISS / Neo4j 检索及 LangGraph 工作流。
- `prepare_demo.py` / `neo4j_transfer.py`：生成演示知识库、校验和导入图谱。

公开可阅的代码不包含生产知识库、原始文献、模型权重或 API 密钥。应用默认只在本机运行；对外部署前需要另行设计认证、授权、上传限额与日志策略。
