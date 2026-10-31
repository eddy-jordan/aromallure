from django import forms
from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from .models import Product, Order, OrderItem, Sale
from .admin_site import aromallure_admin
from .brands import brand_suggestions


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


class BrandSuggestInput(forms.TextInput):
    """Brand text box with a drop-down of existing brands. Customers' brand pages
    group products by brand name, so picking an existing spelling instead of
    retyping it keeps one brand from splitting into several."""

    def render(self, name, value, attrs=None, renderer=None):
        attrs = {**(attrs or {}), 'list': 'brand-suggestions', 'autocomplete': 'off'}
        box = super().render(name, value, attrs, renderer)
        options = format_html_join('', '<option value="{}">', ((b,) for b in brand_suggestions()))
        return format_html('{}<datalist id="brand-suggestions">{}</datalist>', box, options)


class ProductAdmin(admin.ModelAdmin):
    list_display        = ['name', 'brand', 'price', 'sale_price', 'stock', 'concentration', 'is_active', 'created_at']
    list_filter         = ['brand', 'concentration', 'is_active']
    search_fields       = ['name', 'brand', 'scent_notes']
    prepopulated_fields = {'slug': ('name',)}
    list_editable       = ['price', 'sale_price', 'stock', 'is_active']
    fields              = ['name', 'slug', 'brand', 'description', 'scent_notes',
                           'concentration', 'volume_ml', 'price', 'sale_price', 'stock',
                           'image_url', 'image', 'is_active']

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'brand':
            kwargs['widget'] = BrandSuggestInput(attrs={'class': 'vTextField', 'maxlength': 100})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class SaleAdmin(admin.ModelAdmin):
    list_display = ['name', 'start', 'end', 'announce_days', 'is_active', 'status']
    list_filter  = ['is_active']
    fields       = ['name', 'start', 'end', 'announce_days', 'is_active']

    @admin.display(description='Status')
    def status(self, obj):
        if not obj.is_active:
            return 'Switched off'
        now = timezone.now()
        if now < obj.start:
            return 'Scheduled'
        if now < obj.end:
            return 'Live now'
        return 'Ended'


class OrderItemInline(admin.TabularInline):
    model           = OrderItem
    extra           = 0
    readonly_fields = ['product_name', 'unit_price', 'subtotal']

    def subtotal(self, obj):
        # The "add another item" row is a blank OrderItem with no price yet;
        # computing its subtotal used to crash every order page with a 500.
        return obj.subtotal if obj.unit_price is not None else '-'


class OrderAdmin(admin.ModelAdmin):
    list_display    = ['id', 'user', 'full_name', 'status', 'payment_method',
                       'payment_reference', 'total_price', 'created_at']
    list_filter     = ['status', 'payment_method', 'created_at']
    search_fields   = ['full_name', 'user__username', 'phone_number', 'payment_reference']
    inlines         = [OrderItemInline]
    readonly_fields = ['total_price', 'payment_reference', 'created_at', 'updated_at']
    actions         = [mark_as_paid]


aromallure_admin.register(Sale, SaleAdmin)
aromallure_admin.register(Product, ProductAdmin)
aromallure_admin.register(Order, OrderAdmin)
aromallure_admin.register(User, UserAdmin)
aromallure_admin.register(Group, GroupAdmin)
