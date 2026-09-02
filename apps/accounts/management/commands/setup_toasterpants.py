"""
ToasterPants — Initial Setup Management Command
"""

from django.core.management.base import BaseCommand
from django.db import transaction
import os


class Command(BaseCommand):
    help = "Initial ToasterPants platform setup"

    def add_arguments(self, parser):
        parser.add_argument("--username", default="superadmin")
        parser.add_argument("--password", default=None)
        parser.add_argument("--email", default="")
        parser.add_argument("--no-categories", action="store_true")

    def handle(self, *args, **options):
        self.stdout.write(
            "\nToasterPants Initial Setup\n" + "=" * 40
        )

        with transaction.atomic():
            self._create_superadmin(options)
            self._seed_site_config()

            if not options["no_categories"]:
                self._seed_categories()

            self._init_platform_wallet()
            self._create_storage_quota_for_existing_users()

        self.stdout.write(
            "\nSetup complete! Your ToasterPants platform is ready.\n"
        )
        self.stdout.write(
            "   Run: python manage.py runserver\n"
        )
        self.stdout.write(
            "   Admin panel: http://localhost:8000/admin-panel/\n"
        )

    def _create_superadmin(self, options):
        from apps.accounts.models import User

        username = options["username"]
        password = (
            options["password"]
            or os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        )
        email = options.get("email") or None

        if not password:
            raise ValueError(
                "DJANGO_SUPERUSER_PASSWORD environment variable is required"
            )

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                f'  User "{username}" already exists — skipping.'
            )
            return

        User.objects.create_superuser(
            username=username,
            password=password,
            email=email,
        )

        self.stdout.write(
            f"  Super admin created: {username}"
        )

    def _seed_site_config(self):
        from apps.accounts.models import SiteConfig

        defaults = {
            "SITE_NAME": "ToasterPants",
            "SITE_TAGLINE": "The Anonymous Crypto Marketplace",
            "COMMISSION_RATE": "0.08",
            "BUYER_TX_FEE_RATE": "0.02",
            "PHYSICAL_BROKERAGE_RATE": "0.02",
            "RESELLER_UNLOCK_THRESHOLD": "100.00",
            "RESELLER_DAILY_LIMIT": "1",
            "ESCROW_AUTO_RELEASE_DAYS": "14",
            "INACTIVE_ACCOUNT_DELETE_DAYS": "14",
            "INACTIVE_ACCOUNT_MIN_BALANCE": "15.00",
            "VENDOR_APPLICATION_FEE": "10.00",
            "LISTING_FEE": "1.00",
            "MIN_DEPOSIT_COINS": "1",
            "MIN_WITHDRAWAL_COINS": "1",
            "MIN_LISTING_PRICE_USD": "0.01",
            "TP_COIN_VALUE_USD": "10.00",
            "AUCTION_ANTI_SNIPE_MINUTES": "10",
            "AUCTION_EXTENSION_MINUTES": "10",
            "AUCTION_MAX_EXTENSIONS": "5",
            "MAX_FILE_SIZE_MB": "20",
            "MAX_USER_STORAGE_MB": "100",
            "DEFAULT_THEME": "dark",
            "MAINTENANCE_MODE": "false",
            "SITE_ANNOUNCEMENT": "",
            "TRANSLATION_API_URL": "",
            "TRANSLATION_API_KEY": "",
            "SUPPORTED_CRYPTOS": "USDT_TRC20,BTC,LTC,ADA,ETH,XMR",
        }

        created = 0

        for key, value in defaults.items():
            _, was_created = SiteConfig.objects.get_or_create(
                param_name=key,
                defaults={"value": value},
            )

            if was_created:
                created += 1

        self.stdout.write(
            f"  Site config: {created} defaults seeded"
        )

    def _seed_categories(self):
        from apps.listings.models import ListingCategory

        categories = [
            {
                "name": "Digital Goods",
                "slug": "digital-goods",
                "icon": "hard-drive",
                "children": [
                    {
                        "name": "Software",
                        "slug": "software",
                        "icon": "cpu",
                    },
                    {
                        "name": "E-books",
                        "slug": "ebooks",
                        "icon": "book-open",
                    },
                    {
                        "name": "Templates",
                        "slug": "templates",
                        "icon": "layout",
                    },
                    {
                        "name": "Graphics",
                        "slug": "graphics",
                        "icon": "image",
                    },
                    {
                        "name": "Courses",
                        "slug": "courses",
                        "icon": "graduation-cap",
                    },
                ],
            },
            {
                "name": "Physical Goods",
                "slug": "physical-goods",
                "icon": "package",
                "children": [
                    {
                        "name": "Electronics",
                        "slug": "electronics",
                        "icon": "zap",
                    },
                    {
                        "name": "Clothing",
                        "slug": "clothing",
                        "icon": "tag",
                    },
                    {
                        "name": "Collectibles",
                        "slug": "collectibles",
                        "icon": "star",
                    },
                ],
            },
            {
                "name": "Services",
                "slug": "services",
                "icon": "tool",
                "children": [
                    {
                        "name": "Development",
                        "slug": "development",
                        "icon": "code",
                    },
                    {
                        "name": "Design",
                        "slug": "design",
                        "icon": "pen-tool",
                    },
                    {
                        "name": "Consulting",
                        "slug": "consulting",
                        "icon": "briefcase",
                    },
                ],
            },
            {
                "name": "Data & Research",
                "slug": "data-research",
                "icon": "bar-chart-2",
            },
            {
                "name": "Access & Accounts",
                "slug": "access-accounts",
                "icon": "key",
            },
            {
                "name": "Other",
                "slug": "other",
                "icon": "more-horizontal",
            },
        ]

        created = 0

        for i, cat_data in enumerate(categories):
            children = cat_data.pop("children", [])

            cat, was_created = ListingCategory.objects.get_or_create(
                slug=cat_data["slug"],
                defaults={
                    **cat_data,
                    "sort_order": i,
                },
            )

            if was_created:
                created += 1

            for j, child_data in enumerate(children):
                _, child_created = ListingCategory.objects.get_or_create(
                    slug=child_data["slug"],
                    defaults={
                        **child_data,
                        "parent": cat,
                        "sort_order": j,
                    },
                )

                if child_created:
                    created += 1

        self.stdout.write(
            f"  Categories: {created} created"
        )

    def _init_platform_wallet(self):
        from apps.accounts.models import PlatformWallet

        PlatformWallet.get_or_create_main()

        self.stdout.write(
            "  Platform wallet initialized"
        )

    def _create_storage_quota_for_existing_users(self):
        from apps.accounts.models import User
        from apps.filemanager.models import UserStorageQuota

        users_without = User.objects.filter(
            storage_quota__isnull=True
        )

        count = 0

        for user in users_without:
            UserStorageQuota.objects.get_or_create(
                user=user
            )
            count += 1

        if count:
            self.stdout.write(
                f"  Storage quotas: {count} created"
            )
