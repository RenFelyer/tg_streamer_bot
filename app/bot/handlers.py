import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from app.bot.filters import IsAdmin
from app.core.enums import CommonCommand, StreamCursorMode, StreamVisualMode
from app.deliver import AVPlayer
from app.deliver.schemas import MediaAssetPaths
from app.receive import YTDLPReceiver

logger = logging.getLogger(__name__)

router = Router(name='main_router')
router.message.filter(IsAdmin())


@router.message(Command(CommonCommand.help.value.command))
async def cmd_help(message: Message) -> None:
    """Показать справку по командам."""
    logger.info('Пользователь %s запросил справку', message.from_user.id if message.from_user else 'Unknown')
    commands = CommonCommand.list_commands()
    help_text = '<b>📋 Доступные команды:</b>\n\n'
    help_text += '\n'.join(f'/{cmd.command} — {cmd.description}' for cmd in commands)
    await message.answer(help_text)


@router.message(Command(CommonCommand.pause.value.command))
async def cmd_pause(message: Message, player: AVPlayer) -> None:
    """Поставить воспроизведение на паузу."""
    user_id = message.from_user.id if message.from_user else 'Unknown'
    logger.info('Пользователь %s: команда pause (is_playing=%s)', user_id, player.is_playing)
    if not player.is_playing:
        logger.debug('Плеер уже на паузе, команда игнорирована')
        await message.answer('⏸ Воспроизведение уже на паузе.')
        return
    player.pause()
    logger.info('Воспроизведение приостановлено пользователем %s', user_id)
    await message.answer('⏸ Воспроизведение приостановлено.')


@router.message(Command(CommonCommand.resume.value.command))
async def cmd_resume(message: Message, player: AVPlayer) -> None:
    """Возобновить воспроизведение."""
    user_id = message.from_user.id if message.from_user else 'Unknown'
    logger.info('Пользователь %s: команда resume (is_playing=%s)', user_id, player.is_playing)
    if player.is_playing:
        logger.debug('Плеер уже воспроизводит, команда игнорирована')
        await message.answer('▶️ Воспроизведение уже идёт.')
        return
    player.resume()
    logger.info('Воспроизведение возобновлено пользователем %s', user_id)
    await message.answer('▶️ Воспроизведение возобновлено.')


@router.message(Command(CommonCommand.skip.value.command))
async def cmd_skip(message: Message, player: AVPlayer) -> None:
    """Пропустить текущий трек."""
    user_id = message.from_user.id if message.from_user else 'Unknown'
    logger.info('Пользователь %s: команда skip (cursor=%s)', user_id, player.cursor)
    if player.cursor is None:
        logger.debug('Плейлист пуст, пропуск невозможен')
        await message.answer('⚠️ Плейлист пуст.')
        return
    current_track = player.current
    player.next()
    logger.info('Трек пропущен: %s -> %s', current_track.mediafile.name if current_track else 'None', player.cursor)
    await message.answer('⏭ Трек пропущен.')


@router.message(Command(CommonCommand.play.value.command))
async def cmd_play(message: Message, command: CommandObject, player: AVPlayer, downloader: YTDLPReceiver) -> None:
    """Воспроизвести трек по ссылке или поисковому запросу."""
    user_id = message.from_user.id if message.from_user else 'Unknown'
    if not command.args:
        logger.debug('Пользователь %s: команда play без аргументов', user_id)
        await message.answer('⚠️ Укажите ссылку или поисковый запрос.\n\nПример: /play https://youtube.com/watch?v=...')
        return

    query = command.args.strip()
    logger.info('Пользователь %s: команда play, запрос: %s', user_id, query)
    status_msg = await message.answer(f'🔍 Ищу: <code>{query}</code>...')

    try:
        logger.debug('Начинаю загрузку: %s', query)
        result = downloader.download(query)
        if result is None or result.media is None:
            logger.warning('Загрузка не удалась: результат пустой для запроса %s', query)
            await status_msg.edit_text('❌ Не удалось найти или загрузить трек.')
            return

        if not (result.media.mediafile_path and result.media.thumbnail_path):
            logger.warning('Файлы отсутствуют после загрузки: %s', query)
            await status_msg.edit_text('❌ Загрузка не удалась или файлы отсутствуют.')
            return

        media = MediaAssetPaths(
            mediafile=result.media.mediafile_path,
            thumbnail=result.media.thumbnail_path,
        )
        player.append(media)
        logger.info('Трек добавлен в плейлист: %s (позиция %d)', result.media.identifier, len(player.playlist))

        title = result.media.identifier if result.media else query
        await status_msg.edit_text(f'✅ Добавлено в плейлист: <b>{title}</b>')

    except Exception as e:
        logger.exception('Ошибка при загрузке трека: %s', query)
        await status_msg.edit_text(f'❌ Ошибка при загрузке: {e}')


