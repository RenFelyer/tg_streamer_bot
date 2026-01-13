from functools import lru_cache
from pathlib import Path
from typing import Annotated

from aiogram.utils.token import TokenValidationError, validate_token
from pydantic import AfterValidator, BeforeValidator, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def verify_bot_token(v: str) -> str:
    try:
        validate_token(v)
    except TokenValidationError as e:
        raise ValueError('Некорректный формат токена (проверка aiogram)') from e
    return v


def parse_list_from_str(v: str | list[int]) -> list[int]:
    if isinstance(v, str):
        # Удаляем пробелы, скобки (если есть) и сплитим по запятой
        v = v.replace('[', '').replace(']', '').strip()
        if not v:
            return []
        return [int(item) for item in v.split(',')]
    return v


class Settings(BaseSettings):
    """Конфигурация приложения.

    Загружает настройки из переменных окружения и .env файла.
    """

    # Основные настройки
    root_dir: Path = Field(default_factory=Path.cwd)

    # Telegram Bot
    bot_token: Annotated[str, AfterValidator(verify_bot_token)]
    admin_ids: Annotated[list[int], BeforeValidator(parse_list_from_str)]

    # RTMP Stream
    tg_link: str = Field(..., description='Telegram RTMPS link')
    tg_code: str = Field(..., description='Telegram RTMPS stream key')

    # Видео настройки
    width: int = 1360
    height: int = 752

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    @computed_field
    @property
    def placeholder_path(self) -> Path:
        return self.assets_dir / 'technical_cookies.jpg'

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
