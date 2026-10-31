"""
Emails: order confirmations via Resend HTTP API.

Uses Resend's HTTP API over port 443 (HTTPS) — works on all networks
including those that block SMTP ports.

Set RESEND_API_KEY and EMAIL_FROM in your .env file locally,
and in Render's environment variables dashboard for production.
"""
import os
import resend
from django.template.loader import render_to_string
from django.conf import settings


def send_order_confirmation_email(order):
    if not order.user.email:
        return

    api_key = os.environ.get('RESEND_API_KEY', '')
    if not api_key:
        print(f"[EMAIL] No RESEND_API_KEY set — skipping confirmation email for order #{order.id}")
        return

    resend.api_key = api_key

    context   = {'order': order, 'store_name': settings.SITE_NAME}
    subject   = f"Your {settings.SITE_NAME} order #{order.id} is confirmed"
    text_body = render_to_string('shop/email/order_confirmation_email.txt', context)
    html_body = render_to_string('shop/email/order_confirmation_email.html', context)

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL',
                         f'{settings.SITE_NAME} <hello@aromallure.store>')

    resend.Emails.send({
        "from":    from_email,
        "to":      [order.user.email],
        "subject": subject,
        "text":    text_body,
        "html":    html_body,
    })


def _send(to, subject, text_body, html_body=None):
    """Send through Resend. Returns False (and sends nothing) when no API key is
    configured, which is the normal state on a developer's machine."""
    api_key = os.environ.get('RESEND_API_KEY', '')
    if not api_key:
        print(f"[EMAIL] No RESEND_API_KEY set — skipping email '{subject}'")
        return False

    resend.api_key = api_key
    payload = {
        "from":    getattr(settings, 'DEFAULT_FROM_EMAIL', f'{settings.SITE_NAME} <hello@aromallure.store>'),
        "to":      [to],
        "subject": subject,
        "text":    text_body,
    }
    if html_body:
        payload["html"] = html_body
    resend.Emails.send(payload)
    return True


def send_order_shipped_email(order):
    """Tell the customer their order is on its way."""
    if not order.user.email:
        return False
    context = {'order': order, 'store_name': settings.SITE_NAME}
    return _send(
        order.user.email,
        f"Your {settings.SITE_NAME} order #{order.id} is on its way",
        render_to_string('shop/email/order_shipped_email.txt', context),
        render_to_string('shop/email/order_shipped_email.html', context),
    )


def send_owner_new_order_email(order, to, admin_url, whatsapp_url=''):
    """Tell the store owner a new order has just been placed."""
    context = {
        'order': order,
        'store_name': settings.SITE_NAME,
        'admin_url': admin_url,
        'whatsapp_url': whatsapp_url,
        'hold_hours': getattr(settings, 'UNPAID_ORDER_HOURS', 0),
    }
    return _send(
        to,
        f"New order #{order.id}, GH₵{order.total_price}, waiting for payment",
        render_to_string('shop/email/owner_new_order_email.txt', context),
    )
