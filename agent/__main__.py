from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent.parsers import parse_file
from agent.service import SafeONAnalyzer
from agent.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="SafeON施工安全知识推理")
    parser.add_argument("inputs", nargs="+", help="一个或多个DOCX、PDF、JPG文件")
    parser.add_argument("--output-dir", default="output", help="输出目录")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="不调用外部大模型，仅用于本地组件和输出结构测试",
    )
    arguments = parser.parse_args()

    summaries = []
    settings = Settings(offline_mode=True) if arguments.offline else Settings()
    # 先完成所有文件解析，尤其让PaddleOCR在向量模型占用内存前运行。
    parsed_inputs = [parse_file(input_value) for input_value in arguments.inputs]
    with SafeONAnalyzer(settings) as analyzer:
        for input_value, parsed in zip(arguments.inputs, parsed_inputs):
            output = analyzer.analyze_parsed(parsed, arguments.output_dir)
            result = output["result"]
            summaries.append(
                {
                    "input": str(Path(input_value).resolve()),
                    "json_path": output["json_path"],
                    "text_path": output["text_path"],
                    "hazard_count": result["summary"]["hazard_count"],
                    "highest_risk_level": result["summary"]["highest_risk_level"],
                }
            )
            print(json.dumps(summaries[-1], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
