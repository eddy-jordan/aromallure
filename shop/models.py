from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from .sale import sale_is_live


class Product(models.Model):
    """A perfume listed in the store."""

    CONCENTRATION_CHOICES = [
        ('EDP', 'Eau de Parfum'),
        ('EDT', 'Eau de Toilette'),
        ('PARFUM', 'Parfum (Extrait)'),
        ('EDC', 'Eau de Cologne'),
    ]

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True,
                             help_text="Auto-generated from the name if left blank.")
    brand = models.CharField(max_length=100)
    description = models.TextField()
    scent_notes = models.CharField(max_length=255, blank=True,
                                    help_text="e.g. 'Bergamot, Jasmine, Sandalwood'")
    concentration = models.CharField(max_length=10, choices=CONCENTRATION_CHOICES, default='EDP')
    volume_ml = models.PositiveIntegerField(default=50, help_text="Bottle size in millilitres")
    price = models.DecimalField(max_digits=8, decimal_places=2)
    sale_price = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Optional Black Friday price. Only used while the Black Friday "
                  "sale is live, then the normal price above returns automatically. "
                  "Leave blank for no discount. Must be lower than the normal price."
    )
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    image_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text="Paste a direct Cloudinary image URL here. "
                  "Upload your image at cloudinary.com → Assets → Upload, "
                  "then right-click the image → Copy URL."
    )
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide from the store without deleting.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.brand} — {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(f"{self.brand}-{self.name}")
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('product_detail', kwargs={'slug': self.slug})

    @property
    def in_stock(self):
        return self.stock > 0

    def clean(self):
        super().clean()
        if self.sale_price is not None and self.price is not None and self.sale_price >= self.price:
            raise ValidationError({'sale_price': 'The sale price must be lower than the normal price.'})

    @property
    def on_sale(self):
        """True only while the sale window is live AND this product has a
        valid sale price, so prices revert on their own when the window closes."""
        return (
            self.sale_price is not None
            and 0 < self.sale_price < self.price
            and sale_is_live()
        )

    @property
    def current_price(self):
        """The price to charge right now: the sale price during the sale,
        otherwise the normal price. Everything that bills a customer uses this."""
        return self.sale_price if self.on_sale else self.price

    @property
    def discount_percent(self):
        if not self.on_sale:
            return 0
        return int(round((self.price - self.sale_price) / self.price * 100))


class Order(models.Model):
    """A placed order, created at checkout from the user's session cart."""

    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('MOMO', 'Mobile Money'),
        ('CASH', 'Cash on Delivery'),
    ]

    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    full_name        = models.CharField(max_length=150)
    shipping_address = models.TextField()
    phone_number     = models.CharField(max_length=30)
    status           = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PENDING')
    payment_method   = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='MOMO')
    # Paystack transaction reference — populated once payment is confirmed via webhook
    payment_reference = models.CharField(max_length=100, blank=True, default='')
    total_price      = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.pk} — {self.user.username} ({self.status})"

    def recalculate_total(self):
        total = sum(item.subtotal for item in self.items.all())
        self.total_price = total
        self.save(update_fields=['total_price'])
        return total


class OrderItem(models.Model):
    """A single product line within an order, with price captured at purchase time."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name='order_items')
    product_name = models.CharField(max_length=150, help_text="Snapshot in case the product is later renamed/deleted")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2,
                                      help_text="Price at the time of purchase, not the live product price")

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity
