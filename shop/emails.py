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
