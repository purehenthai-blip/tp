from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import User, SiteConfig


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput())
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput())
    agree_terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must agree to the Terms of Service.'}
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'display_name']

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise ValidationError("Username is required.")
        if len(username) < 3:
            raise ValidationError("Username must be at least 3 characters.")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("That username is already taken.")
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with that email already exists.")
        return email if email else None

    def clean(self):
        cd = super().clean()
        p1, p2 = cd.get('password1', ''), cd.get('password2', '')
        if p1 and len(p1) < 8:
            self.add_error('password1', "Password must be at least 8 characters.")
        if p1 and p2 and p1 != p2:
            self.add_error('password2', "Passwords do not match.")
        return cd

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.display_name = (self.cleaned_data.get('display_name') or '').strip() or user.username
        user.language = 'en'
        user.theme = 'dark'
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'placeholder': 'Username', 'autocomplete': 'username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password', 'autocomplete': 'current-password'})
    )


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['display_name', 'email', 'language', 'theme', 'pgp_key']
        widgets = {
            'display_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'pgp_key': forms.Textarea(attrs={'class': 'form-input', 'rows': 6}),
        }


class CryptoAddressForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'btc_address', 'usdt_trc20_address', 'ltc_address',
            'ada_address', 'eth_address', 'xmr_address',
            'withdrawal_address', 'withdrawal_currency',
        ]


class AdminUserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            'username', 'email', 'display_name', 'role',
            'coin_balance', 'purchase_total', 'is_active',
            'is_banned', 'verified_vendor', 'language', 'theme',
            'btc_address', 'usdt_trc20_address', 'ltc_address',
            'ada_address', 'eth_address', 'xmr_address',
            'withdrawal_address', 'withdrawal_currency',
        ]
        widgets = {
            'coin_balance':   forms.NumberInput(attrs={'class': 'form-input', 'step': '0.00000001'}),
            'purchase_total': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
        }


class SiteConfigForm(forms.Form):
    param_name  = forms.CharField()
    value       = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))
    description = forms.CharField(required=False)
