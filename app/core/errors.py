from app.core.enums import StreamCursorMode


class PlaylistError(Exception):
    """Базовое исключение для ошибок плейлиста."""


class MediaFileNotFoundError(PlaylistError):
    """Исключение при попытке добавить несуществующий медиафайл."""

    def __init__(self, media_id: str) -> None:
        super().__init__(f'Media file does not exist: {media_id}')
        self.media_id = media_id


class CursorIndexOutOfRangeError(PlaylistError):
    """Исключение при установке курсора вне допустимого диапазона."""

    def __init__(self, index: int, playlist_size: int) -> None:
        super().__init__(f'Cursor index {index} is out of range for playlist of size {playlist_size}')
        self.index = index
        self.playlist_size = playlist_size
