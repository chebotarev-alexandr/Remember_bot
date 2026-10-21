"""Команда запуска Telegram-бота (long-polling)."""

import asyncio
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Запускает Telegram-бота (long-polling)"

    def handle(self, *args, **options):
        if not settings.BOT_TOKEN:
            self.stderr.write("BOT_TOKEN не задан. Укажите его в окружении или .env.")
            raise SystemExit(1)
        try:
            asyncio.run(self._run())
        except KeyboardInterrupt:
            self.stdout.write("Остановлено.")

    async def _run(self):
        from bot.dispatcher import build_dispatcher
        from bot.scheduler import scheduler_loop

        dp, bot = build_dispatcher()
        asyncio.create_task(scheduler_loop(bot))
        self.stdout.write("✅ Бот запущен. Ctrl+C для остановки.")
        await dp.start_polling(bot)
