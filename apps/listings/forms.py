from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from decimal import Decimal
from .models import Listing, ListingFile, ListingCategory

CURRENCY_CHOICES = [
    ('USDT_TRC20', 'USDT (TRC20)'),
    ('BTC',         'Bitcoin (BTC)'),
    ('LTC',         'Litecoin (LTC)'),
    ('ADA',         'Cardano (ADA)'),
    ('ETH',         'Ethereum (ETH)'),
    ('XMR',         'Monero (XMR)'),
]

INPUT    = 'w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-2.5 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-toast-500'
SELECT   = 'w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-2.5 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-toast-500'
TEXTAREA = 'w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-2.5 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-toast-500 resize-none'
CHECK    = 'w-4 h-4 rounded border-gray-600 bg-gray-700 text-toast-500 focus:ring-toast-500'


class ListingForm(forms.ModelForm):
    external_links_text = forms.CharField(
        label='External Links',
        required=False,
        widget=forms.Textarea(attrs={
            'class': TEXTAREA, 'rows': 3,
            'placeholder': 'One URL per line (for files over 20MB)',
        })
    )

    class Meta:
        model = Listing
        fields = [
            'title', 'description', 'listing_type', 'price_type',
            'price_usd', 'quantity', 'category', 'thumbnail',
            'condition', 'tags', 'expiration',
            'requires_shipping', 'shipping_fee_usd', 'ships_from',
            'ships_worldwide', 'estimated_delivery',
            'resell_allowed', 'max_resell_per_day',
            'delivery_instructions', 'auto_delivery',
        ]
        widgets = {
            'title':                forms.TextInput(attrs={'class': INPUT, 'placeholder': 'Listing title'}),
            'description':          forms.Textarea(attrs={'class': TEXTAREA, 'rows': 6}),
            'listing_type':         forms.Select(attrs={'class': SELECT}),
            'price_type':           forms.Select(attrs={'class': SELECT}),
            'price_usd':            forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0.01', 'placeholder': 'Price in USD (shown as TP Coins to buyers)'}),
            'quantity':             forms.NumberInput(attrs={'class': INPUT, 'min': '0', 'placeholder': '1'}),
            'category':             forms.Select(attrs={'class': SELECT}),
            'condition':            forms.Select(attrs={'class': SELECT}),
            'tags':                 forms.TextInput(attrs={'class': INPUT, 'placeholder': 'tag1, tag2, tag3'}),
            'expiration':           forms.DateTimeInput(attrs={'class': INPUT, 'type': 'datetime-local'}),
            'shipping_fee_usd':     forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'ships_from':           forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. United States'}),
            'estimated_delivery':   forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. 5-10 business days'}),
            'max_resell_per_day':   forms.NumberInput(attrs={'class': INPUT, 'min': '1'}),
            'delivery_instructions':forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
            'requires_shipping':    forms.CheckboxInput(attrs={'class': CHECK}),
            'ships_worldwide':      forms.CheckboxInput(attrs={'class': CHECK}),
            'resell_allowed':       forms.CheckboxInput(attrs={'class': CHECK}),
            'auto_delivery':        forms.CheckboxInput(attrs={'class': CHECK}),
        }

    def __init__(self, *args, vendor=None, **kwargs):
        super().__init__(*args, **kwargs)

        if vendor is not None:
            self.fields['category'].queryset = ListingCategory.objects.filter(
                is_active=True
            ).filter(
                models.Q(vendor__isnull=True) | models.Q(vendor=vendor)
            ).order_by('sort_order', 'name')

        optional = [
            'category', 'thumbnail', 'tags', 'expiration', 'condition',
            'requires_shipping', 'ships_worldwide', 'shipping_fee_usd',
            'ships_from', 'estimated_delivery', 'resell_allowed',
            'max_resell_per_day', 'delivery_instructions', 'auto_delivery',
            'external_links_text', 'quantity',
        ]
        for f in optional:
            if f in self.fields:
                self.fields[f].required = False

        self.fields['title'].required = True
        self.fields['description'].required = True
        self.fields['price_usd'].required = True
        self.fields['listing_type'].required = True
        self.fields['price_type'].required = True

        # Pre-populate external links
        if self.instance and self.instance.pk and self.instance.external_links:
            links = self.instance.external_links
            if isinstance(links, list):
                self.fields['external_links_text'].initial = '\n'.join(str(l) for l in links)

    def clean_price_usd(self):
        price = self.cleaned_data.get('price_usd')
        if price is not None and price <= 0:
            raise ValidationError("Price must be greater than zero.")
        return price

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        return qty if qty is not None else 1

    def clean_max_resell_per_day(self):
        val = self.cleaned_data.get('max_resell_per_day')
        return val if val is not None else 1

    def clean_external_links_text(self):
        text = self.cleaned_data.get('external_links_text', '').strip()
        if not text:
            return []
        links = [l.strip() for l in text.splitlines() if l.strip()]
        for link in links:
            if not (link.startswith('http://') or link.startswith('https://')):
                raise ValidationError(f"Invalid URL: '{link}'")
        return links

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.external_links = self.cleaned_data.get('external_links_text', [])
        if commit:
            instance.save()
        return instance


class ListingFileForm(forms.ModelForm):
    class Meta:
        model = ListingFile
        fields = ['file', 'is_public']
