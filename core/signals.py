"""Signal handlers: SQLite WAL для конкурентного доступа (бот + админка)."""

from django.db.backends.signals import connection_created
from django.dispatch import receiver


@receiver(connection_created)
def enable_sqlite_wal(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
