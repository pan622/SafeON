from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI


def _parse_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("大模型返回的JSON顶层不是对象")
    return value


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int,
    ) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def complete_json(self, system_prompt: str, user_content: str) -> dict[str, Any]:
        last_error: Exception | None = None
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    max_tokens=2500,
                    extra_body={"thinking": {"type": "disabled"}},
                    messages=messages,
                )
                content = response.choices[0].message.content or ""
                return _parse_json_object(content)
            except Exception as error:
                last_error = error
                messages.append(
                    {
                        "role": "user",
                        "content": "上一次返回无法解析。请严格只返回一个合法JSON对象。",
                    }
                )
        raise RuntimeError(f"大模型调用或JSON解析失败：{last_error}") from last_error