@router.message(Command(CommonCommand.playlist.value.command))
async def cmd_playlist(message: Message, player: AVPlayer) -> None:
    """Показать текущий плейлист."""
    user_id = message.from_user.id if message.from_user else 'Unknown'
    playlist = player.playlist
    logger.info('Пользователь %s: команда playlist (размер=%d, cursor=%s)', user_id, len(playlist), player.cursor)
    if not playlist:
        await message.answer('📭 Плейлист пуст.')
        return

    cursor = player.cursor
    lines = []
    for i, item in enumerate(playlist):
        prefix = '▶️ ' if i == cursor else f'{i + 1}. '
        name = item.mediafile.stem if item.mediafile else 'Неизвестный трек'
        lines.append(f'{prefix}{name}')

    text = '<b>📜 Текущий плейлист:</b>\n\n' + '\n'.join(lines)
    await message.answer(text)


@router.message(Command(CommonCommand.clear_playlist.value.command))
async def cmd_clear_playlist(message: Message, player: AVPlayer) -> None:
    """Очистить плейлист."""
    user_id = message.from_user.id if message.from_user else 'Unknown'
    prev_size = len(player.playlist)
    player.clear()
    logger.info('Пользователь %s: плейлист очищен (было %d треков)', user_id, prev_size)
    await message.answer('🗑 Плейлист очищен.')


@router.message(Command(CommonCommand.now_playing.value.command))
async def cmd_now_playing(message: Message, player: AVPlayer) -> None:
    """Показать информацию о текущем треке."""
    user_id = message.from_user.id if message.from_user else 'Unknown'
    current = player.current
    logger.info('Пользователь %s: команда now_playing (is_playing=%s)', user_id, player.is_playing)
    if current is None:
        await message.answer('🔇 Сейчас ничего не воспроизводится.')
        return

    name = current.mediafile.stem if current.mediafile else 'Неизвестный трек'
    status = '▶️ Воспроизводится' if player.is_playing else '⏸ На паузе'
    text = f'🎵 <b>Сейчас играет:</b>\n\n{name}\n\n{status}'
    await message.answer(text)


@router.message(Command(CommonCommand.set_visual_mode.value.command))
async def cmd_set_visual_mode(message: Message, command: CommandObject, player: AVPlayer) -> None:
    """Установить режим визуализации трансляции."""
    user_id = message.from_user.id if message.from_user else 'Unknown'
    modes = {
        'video': StreamVisualMode.VIDEO_CONTENT,
        'thumbnail': StreamVisualMode.VIDEO_THUMBNAIL,
        'placeholder': StreamVisualMode.VIDEO_PLACEHOLDER,
    }

    if not command.args or command.args.lower() not in modes:
        logger.debug('Пользователь %s: set_visual_mode без корректных аргументов', user_id)
        modes_list = ', '.join(modes.keys())
        await message.answer(
            f'⚠️ Укажите режим визуализации.\n\n'
            f'Доступные режимы: <code>{modes_list}</code>\n\n'
            f'Пример: /set_visual_mode video',
        )
        return

    mode = modes[command.args.lower()]
    old_mode = player.visual_mode
    player.visual_mode = mode
    logger.info('Пользователь %s: visual_mode изменён %s -> %s', user_id, old_mode.name, mode.name)
    await message.answer(f'🎬 Режим визуализации установлен: <b>{command.args.lower()}</b>')


@router.message(Command(CommonCommand.set_cursor_mode.value.command))
async def cmd_set_cursor_mode(message: Message, command: CommandObject, player: AVPlayer) -> None:
    """Установить режим работы курсора плейлиста."""
    modes = {
        'delete': StreamCursorMode.PLAY_AND_DELETE,
        'stop': StreamCursorMode.PLAY_AND_STOP,
        'loop': StreamCursorMode.LOOP_PLAYLIST,
    }

    user_id = message.from_user.id if message.from_user else 'Unknown'
    if not command.args or command.args.lower() not in modes:
        logger.debug('Пользователь %s: set_cursor_mode без корректных аргументов', user_id)
        modes_list = ', '.join(modes.keys())
        await message.answer(
            f'⚠️ Укажите режим курсора.\n\n'
            f'Доступные режимы: <code>{modes_list}</code>\n\n'
            f'• <b>delete</b> — проиграть и удалить\n'
            f'• <b>stop</b> — остановиться в конце\n'
            f'• <b>loop</b> — зациклить плейлист\n\n'
            f'Пример: /set_cursor_mode loop',
        )
        return

    mode = modes[command.args.lower()]
    old_mode = player.cursor_mode
    player.cursor_mode = mode
    logger.info('Пользователь %s: cursor_mode изменён %s -> %s', user_id, old_mode.name, mode.name)
    await message.answer(f'🔄 Режим курсора установлен: <b>{command.args.lower()}</b>')


__all__ = ['router']
