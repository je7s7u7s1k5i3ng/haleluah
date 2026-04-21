from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    naver_client_id: str = ""
    naver_client_secret: str = ""

    searchad_api_key: str = ""
    searchad_secret_key: str = ""
    searchad_customer_id: str = ""

    scout_concurrency: int = 20
    scout_rps_shopping: float = 8.0
    scout_rps_searchad: float = 4.0
    scout_cache_ttl_hours: int = 24
    scout_db_path: Path = Field(default=Path("./data/scout.db"))
    scout_checkpoint_dir: Path = Field(default=Path("./data/checkpoints"))
    scout_http2: bool = True

    def require_shopping(self) -> None:
        if not self.naver_client_id or not self.naver_client_secret:
            raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 .env에 필요합니다.")

    def require_searchad(self) -> None:
        missing = [
            name
            for name, val in {
                "SEARCHAD_API_KEY": self.searchad_api_key,
                "SEARCHAD_SECRET_KEY": self.searchad_secret_key,
                "SEARCHAD_CUSTOMER_ID": self.searchad_customer_id,
            }.items()
            if not val
        ]
        if missing:
            raise RuntimeError(f"검색광고 API 키가 필요합니다: {', '.join(missing)}")


def get_settings() -> Settings:
    return Settings()
