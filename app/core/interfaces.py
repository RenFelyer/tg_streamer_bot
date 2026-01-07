from abc import ABC, abstractmethod
from pathlib import Path

from app.core.enums import PlaylistCursorMode, StreamVisualMode
from app.core.schemas import MediaPaths


class ContentDownloader(ABC):
    def __init__(self, download_dir: Path) -> None:
        download_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir = download_dir

    @abstractmethod
    def get_video_id(self, url: str) -> str | None:
        """Извлекает уникальный идентификатор видео из предоставленного URL.

        Args:
            url (str): URL видео.

        Returns:
            str | None: Уникальный идентификатор видео или None, если не удалось извлечь.

        """

    @abstractmethod
    def get_media_by_id(self, video_id: str) -> MediaPaths:
        """Возвращает пути к медиафайлам по уникальному идентификатору видео.

        Args:
            video_id (str): Уникальный идентификатор видео.

        Returns:
            MediaPaths: Объект c путями к медиафайлам.

        """

    @abstractmethod
    def download(self, url: str) -> MediaPaths | None:
        """Скачивает медиафайлы по предоставленному URL.

        Args:
            url (str): URL видео для скачивания.

        Returns:
            MediaPaths | None: Объект c путями к скачанным медиафайлам или None в случае ошибки.

        """


class Player(ABC):
    @abstractmethod
    def start(self) -> None:
        """Запускает плеер."""

    @abstractmethod
    def play(self, media: MediaPaths) -> None:
        """Начинает воспроизведение указанного медиа."""

    @abstractmethod
    def pause(self) -> None:
        """Ставит воспроизведение на паузу."""

    @abstractmethod
    def resume(self) -> None:
        """Возобновляет воспроизведение."""

    @abstractmethod
    def set_visual_mode(self, mode: StreamVisualMode) -> bool:
        """Устанавливает режим визуального отображения трансляции."""

    @abstractmethod
    def close(self) -> None:
        """Закрывает плеер и освобождает ресурсы."""

    @abstractmethod
    def get_visual_mode(self) -> StreamVisualMode:
        """Возвращает текущий режим визуального отображения трансляции."""

    @abstractmethod
    def get_current_media(self) -> MediaPaths | None:
        """Возвращает текущий воспроизводимый медиафайл."""


class Playlist(ABC):
    @abstractmethod
    def add_track(self, media: MediaPaths) -> None:
        """Добавляет трек в плейлист."""

    @abstractmethod
    def del_track(self, index: int) -> None:
        """Удаляет трек из плейлиста по индексу."""

    @abstractmethod
    def move_track(self, old_index: int, new_index: int) -> None:
        """Перемещает трек внутри плейлиста."""

    @abstractmethod
    def next_track(self) -> MediaPaths | None:
        """Переходит к следующему треку в плейлисте."""

    @abstractmethod
    def prev_track(self) -> MediaPaths | None:
        """Переходит к предыдущему треку в плейлисте."""

    @abstractmethod
    def get_tracks(self) -> list[MediaPaths]:
        """Возвращает список всех треков в плейлисте."""

    @abstractmethod
    def set_cursor_mode(self, mode: PlaylistCursorMode) -> None:
        """Устанавливает режим курсора плейлиста."""

    @abstractmethod
    def get_current_track(self) -> MediaPaths | None:
        """Возвращает текущий трек в плейлисте."""
