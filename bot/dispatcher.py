"""Сборка Dispatcher и Bot."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from django.conf import settings

from bot.handlers import create, edit, premium, reminders, start, timezone as tz_handlers
from bot.middlewares import UserMiddleware


def build_dispatcher():
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    dp.include_router(start.router)
    dp.include_router(create.router)
    dp.include_router(reminders.router)
    dp.include_router(edit.router)
    dp.include_router(tz_handlers.router)
    dp.include_router(premium.router)

    return dp, bot
