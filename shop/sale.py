"""
Black Friday sale window, the single source of truth for "is the sale on?".

Used by the banner/countdown context processor and by Product.current_price,
so the look and the prices always switch on and off together, driven only by
settings.BLACK_FRIDAY_START / BLACK_FRIDAY_END.
"""
from django.conf import settings
from django.utils import timezone


def sale_phase(now=None):
    """Return 'upcoming' before the start, 'live' inside the window, or None
    when the campaign is disabled or already over."""
    if not getattr(settings, 'BLACK_FRIDAY_ENABLED', False):
        return None
    now = now or timezone.now()
    if now < settings.BLACK_FRIDAY_START:
        return 'upcoming'
    if now < settings.BLACK_FRIDAY_END:
        return 'live'
    return None


def sale_is_live(now=None):
    return sale_phase(now) == 'live'
