"""
Sale campaign windows: which sale's banner, hero and countdown to show.

Sales are rows in the admin-editable Sale model (name, start, end, on/off) and
drive the storefront campaign look only. They do NOT control prices: a product
shows its sale price whenever one is entered (see Product.on_sale).

The active sales are cached briefly so the lookup done on every request costs
no query most of the time; the cache only holds the sale rows (not whether a
sale is live), so start/end boundaries stay exact and admin edits show up
within CACHE_SECONDS (immediately in the process that saved them).
"""
from datetime import timedelta

from django.core.cache import cache
from django.db import OperationalError, ProgrammingError
from django.utils import timezone

CACHE_KEY = 'shop:active_sales'
CACHE_SECONDS = 30


def clear_sale_cache():
    cache.delete(CACHE_KEY)


def _active_sales():
    sales = cache.get(CACHE_KEY)
    if sales is None:
        from .models import Sale
        try:
            sales = list(
                Sale.objects.filter(is_active=True)
                .values('id', 'name', 'start', 'end', 'announce_days')
            )
        except (OperationalError, ProgrammingError):
            # Table not created yet (e.g. mid-deploy before migrate): behave
            # as "no sale" instead of taking the storefront down.
            return []
        cache.set(CACHE_KEY, sales, CACHE_SECONDS)
    return sales


def get_current_sale(now=None):
    """Return (sale_dict, phase) where phase is 'live' or 'upcoming', or
    (None, None) when nothing should be shown.

    A live sale wins; if several overlap, the most recently started one is
    used. Otherwise the nearest sale that starts within its own
    announce_days is shown as 'upcoming' (a teaser countdown)."""
    now = now or timezone.now()
    sales = _active_sales()

    live = [s for s in sales if s['start'] <= now < s['end']]
    if live:
        return max(live, key=lambda s: s['start']), 'live'

    upcoming = [
        s for s in sales
        if now < s['start']
        and s['announce_days'] > 0
        and s['start'] - now <= timedelta(days=s['announce_days'])
    ]
    if upcoming:
        return min(upcoming, key=lambda s: s['start']), 'upcoming'

    return None, None


def sale_phase(now=None):
    return get_current_sale(now)[1]
