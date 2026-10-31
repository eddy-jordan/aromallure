from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from .models import Product, Order, OrderItem, Sale
from .admin_site import aromallure_admin
from .brands import brand_suggestions
from .orders import (
    CANCELLABLE, cancel_order, mark_shipped, notify_customer_shipped,
    release_stock, stock_shortages, take_stock,
)


def mark_as_paid(modeladmin, request, queryset):
    """One-click action to confirm manual MoMo payments."""
    updated = 0
    cancelled = []
    for order in queryset:
        if order.status == 'CANCELLED':
            cancelled.append(f'#{order.id}')
            continue
        if order.status != 'PENDING':
            continue
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
    if cancelled:
        modeladmin.message_user(
            request,
            f'{", ".join(cancelled)} cannot be marked as Paid because the order was cancelled '
            f'(unpaid orders are released after {settings.UNPAID_ORDER_HOURS} hours). To bring one back, open it, '
            f'change its status to Pending and save (this works only if the perfumes are still in stock), '
            f'then mark it as Paid.',
            level=messages.WARNING,
        )

mark_as_paid.short_description = '✓ Mark selected orders as Paid (manual MoMo confirmed)'


@admin.action(description='🚚 Mark selected orders as Shipped (emails the customer)')
def mark_as_shipped(modeladmin, request, queryset):
    shipped = skipped = 0
    for order in queryset:
        if mark_shipped(order):
            shipped += 1
        else:
            skipped += 1
    modeladmin.message_user(request, f'{shipped} order(s) marked as Shipped and the customer(s) emailed.')
    if skipped:
        modeladmin.message_user(
            request,
            f'{skipped} order(s) skipped: only Paid orders can be shipped.',
            level=messages.WARNING,
        )


@admin.action(description='📦 Mark selected orders as Delivered')
def mark_as_delivered(modeladmin, request, queryset):
    delivered = skipped = 0
    for order in queryset:
        if order.status in ('PAID', 'SHIPPED'):
            order.status = 'DELIVERED'
            order.save(update_fields=['status', 'updated_at'])
            delivered += 1
        else:
            skipped += 1
    modeladmin.message_user(request, f'{delivered} order(s) marked as Delivered.')
    if skipped:
        modeladmin.message_user(
            request,
            f'{skipped} order(s) skipped: only Paid or Shipped orders can be delivered.',
            level=messages.WARNING,
        )


@admin.action(description='✗ Cancel selected orders (puts the perfumes back in stock)')
def cancel_orders(modeladmin, request, queryset):
    cancelled = skipped = 0
    refund = []
    for order in queryset:
        was_paid = order.status == 'PAID'
        if cancel_order(order):
            cancelled += 1
            if was_paid:
                refund.append(f'#{order.id}')
        else:
            skipped += 1
    modeladmin.message_user(request, f'{cancelled} order(s) cancelled and the perfumes put back in stock.')
    if refund:
        modeladmin.message_user(
            request,
            f'Remember to refund the customer(s) of the paid order(s) you cancelled: {", ".join(refund)}.',
            level=messages.WARNING,
        )
    if skipped:
        modeladmin.message_user(
            request,
            f'{skipped} order(s) skipped: only Pending or Paid orders can be cancelled '
            f'(shipped and delivered orders have already left, and cancelled ones are already done).',
            level=messages.WARNING,
        )


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


class OrderAdminForm(forms.ModelForm):
    """Guards the Status box on the order page. Stock follows the status (see
    shop/orders.py), so a few changes are refused instead of silently
    leaving the stock wrong."""

    class Meta:
        model  = Order
        fields = '__all__'

    def clean(self):
        data = super().clean()
        if not self.instance.pk or not data.get('status'):
            return data
        old = Order.objects.filter(pk=self.instance.pk).values_list('status', flat=True).first()
        new = data['status']
        if old == new:
            return data
        if new == 'CANCELLED' and old not in CANCELLABLE:
            self.add_error('status', 'Only Pending or Paid orders can be cancelled. Shipped and delivered orders have already left.')
        elif old == 'CANCELLED':
            problems = stock_shortages(self.instance)
            if problems:
                self.add_error(
                    'status',
                    'This cancelled order cannot be reopened yet because there is not enough stock for: '
                    + '; '.join(problems) + '. Add stock first.'
                )
        return data


class OrderAdmin(admin.ModelAdmin):
    form            = OrderAdminForm
    list_display    = ['id', 'user', 'full_name', 'status', 'payment_method',
                       'payment_reference', 'total_price', 'created_at']
    list_filter     = ['status', 'payment_method', 'created_at']
    search_fields   = ['full_name', 'user__username', 'phone_number', 'payment_reference']
    inlines         = [OrderItemInline]
    readonly_fields = ['total_price', 'payment_reference', 'created_at', 'updated_at']
    actions         = [mark_as_paid, mark_as_shipped, mark_as_delivered, cancel_orders]

    # Deleting an order that is still holding stock must give the stock back,
    # otherwise the perfumes would stay "sold" for an order that no longer exists.
    def delete_model(self, request, obj):
        if obj.status in CANCELLABLE:
            release_stock(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for order in queryset:
            if order.status in CANCELLABLE:
                release_stock(order)
        super().delete_queryset(request, queryset)

    def save_model(self, request, obj, form, change):
        old = Order.objects.filter(pk=obj.pk).values_list('status', flat=True).first() if change else None
        super().save_model(request, obj, form, change)
        if not change or old == obj.status:
            return
        # Changing the status by hand keeps stock and emails in step.
        if obj.status == 'CANCELLED' and old in CANCELLABLE:
            release_stock(obj)
            self.message_user(request, f'Order #{obj.id} cancelled and its perfumes put back in stock.')
        elif old == 'CANCELLED':
            short = take_stock(obj)
            self.message_user(request, f'Order #{obj.id} reopened and its perfumes taken out of stock again.')
            if short:
                self.message_user(
                    request,
                    f'Stock ran out for {", ".join(short)} while saving, so those were not taken. Check the stock.',
                    level=messages.WARNING,
                )
        if obj.status == 'SHIPPED':
            notify_customer_shipped(obj)
            self.message_user(request, f'Order #{obj.id} marked as Shipped and the customer emailed.')


aromallure_admin.register(Sale, SaleAdmin)
aromallure_admin.register(Product, ProductAdmin)
aromallure_admin.register(Order, OrderAdmin)
aromallure_admin.register(User, UserAdmin)
aromallure_admin.register(Group, GroupAdmin)
