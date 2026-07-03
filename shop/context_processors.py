from django.conf import settings
from .cart import Cart


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
