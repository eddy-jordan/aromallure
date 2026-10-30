from django.conf import settings
from django.utils import timezone
from .cart import Cart
from .sale import sale_phase


def store_name(request):
    """Makes SITE_NAME available in every template as {{ store_name }}.
    Named 'store_name' (not 'site_name') deliberately — Django's built-in
    LoginView and LogoutView already inject their OWN context variable
    called 'site_name' (for the django.contrib.sites framework), which
    would silently override ours on those specific pages otherwise.
    Change the store's name in one place: settings.SITE_NAME."""
    return {'store_name': getattr(settings, 'SITE_NAME', 'My Store')}


def cart_count(request):
    """Makes the cart item count available in every template, so the navbar
    badge stays accurate no matter which page the visitor is on."""
    return {'cart_item_count': len(Cart(request))}


def black_friday(request):
    """Black Friday campaign state, driven entirely by the dates in settings.
    'upcoming' counts down to the start, 'live' counts down to the end, and
    outside that window black_friday is None so templates fall back to the
    normal storefront with no manual switch-off needed.

    The countdown is seeded with the seconds remaining (computed here on the
    server) rather than an absolute timestamp, so a visitor's wrong device
    clock can't make it show the wrong time."""
    now   = timezone.now()
    phase = sale_phase(now)
    if phase is None:
        return {'black_friday': None}

    start  = settings.BLACK_FRIDAY_START
    target = start if phase == 'upcoming' else settings.BLACK_FRIDAY_END

    seconds = max(0, int((target - now).total_seconds()))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)

    return {'black_friday': {
        'phase':     phase,
        'start':     start,
        'seconds':   seconds,
        'days':      f'{days:02d}',
        'hours':     f'{hours:02d}',
        'minutes':   f'{minutes:02d}',
        'secs':      f'{secs:02d}',
    }}
