from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import PeerChannel, User
import asyncio
import html
import json
from pathlib import Path

# ========== КОНФИГУРАЦИЯ ==========
API_ID = 25788387
API_HASH = '72cb4a263f27dc80585c6caa13f66136'

# @Lardaux_bot — только отправка (sendMessage), без getUpdates,
# чтобы не конфликтовать с уже работающим API/webhook.
BOT_TOKEN = '7591428095:AAHMqgqRra5IXav_xCze0wlFs2Y7FN9iDys'

CHANNEL_USERNAME = '@lardauxofficial'

# Кому слать уведомления о комментариях (Telegram user id).
# Пользователь должен хотя бы раз нажать /start у @Lardaux_bot.
# Можно задать здесь и/или в subscribers.json
NOTIFY_USER_IDS = [
    # 123456789,
]

SUBSCRIBERS_FILE = Path(__file__).with_name('subscribers.json')


def load_subscribers() -> set[int]:
    ids = set(NOTIFY_USER_IDS)
    if SUBSCRIBERS_FILE.exists():
        try:
            data = json.loads(SUBSCRIBERS_FILE.read_text(encoding='utf-8'))
            ids.update(int(x) for x in data)
        except Exception as e:
            print(f'⚠️ Не удалось прочитать {SUBSCRIBERS_FILE.name}: {e}')
    return ids


def message_link(entity, message_id: int) -> str:
    if getattr(entity, 'username', None):
        return f'https://t.me/{entity.username}/{message_id}'
    return f'https://t.me/c/{entity.id}/{message_id}'


def sender_label(sender) -> str:
    if sender is None:
        return 'Неизвестный'
    if isinstance(sender, User):
        parts = [sender.first_name or '', sender.last_name or '']
        name = ' '.join(p for p in parts if p).strip() or 'Без имени'
        if sender.username:
            return f'{name} (@{sender.username})'
        return f'{name} (id {sender.id})'
    title = getattr(sender, 'title', None)
    if title:
        return title
    return str(getattr(sender, 'id', 'Неизвестный'))


async def main():
    # user — читает комментарии; bot — только рассылает уведомления
    user = TelegramClient('user_session', API_ID, API_HASH)
    bot = TelegramClient('lardaux_bot_session', API_ID, API_HASH)

    await user.start()
    await bot.start(bot_token=BOT_TOKEN)

    me = await user.get_me()
    print(f'👤 User-сессия: {me.first_name} (id {me.id})')

    subscribers = load_subscribers()
    if not subscribers:
        print('❌ Нет получателей. Добавьте user id в NOTIFY_USER_IDS или subscribers.json')
        print('   Узнать свой id: напишите @userinfobot')
        await user.disconnect()
        await bot.disconnect()
        return

    channel = await user.get_entity(CHANNEL_USERNAME)
    full = await user(GetFullChannelRequest(channel))
    linked_chat_id = full.full_chat.linked_chat_id

    if not linked_chat_id:
        print('❌ У канала нет группы обсуждений. Включите комментарии в настройках канала.')
        await user.disconnect()
        await bot.disconnect()
        return

    discussion = await user.get_entity(linked_chat_id)
    discussion_title = getattr(discussion, 'title', linked_chat_id)

    print('🚀 Мониторинг комментариев запущен')
    print(f'📡 Канал: {CHANNEL_USERNAME}')
    print(f'💬 Группа: {discussion_title} ({linked_chat_id})')
    print(f'📬 Рассылка через @Lardaux_bot → {sorted(subscribers)}')

    @user.on(events.NewMessage(chats=discussion))
    async def on_new_comment(event):
        message = event.message

        if message.action:
            return
        if isinstance(message.from_id, PeerChannel) and message.from_id.channel_id == channel.id:
            return
        if message.sender_id == channel.id:
            return

        sender = await message.get_sender()
        author = sender_label(sender)
        text = (message.text or message.message or '').strip()
        if not text:
            text = '[медиа / стикер / файл без текста]'

        link = message_link(discussion, message.id)
        preview = text if len(text) <= 500 else text[:500] + '…'

        notify = (
            '💬 <b>Новый комментарий</b>\n'
            f'👤 {html.escape(author)}\n'
            f'📝 {html.escape(preview)}\n'
            f'🔗 <a href="{html.escape(link)}">Открыть комментарий</a>'
        )

        for user_id in list(subscribers):
            try:
                await bot.send_message(
                    user_id,
                    notify,
                    parse_mode='html',
                    link_preview=False,
                )
                print(f'✅ → {user_id}: {author} — {preview[:60]!r}')
            except Exception as e:
                print(f'❌ Не доставлено {user_id}: {e}')

    await user.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
