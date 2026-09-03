from django import forms
from django.db.models import Q

from apps.listings.models import ListingCategory


class VendorCategoryForm(forms.ModelForm):
    class Meta:
        model = ListingCategory
        fields = [
            'name',
            'slug',
            'parent',
            'icon',
            'is_active',
            'sort_order',
            'max_listings_per_vendor',
            'min_price_usd',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-2.5 text-gray-100'}),
            'slug': forms.TextInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-2.5 text-gray-100'}),
            'parent': forms.Select(attrs={'class': 'w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-2.5 text-gray-100'}),
            'icon': forms.TextInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-2.5 text-gray-100'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-4 h-4 rounded border-gray-600 bg-gray-700'}),
            'sort_order': forms.NumberInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-2.5 text-gray-100'}),
            'max_listings_per_vendor': forms.NumberInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-2.5 text-gray-100'}),
            'min_price_usd': forms.NumberInput(attrs={'class': 'w-full bg-gray-700 border border-gray-600 rounded-xl px-4 py-2.5 text-gray-100', 'step': '0.01'}),
        }

    def __init__(self, *args, vendor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vendor = vendor

        if vendor is not None:
            self.fields['parent'].queryset = ListingCategory.objects.filter(
                is_active=True
            ).filter(
                Q(vendor__isnull=True) | Q(vendor=vendor)
            ).order_by('sort_order', 'name')
