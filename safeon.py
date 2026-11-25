"""Run from the extracted SafeON directory using its Python environment."""
import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
LOCAL = ROOT / "backend" / "data" / "migration-local.json"
GRAPH_SERVICE = "SafeON-Portable-Neo4j"


def graph_settings():
    try:
        settings = json.loads(LOCAL.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit("先运行 safeon.py configure，配置目标电脑的 Neo4j。")
    import keyring
    password = keyring.get_password(GRAPH_SERVICE, settings["uri"] + "|" + settings["user"])
    if not password:
        raise SystemExit("未找到该 Neo4j 连接的密码，请重新运行 configure。")
    return settings, password


def configure():
    import keyring
    from neo4j import GraphDatabase
    uri = input("Bolt 地址 [bolt://127.0.0.1:7687]：").strip() or "bolt://127.0.0.1:7687"
    username = input("用户名 [neo4j]：").strip() or "neo4j"
    database = input("目标数据库名 [safeon]：").strip() or "safeon"
    if database.lower() == "system":
        raise SystemExit("不能使用系统数据库。")
    password = getpass("目标电脑 Neo4j 密码（输入不回显）：")
    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        with driver.session(database=database) as session:
            session.run("RETURN 1").consume()
    keyring.set_password(GRAPH_SERVICE, uri + "|" + username, password)
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    LOCAL.write_text(json.dumps({"uri": uri, "user": username, "database": database}, indent=2), encoding="utf-8")
    print("Neo4j 连接已验证；密码已保存到当前 Windows 用户的凭据库。")


def runtime_env():
    settings, password = graph_settings()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.update({
        "SAFEON_NEO4J_URI": settings["uri"], "SAFEON_NEO4J_USER": settings["user"],
        "SAFEON_NEO4J_DATABASE": settings["database"], "SAFEON_NEO4J_PASSWORD": password,
        "SAFEON_FAISS_INDEX": str(ROOT / "knowledge" / "faiss" / "fused_cause_faiss.index"),
        "SAFEON_FAISS_MAPPING": str(ROOT / "knowledge" / "faiss" / "fused_cause_mapping.csv"),
        "SAFEON_EMBEDDING_MODEL": str(ROOT / "models" / "bge-small-zh-v1.5"),
        "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "HF_HUB_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
    })


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("configure", "import-neo4j", "validate-snapshot", "verify", "backend"):
        sub.add_parser(name)
    args = parser.parse_args()
    if args.command == "configure":
        configure()
    elif args.command in {"validate-snapshot", "import-neo4j"}:
        from neo4j_transfer import import_graph, read_snapshot
        snapshot = ROOT / "knowledge" / "neo4j"
        if args.command == "validate-snapshot":
            print(json.dumps(read_snapshot(snapshot)[2], ensure_ascii=False, indent=2))
        else:
            from neo4j import GraphDatabase
            settings, password = graph_settings()
            with GraphDatabase.driver(settings["uri"], auth=(settings["user"], password)) as driver:
                result = import_graph(driver, settings["database"], snapshot)
            print(f"导入并核对成功：{result['nodes']:,} 个节点，{result['relationships']:,} 条关系。")
    elif args.command == "backend":
        runtime_env()
        import uvicorn
        uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, workers=1)
    else:
        runtime_env()
        from agent.retrieval.faiss_retriever import FaissHazardRetriever
        from agent.settings import Settings
        from agent.parsers.resident_ocr import resident_ocr
        from backend.app.services.home_service import get_home_stats
        from backend.app.services.settings_service import settings_service
        from neo4j_transfer import read_snapshot
        settings = Settings()
        stats = get_home_stats()
        expected = read_snapshot(ROOT / "knowledge" / "neo4j")[2]
        if (stats["entity_count"], stats["relationship_count"]) != (expected["nodes"], expected["relationships"]):
            raise SystemExit(f"Neo4j 节点/关系数量与快照不同：{stats}")
        print(f"Neo4j：{stats['entity_count']:,} 个节点 / {stats['relationship_count']:,} 条关系", flush=True)
        retriever = FaissHazardRetriever(settings.faiss_index_path, settings.faiss_mapping_path, settings.embedding_model)
        results = retriever.search(["高处作业未系安全带"], 3)
        if not results or not results[0]:
            raise SystemExit("FAISS 未返回检索结果。")
        print(f"FAISS：{retriever.index.ntotal:,} 条向量，{retriever.index.d} 维；本地检索成功", flush=True)
        try:
            cases = list((ROOT / "demo_generated").glob("*.jpg"))
            if len(cases) != 1 or not resident_ocr.recognize(cases[0]):
                raise SystemExit("JPG 示例未识别到文字。")
        finally:
            resident_ocr.close()
        print("PaddleOCR：JPG 示例识别成功")
        for info in settings_service.public_settings()["models"]:
            if info["requires_api_key"]:
                print(f"{info['id']}：{'已配置' if info['api_key_configured'] else '未配置'}")
        print("本地检查通过；未调用 DeepSeek。联网验证请在网页设置中完成。")


if __name__ == "__main__":
    main()
