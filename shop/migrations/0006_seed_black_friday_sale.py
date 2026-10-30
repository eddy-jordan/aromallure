import os
from datetime import datetime, timezone as dt_timezone

from django.db import migrations


def _env_datetime(name, default):
    """Honour BLACK_FRIDAY_START / BLACK_FRIDAY_END if they were set in the
    environment (the previous way of moving the dates), so a date already
    extended in Render is carried over instead of silently reset."""
    raw = os.environ.get(name, '')
    if not raw:
        return default
    parsed = datetime.fromisoformat(raw)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt_timezone.utc)


def seed_black_friday(apps, schema_editor):
    Sale = apps.get_model('shop', 'Sale')
    if Sale.objects.exists():
        return
    Sale.objects.create(
        name='Black Friday',
        start=_env_datetime('BLACK_FRIDAY_START', datetime(2026, 11, 28, 0, 0, 0, tzinfo=dt_timezone.utc)),
        end=_env_datetime('BLACK_FRIDAY_END', datetime(2026, 11, 30, 0, 0, 0, tzinfo=dt_timezone.utc)),
        announce_days=30,
        is_active=os.environ.get('BLACK_FRIDAY_ENABLED', 'True') == 'True',
    )


def unseed_black_friday(apps, schema_editor):
    apps.get_model('shop', 'Sale').objects.filter(name='Black Friday').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_sale_model'),
    ]

    operations = [
        migrations.RunPython(seed_black_friday, unseed_black_friday),
    ]
