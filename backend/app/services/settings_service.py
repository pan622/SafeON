from __future__ import annotations

import json
import threading
from pathlib import Path

import keyring

from backend.app.config import DATA_DIR, SUPPORTED_MODELS
from entract import config as legacy_config


class SettingsService:
    service_name = "SafeON"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._memory_keys: dict[str, str] = {}
        self._state_path = Path(DATA_DIR) / "settings.json"
        self._selected_model = self._load_selected_model()

    def _load_selected_model(self) -> str:
        if self._state_path.is_file():
            try:
                model = json.loads(self._state_path.read_text("utf-8")).get(
                    "selected_model"
                )
                if model in SUPPORTED_MODELS:
                    return model
            except (OSError, json.JSONDecodeError):
                pass
        return "deepseek-v4-pro"

    @property
    def selected_model(self) -> str:
        return self._selected_model

    def select_model(self, model: str) -> None:
        if model not in SUPPORTED_MODELS:
            raise ValueError("不支持的模型")
        with self._lock:
            self._selected_model = model
            self._state_path.write_text(
                json.dumps({"selected_model": model}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def get_api_key(self, model: str) -> str | None:
        if model == "qwen3-8b":
            return None
        if model in self._memory_keys:
            return self._memory_keys[model]
        try:
            stored = keyring.get_password(self.service_name, model)
            if stored:
                return stored
        except Exception:
            pass
        # 兼容既有配置，仅Pro模型使用原config中的密钥。
        if model == "deepseek-v4-pro" and legacy_config.API_KEY:
            return legacy_config.API_KEY
        return None

    def save_api_key(self, model: str, api_key: str) -> None:
        if model not in SUPPORTED_MODELS or model == "qwen3-8b":
            raise ValueError("该模型不支持API Key配置")
        value = api_key.strip()
        if len(value) < 8:
            raise ValueError("API Key格式无效")
        try:
            keyring.set_password(self.service_name, model, value)
        except Exception:
            self._memory_keys[model] = value

    def delete_api_key(self, model: str) -> None:
        self._memory_keys.pop(model, None)
        try:
            keyring.delete_password(self.service_name, model)
        except Exception:
            pass

    def public_settings(self) -> dict:
        models = []
        for model_id, metadata in SUPPORTED_MODELS.items():
            models.append(
                {
                    "id": model_id,
                    **metadata,
                    "api_key_configured": bool(self.get_api_key(model_id)),
                    "selected": model_id == self.selected_model,
                }
            )
        return {"selected_model": self.selected_model, "models": models}


settings_service = SettingsService()
