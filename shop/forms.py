from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Order


class SignUpForm(UserCreationForm):
    """Extends Django's built-in UserCreationForm to also collect an email.
    Django's default version only asks for username + password."""

    email = forms.EmailField(required=True, help_text="Used for order confirmations.")

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class CheckoutForm(forms.ModelForm):
    """Shipping details collected at checkout. Deliberately minimal for v1 —
    no payment fields, since we're not integrating a real payment gateway yet."""

    class Meta:
        model = Order
        fields = ['full_name', 'shipping_address', 'phone_number']
        widgets = {
            'shipping_address': forms.Textarea(attrs={'rows': 3}),
        }
