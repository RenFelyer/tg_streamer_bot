from threading import RLock

from app.core.enums import StreamCursorMode, StreamVisualMode
from app.deliver.interfaces import PlayerDeliver
from app.deliver.schemas import MediaAssetPaths


class AVPlayer(PlayerDeliver):
    def __init__(self, visual_mode: StreamVisualMode, cursor_mode: StreamCursorMode) -> None:
        self._visual_mode: StreamVisualMode = visual_mode
        self._cursor_mode: StreamCursorMode = cursor_mode
        self._playlist: list[MediaAssetPaths] = []
        self._is_playing: bool = True
        self._cursor: int | None = None
        self._lock = RLock()

    @property
    def cursor(self) -> int | None:
        if self._cursor is None:
            return None

        size = len(self._playlist)
        if size == 0:
            self._cursor = None
            return None

        # Исправленное условие:
        if not (0 <= self._cursor < size):
            self._cursor = None
            return None

        return self._cursor

    @cursor.setter
    def cursor(self, value: int | None) -> None:
        size = len(self._playlist)

        if value is None or not size:
            self._cursor = None
            return

        if self._cursor_mode != StreamCursorMode.LOOP_PLAYLIST:
            self._cursor = value if 0 <= value < size else None

        else:
            self._cursor = value % size

    def append(self, media: MediaAssetPaths) -> None:
        with self._lock:
            self._playlist.append(media)
            if self.cursor is None:
                self.cursor = 0

    def remove(self, index: int) -> None:
        with self._lock:
            if 0 <= index < len(self._playlist):
                del self._playlist[index]
                if self.cursor is None:
                    return

                if index < self.cursor:
                    self.cursor -= 1
                elif index == self.cursor:
                    self.cursor = min(self.cursor, len(self._playlist) - 1)

    def select(self, index: int) -> None:
        step = 0
        with self._lock:
            current_cursor = self.cursor
            if self._cursor_mode == StreamCursorMode.PLAY_AND_DELETE and current_cursor is not None:
                del self._playlist[current_cursor]
                if index >= current_cursor:
                    step = -1

            if 0 <= index < len(self._playlist):
                self.cursor = index + step

    def move(self, from_index: int, to_index: int) -> None:
        with self._lock:
            size = len(self._playlist)
            if not (0 <= from_index < size) or not (0 <= to_index < size) or self.cursor is None:
                return

            item = self._playlist.pop(from_index)
            self._playlist.insert(to_index, item)

            if from_index == self.cursor:
                self.cursor = to_index

            elif from_index < self.cursor <= to_index:
                self.cursor = self.cursor - 1

            elif to_index <= self.cursor < from_index:
                self.cursor = self.cursor + 1

    def next(self, step: int = 1) -> None:
        """Переходит к следующему элементу плейлиста."""
        self.select((self.cursor or 0) + step)

    def prev(self, step: int = 1) -> None:
        """Переходит к предыдущему элементу плейлиста."""
        self.select((self.cursor or 0) - step)

    def get_current(self, step: int = 0) -> MediaAssetPaths | None:
        with self._lock:
            if self.cursor is None:
                return None

            size = len(self._playlist)
            if size == 0:
                return None

            current_index = self.cursor + step
            if not (0 <= current_index < size):
                if self._cursor_mode == StreamCursorMode.LOOP_PLAYLIST:
                    current_index = current_index % size
                else:
                    return None

            return self._playlist[current_index]

    def get_next(self) -> MediaAssetPaths | None:
        return self.get_current(step=+1)

    def get_prev(self) -> MediaAssetPaths | None:
        return self.get_current(step=-1)

    def get_playlist(self) -> list[MediaAssetPaths]:
        with self._lock:
            return self._playlist.copy()

    @property
    def cursor_mode(self) -> StreamCursorMode:
        with self._lock:
            return self._cursor_mode

    @cursor_mode.setter
    def cursor_mode(self, mode: StreamCursorMode) -> None:
        with self._lock:
            self._cursor_mode = mode

    @property
    def visual_mode(self) -> StreamVisualMode:
        with self._lock:
            return self._visual_mode

    @visual_mode.setter
    def visual_mode(self, mode: StreamVisualMode) -> None:
        with self._lock:
            self._visual_mode = mode

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._is_playing

    @is_playing.setter
    def is_playing(self, playing: bool) -> None:
        with self._lock:
            self._is_playing = playing

    def pause(self) -> None:
        """Приостановить воспроизведение."""
        self.is_playing = False

    def resume(self) -> None:
        """Возобновить воспроизведение."""
        self.is_playing = True

    @property
    def current(self) -> MediaAssetPaths | None:
        """Текущий трек."""
        return self.get_current()

    @property
    def playlist(self) -> list[MediaAssetPaths]:
        """Копия текущего плейлиста."""
        return self.get_playlist()

    def clear(self) -> None:
        with self._lock:
            self._playlist.clear()
            self._cursor = None
