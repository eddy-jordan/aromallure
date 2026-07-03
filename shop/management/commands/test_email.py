import os
import resend
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Send a test email using Resend to verify your configuration'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address to send the test to')

    def handle(self, *args, **options):
        recipient  = options['email']
        api_key    = os.environ.get('RESEND_API_KEY', '')
        from_email = settings.DEFAULT_FROM_EMAIL

        self.stdout.write(f'\nAPI key present: {"Yes" if api_key else "No — add RESEND_API_KEY to your .env file"}')
        self.stdout.write(f'From address:   {from_email}')
        self.stdout.write(f'Sending to:     {recipient}\n')

        if not api_key:
            self.stdout.write(self.style.ERROR('No RESEND_API_KEY found. Add it to your .env file and restart the server.'))
            return

        try:
            resend.api_key = api_key
            result = resend.Emails.send({
                "from":    from_email,
                "to":      [recipient],
                "subject": f"Test email from {settings.SITE_NAME}",
                "text":    f"If you receive this, your Resend email configuration is working correctly for {settings.SITE_NAME}!",
            })
            self.stdout.write(self.style.SUCCESS(f'✅ Email sent! Resend ID: {result.get("id", "unknown")}'))
            self.stdout.write('Check your inbox (and spam folder).')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Failed: {e}'))
            self.stdout.write('\nCheck that your domain is verified on Resend and the API key is correct.')
