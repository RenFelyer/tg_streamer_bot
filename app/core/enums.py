from enum import Enum, auto


class StreamVisualMode(Enum):
    """Режим визуального отображения трансляции."""

    VIDEO_CONTENT = auto()  # Видео и его оригинальный видеоряд
    VIDEO_PREVIEW = auto()  # Аудио из видео + статичное превью (обложка)
    VIDEO_LOGO = auto()  # Аудио из видео + заданный логотип


class PlaylistCursorMode(Enum):
    """Логика работы курсора (очереди) после окончания трека."""

    PLAY_AND_DELETE = auto()  # Проиграть и удалить из списка
    PLAY_AND_STOP = auto()  # Проиграть, сдвинуться, если конец списка — стоп/пауза
    LOOP_QUEUE = auto()  # Проиграть, сдвинуться, если конец — перейти в начало (цикл)
