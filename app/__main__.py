import asyncio
import logging
import sys
import threading

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import router as main_router
from app.core.config import settings, setup_logger
from app.core.enums import CommonCommand, StreamCursorMode, StreamVisualMode
from app.deliver import AVPlayer, AVStreamer
from app.receive import YTDLPReceiver

logger = logging.getLogger(__name__)


async def main() -> None:
    """Главная функция приложения."""
    # Настройка логирования
    setup_logger()

    # Валидация конфигурации
    if not settings.bot_token:
        logger.error('BOT_TOKEN не установлен в переменных окружения')
        sys.exit(1)

    if not settings.tg_link or not settings.tg_code:
        logger.error('TG_LINK и TG_CODE должны быть установлены для RTMP трансляции')
        sys.exit(1)

    rtmps_url = settings.rtmps_url
    if not rtmps_url or 'rtmp' not in rtmps_url.lower():
        logger.error('Invalid RTMPS URL. Check TG_LINK and TG_CODE in .env')
        sys.exit(1)

    placeholder_path = settings.placeholder_path
    if not placeholder_path.exists():
        logger.error('Placeholder image not found at %s', placeholder_path)
        sys.exit(1)

    player = AVPlayer(
        visual_mode=StreamVisualMode.VIDEO_CONTENT,
        cursor_mode=StreamCursorMode.LOOP_PLAYLIST,
    )
    streamer = AVStreamer(rtmps_url, player, settings.placeholder_path)
    downloader = YTDLPReceiver(settings.multimedia_dir)

    thread = threading.Thread(
        name='livestream_thread',
        target=streamer.run,
        daemon=True,
    )

    # Создаём бота и диспетчер
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
    await bot.set_my_commands(CommonCommand.list_commands())
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем роутеры (порядок важен!)
    dp.include_router(main_router)

    # Регистрируем хуки жизненного цикла
    dp.startup.register(thread.start)
    dp.shutdown.register(streamer.stop)

    # Запускаем polling
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            downloader=downloader,
            player=player,
        )
    finally:
        await bot.session.close()
        if thread.is_alive():
            await asyncio.to_thread(thread.join)


if __name__ == '__main__':
    asyncio.run(main())
