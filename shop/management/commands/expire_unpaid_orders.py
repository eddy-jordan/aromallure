from django.conf import settings
from django.core.management.base import BaseCommand

from shop.orders import release_expired_orders


class Command(BaseCommand):
    help = ('Cancel Pending orders that have gone unpaid for too long and put their '
            'perfumes back in stock. This also happens automatically as the shop is used; '
            'this command is for running it by hand or from a scheduler.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours', type=int, default=None,
            help=f'Release orders older than this many hours (default: {settings.UNPAID_ORDER_HOURS}).')

    def handle(self, *args, **options):
        released = release_expired_orders(options['hours'])
        self.stdout.write(self.style.SUCCESS(f'Released {released} unpaid order(s).'))
