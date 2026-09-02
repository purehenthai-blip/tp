"""
ToasterPants API Serializers
==============================
Converting models to JSON and back.
Anonymous-aware: no real identities leak through the API. TP
"""

from rest_framework import serializers
from apps.accounts.models import User
from apps.listings.models import Listing, ListingCategory
from apps.auctions.models import Auction, Bid
from apps.orders.models import Order, Escrow, WalletTransaction
from apps.messaging.models import MessageThread, Message
from apps.reviews.models import Review
from apps.support.models import Ticket


class AnonymousUserSerializer(serializers.ModelSerializer):
    """
    Safe user serializer — never exposes real identity.
    display field only. No email, no real name.
    """
    display = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['display', 'role']


class UserProfileSerializer(serializers.ModelSerializer):
    """For user viewing their own profile."""
    display = serializers.CharField(read_only=True)
    is_reseller_eligible = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'display', 'email', 'role', 'language', 'theme',
            'wallet_balance', 'escrow_balance', 'purchase_total',
            'is_reseller_eligible', 'verified_vendor', 'created_at',
            'btc_address', 'usdt_trc20_address', 'ltc_address',
            'ada_address', 'eth_address', 'xmr_address',
        ]
        read_only_fields = ['role', 'wallet_balance', 'escrow_balance', 'purchase_total', 'verified_vendor']


class ListingCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingCategory
        fields = ['id', 'name', 'slug', 'icon']


class ListingSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.shop_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_available = serializers.BooleanField(read_only=True)
    stock_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id', 'vendor_name', 'category_name', 'listing_type', 'price_type',
            'title', 'description', 'tags', 'price', 'currency',
            'quantity', 'quantity_sold', 'stock_remaining', 'status',
            'expiration', 'is_available', 'resell_allowed',
            'max_resell_per_day', 'external_links', 'avg_rating',
            'review_count', 'view_count', 'thumbnail',
            'delivery_instructions', 'auto_delivery',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['quantity_sold', 'avg_rating', 'review_count', 'view_count', 'status']

    def get_stock_remaining(self, obj):
        return str(obj.stock_remaining)


class AuctionStatusSerializer(serializers.ModelSerializer):
    minimum_next_bid = serializers.DecimalField(max_digits=18, decimal_places=8, read_only=True)
    seconds_remaining = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    winner = AnonymousUserSerializer(read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)

    class Meta:
        model = Auction
        fields = [
            'id', 'listing_title', 'start_price', 'reserve_price', 'current_bid',
            'minimum_next_bid', 'buyout_price', 'start_time', 'end_time',
            'original_end_time', 'extension_count', 'total_extension_minutes',
            'anti_sniping', 'snipe_window_minutes', 'extension_minutes',
            'max_extensions', 'status', 'is_active', 'seconds_remaining', 'winner',
        ]


class BidSerializer(serializers.ModelSerializer):
    bidder = AnonymousUserSerializer(read_only=True)

    class Meta:
        model = Bid
        fields = ['id', 'bid_amount', 'bidder', 'is_winning', 'triggered_extension', 'timestamp']
        read_only_fields = ['is_winning', 'triggered_extension']


class OrderSerializer(serializers.ModelSerializer):
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    vendor_name = serializers.CharField(source='vendor.shop_name', read_only=True)
    # Never expose buyer identity to vendor
    buyer_display = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'buyer_display', 'vendor_name', 'listing_title',
            'unit_price', 'quantity', 'subtotal', 'commission', 'total_amount',
            'currency', 'status', 'is_resale', 'buyer_note',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['order_number', 'commission', 'status']

    def get_buyer_display(self, obj):
        """Never reveal real buyer identity."""
        if obj.buyer:
            return obj.buyer.display
        return "Anonymous"


class MessageSerializer(serializers.ModelSerializer):
    sender_display = serializers.CharField(source='sender.display', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'content', 'sender_display', 'is_read', 'timestamp']
        read_only_fields = ['sender_display', 'is_read']


class ReviewSerializer(serializers.ModelSerializer):
    buyer_display = serializers.CharField(source='buyer.display', read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'listing_title', 'buyer_display', 'rating', 'title',
            'comment', 'verified_purchase', 'vendor_reply', 'created_at',
        ]
        read_only_fields = ['buyer_display', 'verified_purchase', 'vendor_reply']


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_number', 'subject', 'category', 'status',
            'priority', 'created_at', 'updated_at',
        ]
        read_only_fields = ['ticket_number', 'status']


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'transaction_type', 'amount', 'currency',
            'balance_after', 'description', 'tx_hash', 'timestamp',
        ]
        read_only_fields = ['balance_after']
