from abc import ABC, abstractmethod
from fractions import Fraction

from av import AudioFrame, AudioStream, VideoFrame, VideoStream

from app.core.enums import StreamCursorMode, StreamVisualMode
from app.deliver.constants import SYNC_TOLERANCE
from app.deliver.schemas import MediaAssetPaths


class ContextDeliver(ABC):
    """Абстрактный класс для доставки закодированных медиа-пакетов в контейнер."""

    @abstractmethod
    def create_graph(self, stream: AudioStream | VideoStream) -> None:
        """Создает граф фильтров для указанного потока."""

    @abstractmethod
    def encode_video(self, frame: VideoFrame | None, *, apply_filters: bool = True) -> None:
        """Кодирует видео-фрейм и записывает пакеты в контейнер."""

    @abstractmethod
    def encode_audio(self, frame: AudioFrame | None, *, apply_filters: bool = True) -> None:
        """Кодирует аудио-фрейм и записывает пакеты в контейнер."""

    @abstractmethod
    def flush(self) -> None:
        """Сбрасывает буферы кодировщиков."""

    @abstractmethod
    def close(self) -> None:
        """Закрывает контейнер и освобождает ресурсы."""

    @property
    @abstractmethod
    def video_duration(self) -> Fraction:
        """Возвращает текущую видео-длительность в секундах."""

    @property
    @abstractmethod
    def audio_duration(self) -> Fraction:
        """Возвращает текущую аудио-длительность в секундах."""

    @property
    def duration(self) -> Fraction:
        """Возвращает текущую длительность в секундах."""
        return max(self.video_duration, self.audio_duration)

    @property
    def is_audio_video_synced(self) -> bool:
        """Проверяет, синхронизированы ли аудио и видео по длительности."""
        return abs(self.audio_duration - self.video_duration) <= SYNC_TOLERANCE


class PlayerDeliver(ABC):
    """Абстрактный плеер для потоковой передачи медиа."""

    @abstractmethod
    def append(self, media: MediaAssetPaths) -> None:
        """Добавляет элемент в плейлист."""

    @abstractmethod
    def remove(self, index: int) -> None:
        """Удаляет элемент из плейлиста по индексу."""

    @abstractmethod
    def select(self, index: int) -> None:
        """Выбирает элемент плейлиста по индексу."""

    @abstractmethod
    def move(self, from_index: int, to_index: int) -> None:
        """Перемещает элемент внутри плейлиста."""

    @abstractmethod
    def next(self, step: int = 1) -> None:
        """Переходит к следующему элементу плейлиста."""

    @abstractmethod
    def prev(self, step: int = 1) -> None:
        """Переходит к предыдущему элементу плейлиста."""

    @abstractmethod
    def get_current(self, step: int = 0) -> MediaAssetPaths | None:
        """Возвращает текущий элемент плейлиста."""

    @abstractmethod
    def get_next(self) -> MediaAssetPaths | None:
        """Возвращает следующий элемент плейлиста."""

    @abstractmethod
    def get_prev(self) -> MediaAssetPaths | None:
        """Возвращает предыдущий элемент плейлиста."""

    @abstractmethod
    def get_playlist(self) -> list[MediaAssetPaths]:
        """Возвращает полный список элементов плейлиста."""

    @property
    @abstractmethod
    def cursor_mode(self) -> StreamCursorMode:
        """Возвращает текущий режим курсора плейлиста."""

    @property
    @abstractmethod
    def visual_mode(self) -> StreamVisualMode:
        """Возвращает текущий режим визуализации плеера."""

    @property
    @abstractmethod
    def is_playing(self) -> bool:
        """Возвращает состояние паузы плеера."""

    @abstractmethod
    def clear(self) -> None:
        """Очищает плейлист."""


__all__ = [
    'ContextDeliver',
    'PlayerDeliver',
]
