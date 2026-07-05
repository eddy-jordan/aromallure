from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from .forms import SignUpForm, CheckoutForm
from .models import Product, Order, OrderItem
from .cart import Cart
from .emails import send_order_confirmation_email


def signup_view(request):
    """Customer signup — separate system from the admin login.
    On success, logs the new user in immediately and sends them home."""
    if request.user.is_authenticated:
        return redirect('product_list')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account has been created.")
            return redirect('product_list')
    else:
        form = SignUpForm()

    return render(request, 'registration/signup.html', {'form': form})


def product_list_view(request):
    """Product catalog with search and pagination — 12 products per page."""
    from django.core.paginator import Paginator
    from django.db.models import Q

    query    = request.GET.get('q', '').strip()
    products_qs = Product.objects.filter(is_active=True)

    if query:
        products_qs = products_qs.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(scent_notes__icontains=query) |
            Q(description__icontains=query)
        )

    paginator   = Paginator(products_qs, 12)
    page_number = request.GET.get('page', 1)
    products    = paginator.get_page(page_number)

    return render(request, 'shop/product_list.html', {
        'products': products,
        'is_home':  not query,  # only show entrance animation when not searching
        'query':    query,
    })


def product_detail_view(request, slug):
    """A single perfume's full detail page. 404s for inactive/missing products
    rather than leaking that a hidden product's slug exists."""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    # Related: other active products from the same brand, or if none,
    # any other active products — capped at 3 so the grid stays clean
    related = (
        Product.objects
        .filter(is_active=True)
        .exclude(pk=product.pk)
        .order_by('?')[:3]
    )
    return render(request, 'shop/product_detail.html', {
        'product': product,
        'related': related,
    })


# ════════════════════════════════════════════════════════════
# PHASE 4 — Cart & Checkout
# ════════════════════════════════════════════════════════════

@require_POST
def add_to_cart(request, slug):
    """Anyone can add to cart, even anonymous visitors — the cart lives in
    their session. Login is only required later, at checkout."""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    cart = Cart(request)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except ValueError:
        quantity = 1
    quantity = max(1, quantity)

    if not product.in_stock:
        messages.error(request, f"Sorry, {product.name} is currently sold out.")
        return redirect('product_detail', slug=product.slug)

    # Cap at available stock so the cart can never hold more than exists
    current_qty_in_cart = cart.cart.get(str(product.id), {}).get('quantity', 0)
    allowed_to_add = max(0, product.stock - current_qty_in_cart)
    quantity_to_add = min(quantity, allowed_to_add)

    if quantity_to_add == 0:
        messages.warning(request, f"You already have all {product.stock} available units of {product.name} in your cart.")
    else:
        cart.add(product, quantity_to_add)
        messages.success(request, f"Added {quantity_to_add} x {product.name} to your cart.")
        if quantity_to_add < quantity:
            messages.warning(request, f"Only {product.stock} units of {product.name} are in stock — added the maximum available.")

    return redirect('cart_detail')


def cart_detail(request):
    cart = Cart(request)
    return render(request, 'shop/cart_detail.html', {'cart': cart})


@require_POST
def cart_update(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    try:
        quantity = int(request.POST.get('quantity', 1))
    except ValueError:
        quantity = 1

    quantity = min(quantity, product.stock) if quantity > 0 else quantity
    cart.update(product_id, quantity)
    return redirect('cart_detail')


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    cart.remove(product_id)
    return redirect('cart_detail')


@login_required
def checkout(request):
    cart = Cart(request)

    if cart.is_empty():
        messages.info(request, "Your cart is empty — add something from the collection first.")
        return redirect('product_list')

    # Re-validate stock at checkout time
    stock_issues = []
    for line in cart:
        if line['quantity'] > line['product'].stock:
            stock_issues.append(
                f"Only {line['product'].stock} of {line['product'].name} left "
                f"(you have {line['quantity']} in your cart)"
            )
    if stock_issues:
        for issue in stock_issues:
            messages.error(request, issue)
        return redirect('cart_detail')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                order.user   = request.user
                order.status = 'PENDING'
                order.save()

                for line in cart:
                    # Lock the product row so no other transaction can
                    # modify stock until this transaction completes.
                    # This prevents two customers from buying the last
                    # item simultaneously (race condition).
                    try:
                        product = Product.objects.select_for_update().get(
                            pk=line['product'].pk, is_active=True
                        )
                    except Product.DoesNotExist:
                        order.delete()
                        messages.error(request, f"{line['product'].name} is no longer available.")
                        return redirect('cart_detail')

                    if product.stock < line['quantity']:
                        order.delete()
                        messages.error(
                            request,
                            f"Sorry — only {product.stock} of {product.name} "
                            f"left. Please update your cart."
                        )
                        return redirect('cart_detail')

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        product_name=product.name,
                        quantity=line['quantity'],
                        unit_price=product.price,
                    )
                    product.stock -= line['quantity']
                    product.save(update_fields=['stock'])

                order.recalculate_total()
                request.session['pending_order_id'] = order.id

            # Clear the cart immediately after the order is placed —
            # for manual MoMo, payment happens offline so we can't
            # wait for a webhook to clear it.
            cart.clear()

            return redirect('payment_initiate', order_id=order.id)
    else:
        initial = {'full_name': request.user.get_full_name() or request.user.username}
        form = CheckoutForm(initial=initial)

    return render(request, 'shop/checkout.html', {'form': form, 'cart': cart})


