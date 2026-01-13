"""Конфигурация логирования."""

import logging
import sys
from typing import Literal


def setup_logger(
    level: int = logging.INFO,
    fmt: str = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt: str = '%Y-%m-%d %H:%M:%S',
) -> None:
    """Настраивает корневой логгер приложения.

    Args:
        level: Уровень логирования.
        fmt: Формат сообщений.
        datefmt: Формат даты/времени.

    """
    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Удаляем существующие обработчики
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Создаём консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Форматирование
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    # Уменьшаем шум от сторонних библиотек
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('yt_dlp').setLevel(logging.WARNING)
    logging.getLogger('av').setLevel(logging.WARNING)


__all__ = ['setup_logger']
