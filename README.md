# ToasterPants — Anonymous Crypto Marketplace

A production-ready, multi-vendor, crypto-first marketplace built with Django.

## Tech Stack
- **Backend:** Django 4.2, Django REST Framework, JWT Auth
- **Database:** SQLite (dev) / PostgreSQL (production)
- **Passwords:** Argon2 hashing
- **Static Files:** WhiteNoise
- **Background Tasks:** Celery + Redis (optional)
- **Currency:** TP Coins (1 coin = $10 USD)

## Quick Start (Development)

```bash
# 1. Unzip and enter
unzip toasterpants.zip && cd toasterpants

# 2. Create virtual environment
python3 -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations
python manage.py makemigrations accounts vendors listings auctions orders messaging filemanager
python manage.py migrate

# 5. Seed platform data
python manage.py setup_toasterpants

# 6. Start server
python manage.py runserver
```

**Default superadmin:** `superadmin` / password configured via `DJANGO_SUPERUSER_PASSWORD`

## Production Deployment (PostgreSQL)

```bash
# 1. Set environment variables (copy .env.example to .env)
export DJANGO_DEBUG=False
export DJANGO_SECRET_KEY=your-secret-key-here
export DJANGO_ALLOWED_HOSTS=yourdomain.com
export DB_ENGINE=django.db.backends.postgresql
export DB_NAME=toasterpants
export DB_USER=postgres
export DB_PASSWORD=your-db-password
export DB_HOST=localhost

# 2. Install production dependencies
pip install -r requirements.txt psycopg2-binary

# 3. Run migrations
python manage.py migrate

# 4. Seed platform
python manage.py setup_toasterpants

# 5. Collect static files
python manage.py collectstatic --noinput

# 6. Run with Gunicorn
pip install gunicorn
gunicorn toasterpants.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

## Switching from SQLite to PostgreSQL

1. Create a PostgreSQL database:
```sql
CREATE DATABASE toasterpants;
CREATE USER toasterpants_user WITH PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE toasterpants TO toasterpants_user;
```

2. Set env vars:
```bash
export DB_ENGINE=django.db.backends.postgresql
export DB_NAME=toasterpants
export DB_USER=toasterpants_user
export DB_PASSWORD=yourpassword
```

3. Run migrations on the new database:
```bash
python manage.py migrate
python manage.py setup_toasterpants
```

## Key Platform URLs

| URL | Description |
|-----|-------------|
| `/` | Marketplace homepage |
| `/accounts/register/` | User registration |
| `/accounts/login/` | Login |
| `/listings/` | Browse listings |
| `/wallet/` | TP Coin wallet |
| `/leaderboard/` | Vendor & buyer rankings |
| `/vendors/apply/` | Become a vendor |
| `/admin-panel/` | Admin dashboard |
| `/api/v1/docs/` | REST API documentation |

## TP Coin System
- 1 TP Coin = $10 USD
- Vendors set prices in USD, displayed as TP Coins to buyers
- 8% commission deducted from vendor payout (NOT from buyer)
- 2% buyer transaction fee on every purchase
- 2% brokerage fee on physical product purchases (paid by buyer)

## Admin Login
`http://localhost:8000/admin-panel/`  
Default: `superadmin` / password configured via `DJANGO_SUPERUSER_PASSWORD`
