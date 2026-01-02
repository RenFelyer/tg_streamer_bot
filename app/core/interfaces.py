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


class StreamManager(ABC):
    def __init__(self) -> None:
        self.media_queue: list[MediaPaths] = []
        self.current_index: int = 0

        self.cursor_mode = PlaylistCursorMode.LOOP_QUEUE
        self.visual_mode = StreamVisualMode.VIDEO_CONTENT

    # --- Управление соединением ---
    @abstractmethod
    def start_stream(self) -> None:
        """Запускает потоковую передачу."""

    @abstractmethod
    def close_stream(self) -> None:
        """Закрывает потоковую передачу."""

    # --- Управление очередью (Playlist) ---
    def add_track(self, media: MediaPaths) -> None:
        """Добавляет медиа в конец очереди."""
        self.media_queue.append(media)

    @abstractmethod
    def remove_track(self, index: int) -> None:
        """Удаляет медиа из очереди по индексу."""
        if 0 <= index < len(self.media_queue):
            del self.media_queue[index]

    @abstractmethod
    def move_track(self, from_index: int, to_index: int) -> None:
        """Перемещает трек внутри очереди (изменение порядка)."""
        if not (0 <= from_index < len(self.media_queue)):
            return

        if not (0 <= to_index < len(self.media_queue)):
            return

        # Перемещение трека
        track = self.media_queue.pop(from_index)
        self.media_queue.insert(to_index, track)

    @abstractmethod
    def select_track(self, index: int) -> None:
        """Принудительно переключает курсор на указанный индекс."""

    # --- Управление воспроизведением ---
    @abstractmethod
    def pause_current_track(self) -> None:
        """Ставит на паузу текущее видео."""

    @abstractmethod
    def resume_current_track(self) -> None:
        """Возобновляет воспроизведение текущего видео."""

    @abstractmethod
    def restart_current_track(self) -> None:
        """Перезапускает текущее видео."""

    @abstractmethod
    def next_track(self) -> None:
        """Ручной переход к следующему треку."""

    @abstractmethod
    def prev_track(self) -> None:
        """Ручной переход к предыдущему треку."""

    # --- Настройки режимов ---
    def set_visual_mode(self, mode: StreamVisualMode) -> bool:
        """Устанавливает режим визуального отображения трансляции."""
        if not isinstance(mode, StreamVisualMode):
            return False

        self.visual_mode = mode
        return True

    def set_cursor_mode(self, mode: PlaylistCursorMode) -> bool:
        """Устанавливает логику работы курсора (очереди) после окончания трека."""
        if not isinstance(mode, PlaylistCursorMode):
            return False

        self.cursor_mode = mode
        return True
