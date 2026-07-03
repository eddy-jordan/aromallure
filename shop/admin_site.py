"""
Custom admin site that overrides the index view to inject
dashboard stats into the admin homepage template.
"""
from django.contrib.admin import AdminSite
from django.utils import timezone


class AromallureAdminSite(AdminSite):
    site_header  = 'Aromallure Admin'
    site_title   = 'Aromallure'
    index_title  = 'Dashboard'

    def index(self, request, extra_context=None):
        from shop.models import Order, Product
        from django.contrib.auth.models import User
        from django.db.models import Sum

        today = timezone.now().date()
        week_ago = timezone.now() - timezone.timedelta(days=7)

        extra_context = extra_context or {}
        extra_context.update({
            'total_orders':    Order.objects.count(),
            'orders_today':    Order.objects.filter(created_at__date=today).count(),
            'pending_orders':  Order.objects.filter(status='PENDING').count(),
            'total_revenue':   Order.objects.filter(status='PAID')
                                    .aggregate(t=Sum('total_price'))['t'] or 0,
            'recent_orders':   Order.objects.select_related('user')
                                    .prefetch_related('items')
                                    .order_by('-created_at')[:10],
            'low_stock':       Product.objects.filter(
                                    is_active=True, stock__lte=3
                               ).order_by('stock'),
            'total_customers': User.objects.filter(is_staff=False).count(),
            'new_customers_week': User.objects.filter(
                                    is_staff=False,
                                    date_joined__gte=week_ago
                               ).count(),
        })
        return super().index(request, extra_context)


aromallure_admin = AromallureAdminSite(name='aromallure_admin')
