from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    admin_ids: str = ""
    admin_username: str = "dankovvv"
    database_url: str = "sqlite+aiosqlite:///./data/kufar_bot.db"
    kufar_impersonate: str = "chrome"
    log_level: str = "INFO"
    kufar_fetch_description: bool = True
    kufar_description_max_chars: int = 600
    kufar_request_delay_sec: float = 0.4
    kufar_use_thumbnail: bool = True
    kufar_send_photo_separate: bool = True
    poll_max_pages: int = 3
    poll_watermark_max_pages: int = 100
    poll_first_run_hours: int = 24
    poll_digest_threshold: int = 100
    poll_max_send_per_run: int = 0
    telegram_send_delay_sec: float = 0.35

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _coerce_admin_ids(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value)

    @property
    def admin_id_list(self) -> list[int]:
        if not self.admin_ids.strip():
            return []
        return [int(part.strip()) for part in self.admin_ids.split(",") if part.strip()]

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.admin_id_list)


settings = Settings()
