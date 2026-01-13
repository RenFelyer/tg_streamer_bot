from enum import Enum, auto

from aiogram.types import BotCommand


class StreamVisualMode(Enum):
    """Режим визуального отображения трансляции."""

    VIDEO_CONTENT = auto()  # Видео и его оригинальный видеоряд
    VIDEO_THUMBNAIL = auto()  # Аудио из видео + статичное превью
    VIDEO_PLACEHOLDER = auto()  # Аудио из видео + заданный логотип


class StreamCursorMode(Enum):
    """Логика работы курсора (очереди) после окончания трека."""

    PLAY_AND_DELETE = auto()  # Проиграть и удалить из списка
    PLAY_AND_STOP = auto()  # Проиграть, сдвинуться, если конец списка — стоп/пауза
    LOOP_PLAYLIST = auto()  # Проигрывать плейлист по кругу (возвращаться к началу)


class CommonCommand(Enum):
    """Общие команды для управления плеером."""

    help = BotCommand(command='help', description='Показать это сообщение помощи')
    pause = BotCommand(command='pause', description='Поставить воспроизведение на паузу')
    resume = BotCommand(command='resume', description='Возобновить воспроизведение')
    skip = BotCommand(command='skip', description='Пропустить текущий трек')

    play = BotCommand(command='play', description='Воспроизвести трек по ссылке или поисковому запросу')
    playlist = BotCommand(command='playlist', description='Показать текущий плейлист')

    clear_playlist = BotCommand(command='clear_playlist', description='Очистить текущий плейлист')
    now_playing = BotCommand(command='now_playing', description='Показать информацию о текущем треке')

    set_visual_mode = BotCommand(command='set_visual_mode', description='Установить режим визуализации трансляции')
    set_cursor_mode = BotCommand(command='set_cursor_mode', description='Установить режим работы курсора плейлиста')

    @staticmethod
    def list_commands() -> list[BotCommand]:
        return [command.value for command in CommonCommand]
