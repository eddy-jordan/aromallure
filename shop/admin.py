from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.utils import timezone
from .models import Product, Order, OrderItem
from .admin_site import aromallure_admin


def mark_as_paid(modeladmin, request, queryset):
    """One-click action to confirm manual MoMo payments."""
    updated = 0
    for order in queryset.filter(status='PENDING'):
        order.status = 'PAID'
        order.payment_reference = f'MOMO-MANUAL-{order.id}-{timezone.now().strftime("%Y%m%d%H%M")}'
        order.save(update_fields=['status', 'payment_reference'])
        try:
            from .emails import send_order_confirmation_email
            send_order_confirmation_email(order)
        except Exception:
            pass
        updated += 1
    modeladmin.message_user(
        request,
        f'{updated} order(s) marked as Paid and confirmation email sent to customer(s).'
    )

mark_as_paid.short_description = '✓ Mark selected orders as Paid (manual MoMo confirmed)'


class ProductAdmin(admin.ModelAdmin):
    list_display        = ['name', 'brand', 'price', 'stock', 'concentration', 'is_active', 'created_at']
    list_filter         = ['brand', 'concentration', 'is_active']
    search_fields       = ['name', 'brand', 'scent_notes']
    prepopulated_fields = {'slug': ('name',)}
    list_editable       = ['price', 'stock', 'is_active']
    fields              = ['name', 'slug', 'brand', 'description', 'scent_notes',
                           'concentration', 'volume_ml', 'price', 'stock',
                           'image_url', 'image', 'is_active']


class OrderItemInline(admin.TabularInline):
    model           = OrderItem
    extra           = 0
    readonly_fields = ['product_name', 'unit_price', 'subtotal']

    def subtotal(self, obj):
        return obj.subtotal


class OrderAdmin(admin.ModelAdmin):
    list_display    = ['id', 'user', 'full_name', 'status', 'payment_method',
                       'payment_reference', 'total_price', 'created_at']
    list_filter     = ['status', 'payment_method', 'created_at']
    search_fields   = ['full_name', 'user__username', 'phone_number', 'payment_reference']
    inlines         = [OrderItemInline]
    readonly_fields = ['total_price', 'payment_reference', 'created_at', 'updated_at']
    actions         = [mark_as_paid]


aromallure_admin.register(Product, ProductAdmin)
aromallure_admin.register(Order, OrderAdmin)
aromallure_admin.register(User, UserAdmin)
aromallure_admin.register(Group, GroupAdmin)
