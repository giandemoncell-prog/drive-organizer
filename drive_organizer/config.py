from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    anthropic_api_key: str = ""

    gemini_api_key: str = ""
    gemini_flash_model: str = "gemini-2.5-flash"
    gemini_pro_model: str = "gemini-2.5-pro"

    deepseek_api_key: str = ""
    deepseek_flash_model: str = "deepseek-chat"
    deepseek_pro_model: str = "deepseek-reasoner"

    dashscope_api_key: str = ""
    qwen_flash_model: str = "qwen-plus"
    qwen_pro_model: str = "qwen-max"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    haiku_model: str = "claude-haiku-4-5"
    opus_model: str = "claude-opus-4-8"

    ollama_confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    haiku_confidence_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    max_cloud_escalations: int = 200
    max_cloud_escalations_pct: float = Field(default=0.20, ge=0.0, le=1.0)

    duplicate_exclude_folder_patterns: list[str] = [
        "analytics_snapshot",
        "trackers_snapshot",
        "Workflow Backups",
    ]

    credentials_path: str = "credentials.json"
    tokens_dir: str = "tokens"
    rollback_dir: str = "logs"

    drive_scopes: list[str] = ["https://www.googleapis.com/auth/drive"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
