"""
Session-based shopping cart.

Design decision (from Phase 1): the cart itself is NOT a database model.
It lives in the visitor's session — meaning it works for anonymous browsers
too, and never needs cleanup for abandoned carts. A real, permanent Order
is only created at the moment of checkout. This keeps the database clean
and matches how most small storefronts actually work.
"""
from decimal import Decimal
from .models import Product

CART_SESSION_KEY = 'cart'


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if cart is None:
            cart = self.session[CART_SESSION_KEY] = {}
        self.cart = cart

    def _save(self):
        self.session.modified = True

    def add(self, product, quantity=1):
        """Add a product, or increase quantity if it's already in the cart."""
        product_id = str(product.id)
        if product_id in self.cart:
            self.cart[product_id]['quantity'] += quantity
        else:
            self.cart[product_id] = {'quantity': quantity}
        self._save()

    def update(self, product_id, quantity):
        """Set an exact quantity. Removing the item if quantity drops to 0 or below."""
        product_id = str(product_id)
        if product_id in self.cart:
            if quantity <= 0:
                self.remove(product_id)
            else:
                self.cart[product_id]['quantity'] = quantity
                self._save()

    def remove(self, product_id):
        product_id = str(product_id)
        if product_id in self.cart:
            del self.cart[product_id]
            self._save()

    def clear(self):
        self.session[CART_SESSION_KEY] = {}
        self._save()

    def __iter__(self):
        """Yield each cart line with the live Product object and computed totals attached."""
        product_ids = self.cart.keys()
        products = Product.objects.filter(id__in=product_ids)
        products_by_id = {str(p.id): p for p in products}

        for product_id, item in self.cart.items():
            product = products_by_id.get(product_id)
            if product is None:
                continue  # product was deleted after being added to someone's cart
            unit_price = product.price
            quantity = item['quantity']
            yield {
                'product': product,
                'quantity': quantity,
                'unit_price': unit_price,
                'subtotal': unit_price * quantity,
            }

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self):
        total = Decimal('0.00')
        for line in self:
            total += line['subtotal']
        return total

    def is_empty(self):
        return len(self.cart) == 0