@login_required
def payment_initiate(request, order_id):
    """Shows the payment page with Paystack's inline popup.
    In test/simulation mode (no PAYSTACK_PUBLIC_KEY set), shows a
    simulated payment button so the full flow can be tested locally."""
    import os
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status == 'PAID':
        return redirect('order_confirmation', order_id=order.id)

    paystack_public_key = os.environ.get('PAYSTACK_PUBLIC_KEY', '')
    # Amount in pesewas (Ghana cedis × 100) — adjust currency when you
    # configure Paystack for GHS in the dashboard
    amount_pesewas = int(order.total_price * 100)

    from django.conf import settings as django_settings
    context = {
        'order': order,
        'paystack_public_key': paystack_public_key,
        'amount_pesewas': amount_pesewas,
        'user_email': request.user.email,
        'simulation_mode': not paystack_public_key,
        'momo_number':  django_settings.MOMO_NUMBER,
        'momo_name':    django_settings.MOMO_NAME,
        'momo_network': django_settings.MOMO_NETWORK,
    }
    return render(request, 'shop/payment.html', context)


@login_required
def payment_simulate(request, order_id):
    """Simulates a successful payment locally — only active when
    PAYSTACK_PUBLIC_KEY is not set. Allows full flow testing before
    the Paystack account is ready."""
    import os
    if os.environ.get('PAYSTACK_PUBLIC_KEY'):
        # Real keys are set — simulation shouldn't be accessible
        return redirect('payment_initiate', order_id=order_id)

    order = get_object_or_404(Order, id=order_id, user=request.user)
    order.status = 'PAID'
    order.payment_reference = f'SIMULATED-{order.id}'
    order.save(update_fields=['status', 'payment_reference'])

    cart = Cart(request)
    cart.clear()

    try:
        send_order_confirmation_email(order)
    except Exception:
        pass

    messages.success(request, f"[TEST MODE] Payment simulated for Order #{order.id}.")
    return redirect('order_confirmation', order_id=order.id)


import json
import hmac
import hashlib
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse


@csrf_exempt
def paystack_webhook(request):
    """Receives Paystack's server-to-server webhook after a successful
    payment. This is the authoritative source of payment confirmation —
    we never trust the browser's return URL alone.

    Security: Paystack signs every webhook with your secret key.
    We verify the signature before doing anything with the payload."""
    import os

    if request.method != 'POST':
        return HttpResponse(status=405)

    paystack_secret = os.environ.get('PAYSTACK_SECRET_KEY', '')
    if not paystack_secret:
        # No secret key configured — skip in test/simulation mode
        return HttpResponse(status=200)

    # Verify the webhook signature
    signature = request.headers.get('X-Paystack-Signature', '')
    expected = hmac.new(
        paystack_secret.encode('utf-8'),
        msg=request.body,
        digestmod=hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        return HttpResponse(status=400)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event = payload.get('event')
    data  = payload.get('data', {})

    if event == 'charge.success':
        reference = data.get('reference', '')
        # Find the order by its payment reference stored during initiation
        try:
            order = Order.objects.get(payment_reference=reference, status='PENDING')
            order.status = 'PAID'
            order.save(update_fields=['status'])
            try:
                send_order_confirmation_email(order)
            except Exception:
                pass
        except Order.DoesNotExist:
            pass  # Already paid or reference not found — safe to ignore

    return HttpResponse(status=200)


@login_required
def payment_callback(request):
    """Handles Paystack's redirect back to our site after the customer
    completes payment on Paystack's hosted page. We don't trust this
    URL alone for payment confirmation — the webhook above is the
    authoritative source. This view just shows the right page."""
    import os
    reference = request.GET.get('reference', '')
    trxref    = request.GET.get('trxref', reference)

    if reference:
        try:
            order = Order.objects.get(
                payment_reference=reference,
                user=request.user
            )
            if order.status == 'PAID':
                cart = Cart(request)
                cart.clear()
                messages.success(request, f"Payment confirmed! Order #{order.id} is now paid.")
                return redirect('order_confirmation', order_id=order.id)
            else:
                # Webhook may not have arrived yet — show pending page
                messages.info(
                    request,
                    f"Payment received. Your order #{order.id} is being confirmed — "
                    f"please check back shortly."
                )
                return redirect('order_confirmation', order_id=order.id)
        except Order.DoesNotExist:
            pass

    messages.error(request, "We couldn't verify your payment. Please contact us if money was deducted.")
    return redirect('order_history')


@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'shop/order_confirmation.html', {'order': order})


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, 'shop/order_history.html', {'orders': orders})
