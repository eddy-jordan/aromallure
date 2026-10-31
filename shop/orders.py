"""
Order lifecycle: stock, cancelling, reopening, releasing unpaid orders, and
telling the owner about new orders.

How stock works in this shop: it is taken from the product the moment an order
is placed (so two customers can't buy the last bottle). That means a Pending or
Paid order is holding stock. Cancelling it must give the stock back, and a
Cancelled order can only be reopened if the stock is still there. Shipped and
Delivered orders have left the building, so they can't be cancelled here.

Unpaid orders are released automatically after settings.UNPAID_ORDER_HOURS so
that customers who never pay don't hold perfumes (especially during a sale).
There is no scheduler on this hosting plan, so the sweep runs on shop activity,
at most once every few minutes (see sweep_expired_orders), and can also be run
by hand with `python manage.py expire_unpaid_orders`.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from .emails import send_order_shipped_email, send_owner_new_order_email
from .models import Order, Product

logger = logging.getLogger('shop')

# Statuses that have taken stock but not yet sent the goods out.
CANCELLABLE = ('PENDING', 'PAID')
SWEEP_CACHE_KEY = 'shop:order-sweep'
SWEEP_EVERY_SECONDS = 300


def _items_with_products(order):
    return [item for item in order.items.select_related('product') if item.product_id]


def release_stock(order):
    """Give an order's perfumes back to stock."""
    for item in _items_with_products(order):
        Product.objects.filter(pk=item.product_id).update(stock=F('stock') + item.quantity)


def stock_shortages(order):
    """Human-readable list of items that are no longer in stock in the
    quantity the order needs (empty when the order could be taken again)."""
    problems = []
    for item in _items_with_products(order):
        if item.product.stock < item.quantity:
            problems.append(f'{item.product_name} (needs {item.quantity}, only {item.product.stock} in stock)')
    return problems


def take_stock(order):
    """Take an order's perfumes out of stock again (reopening a cancelled
    order). Returns the names it could not take because stock ran out in the
    meantime; the rest are taken."""
    short = []
    for item in _items_with_products(order):
        taken = Product.objects.filter(pk=item.product_id, stock__gte=item.quantity).update(
            stock=F('stock') - item.quantity)
        if not taken:
            short.append(item.product_name)
    return short


def cancel_order(order):
    """Cancel a Pending or Paid order and return its stock. Safe to call twice:
    the second call does nothing, so stock can never be returned twice.
    Returns True if this call cancelled it."""
    with transaction.atomic():
        locked = Order.objects.select_for_update().get(pk=order.pk)
        if locked.status not in CANCELLABLE:
            return False
        release_stock(locked)
        locked.status = 'CANCELLED'
        locked.save(update_fields=['status', 'updated_at'])
    order.status = 'CANCELLED'
    return True


def mark_shipped(order):
    """Paid -> Shipped, then email the customer. Only a Paid order can ship.
    Returns True if it changed the order."""
    if order.status != 'PAID':
        return False
    order.status = 'SHIPPED'
    order.save(update_fields=['status', 'updated_at'])
    notify_customer_shipped(order)
    return True


def notify_customer_shipped(order):
    try:
        send_order_shipped_email(order)
    except Exception:
        logger.exception('Could not send the shipped email for order #%s', order.pk)


def whatsapp_link(phone):
    """wa.me link for a customer's phone number (Ghana numbers starting with 0
    become +233...). Empty if the number has no digits."""
    digits = ''.join(ch for ch in (phone or '') if ch.isdigit())
    if not digits:
        return ''
    if digits.startswith('0'):
        digits = '233' + digits[1:]
    return f'https://wa.me/{digits}'


def notify_owner_of_new_order(request, order):
    """Email the store owner that an order has just been placed. Never raises:
    a failed email must not break a customer's checkout."""
    to = getattr(settings, 'OWNER_ORDER_EMAIL', '')
    if not to:
        return
    try:
        admin_url = request.build_absolute_uri(reverse('aromallure_admin:shop_order_change', args=[order.pk]))
        send_owner_new_order_email(order, to, admin_url, whatsapp_link(order.phone_number))
    except Exception:
        logger.exception('Could not send the new-order alert for order #%s', order.pk)


def release_expired_orders(hours=None):
    """Cancel Pending orders older than `hours` (default settings.UNPAID_ORDER_HOURS)
    and return their stock. Returns how many were released."""
    hours = settings.UNPAID_ORDER_HOURS if hours is None else hours
    if hours <= 0:
        return 0
    cutoff = timezone.now() - timedelta(hours=hours)
    released = 0
    for order in Order.objects.filter(status='PENDING', created_at__lt=cutoff):
        if cancel_order(order):
            released += 1
            logger.info('Released unpaid order #%s (older than %s hours)', order.pk, hours)
    return released


def sweep_expired_orders():
    """release_expired_orders(), but at most once every few minutes per server
    process, and never allowed to break the page that triggered it. Called from
    the shop pages, the cart and checkout so stock is accurate when it matters."""
    try:
        if not cache.add(SWEEP_CACHE_KEY, 1, SWEEP_EVERY_SECONDS):
            return 0
        return release_expired_orders()
    except Exception:
        logger.exception('Releasing expired orders failed')
        return 0
