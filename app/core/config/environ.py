from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    root_dir: Path = Field(default_factory=Path.cwd)
    tg_link: str = Field(..., description='Telegram RTMPS link')
    tg_code: str = Field(..., description='Telegram RTMPS stream key')

    width: int = 1360
    height: int = 752

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @computed_field
    @property
    def assets_dir(self) -> Path:
        _dir = self.root_dir / 'assets'
        _dir.mkdir(parents=True, exist_ok=True)
        return _dir

    @computed_field
    @property
    def thumbnails_dir(self) -> Path:
        _dir = self.assets_dir / 'thumbnails'
        _dir.mkdir(parents=True, exist_ok=True)
        return _dir

    @computed_field
    @property
    def multimedia_dir(self) -> Path:
        _dir = self.assets_dir / 'multimedia'
        _dir.mkdir(parents=True, exist_ok=True)
        return _dir

    @computed_field
    @property
    def rtmps_url(self) -> str:
        return f'{self.tg_link[: -1 if self.tg_link[-1] == "/" else 0]}/{self.tg_code}'


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]


settings = get_settings()

__all__ = ['settings']
