from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list_view, name='product_list'),
    path('signup/', views.signup_view, name='signup'),
    path('perfume/<slug:slug>/', views.product_detail_view, name='product_detail'),

    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<slug:slug>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:product_id>/', views.cart_remove, name='cart_remove'),

    path('checkout/', views.checkout, name='checkout'),
    path('payment/<int:order_id>/', views.payment_initiate, name='payment_initiate'),
    path('payment/<int:order_id>/simulate/', views.payment_simulate, name='payment_simulate'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('payment/webhook/', views.paystack_webhook, name='paystack_webhook'),

    path('orders/', views.order_history, name='order_history'),
    path('orders/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
]
