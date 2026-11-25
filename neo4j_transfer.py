"""Lossless logical transfer for the current SafeON graph (JSON-native properties)."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

NODE_QUERY = "MATCH (n) RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props"
EDGE_QUERY = """MATCH (a)-[r]->(b) RETURN elementId(a) AS start,
                elementId(b) AS end, type(r) AS type, properties(r) AS props"""


def token(name):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
        raise ValueError(f"Unsupported graph token: {name!r}")
    return name


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def graph_signature(nodes, edges):
    def signature(rows):
        hashes = sorted(hashlib.sha256(canonical(row).encode()).digest() for row in rows)
        return hashlib.sha256(b"".join(hashes)).hexdigest()
    keys = {}
    labels, types = Counter(), Counter()
    for node in nodes:
        if node["id"] in keys:
            raise ValueError("Duplicate node ID")
        labs = sorted(token(name) for name in node["labels"])
        labels.update(labs)
        keys[node["id"]] = hashlib.sha256(canonical([labs, node["props"]]).encode()).hexdigest()
    for edge in edges:
        token(edge["type"])
        types[edge["type"]] += 1
    return {"nodes": len(nodes), "relationships": len(edges), "labels": dict(labels),
            "relationship_types": dict(types),
            "node_fingerprint": signature(keys.values()),
            "relationship_fingerprint": signature(
                [keys[e["start"]], e["type"], e["props"], keys[e["end"]]] for e in edges)}


def capture(tx):
    return tx.run(NODE_QUERY).data(), tx.run(EDGE_QUERY).data()


def export_graph(driver, database, folder):
    with driver.session(database=database) as session:
        nodes, edges = session.execute_read(capture)
        indexes = session.run("SHOW INDEXES YIELD type RETURN type").value()
        constraints = session.run("SHOW CONSTRAINTS YIELD name RETURN name").value()
    if any(kind != "LOOKUP" for kind in indexes) or constraints:
        raise ValueError("Custom indexes or constraints found; document and migrate schema before release.")
    summary = graph_signature(nodes, edges)
    if not (summary["nodes"] and summary["relationships"]):
        raise ValueError("Source graph unexpectedly empty")
    folder.mkdir(parents=True, exist_ok=True)
    for name, rows in [("nodes", nodes), ("relationships", edges)]:
        with (folder / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(canonical(row) + "\n")
    (folder / "manifest.json").write_text(
        json.dumps({"format": 1, "source_database": database, **summary}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def read_snapshot(folder: Path):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest.pop("format") != 1:
        raise ValueError("Unknown graph package format")
    manifest.pop("source_database")
    def rows(name):
        with (folder / f"{name}.jsonl").open(encoding="utf-8") as f:
            return [json.loads(line) for line in f]
    nodes, edges = rows("nodes"), rows("relationships")
    if manifest != graph_signature(nodes, edges):
        raise ValueError("Graph package failed checksum or count verification")
    return nodes, edges, manifest


def import_graph(driver, database, folder, rollback_only=False):
    if database.lower() == "system":
        raise ValueError("Never import into the system database")
    nodes, edges, expected = read_snapshot(folder)
    by_labels, by_type = defaultdict(list), defaultdict(list)
    for n in nodes:
        by_labels[tuple(n["labels"])].append(n)
    for e in edges:
        by_type[e["type"]].append(e)
    def batches(items):
        for start in range(0, len(items), 1000):
            yield items[start:start + 1000]
    with driver.session(database=database) as session, session.begin_transaction(timeout=300) as tx:
        if tx.run("MATCH (n) RETURN count(n) AS n").single()["n"] != 0:
            raise ValueError(f"目标数据库 {database} 非空，停止导入；不会删除或覆盖任何数据。")
        ids = {}
        for labs, group in by_labels.items():
            label_expression = "".join(":" + token(label) for label in labs)
            query = (f"UNWIND $rows AS row CREATE (n{label_expression}) "
                     "SET n = row.props RETURN row.id AS source, elementId(n) AS target")
            for batch in batches(group):
                ids.update((row["source"], row["target"]) for row in tx.run(query, rows=batch))
        for kind, group in by_type.items():
            query = ("UNWIND $rows AS row "
                     "MATCH (a) WHERE elementId(a) = row.start "
                     "MATCH (b) WHERE elementId(b) = row.end "
                     f"CREATE (a)-[r:{token(kind)}]->(b) SET r = row.props")
            for batch in batches(group):
                payload = [{**e, "start": ids[e["start"]], "end": ids[e["end"]]} for e in batch]
                if tx.run(query, rows=payload).consume().counters.relationships_created != len(batch):
                    raise RuntimeError("Relationship import incomplete; transaction will roll back.")
        if graph_signature(*capture(tx)) != expected:
            raise RuntimeError("Imported graph differs from the snapshot; transaction will roll back.")
        if rollback_only:
            tx.rollback()
        else:
            tx.commit()
    return expected
