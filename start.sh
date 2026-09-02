#!/usr/bin/env bash
# ============================================================
# ToasterPants — Local Setup Script 🍞
# ============================================================
set -e
echo ""
echo "🍞  ToasterPants Local Setup"
echo "================================"

python3 --version || { echo "❌ Python 3 not found."; exit 1; }

if [ ! -d "venv" ]; then
  echo "→ Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

echo "→ Installing dependencies..."
pip install -q --upgrade pip
pip install -q \
  "Django>=4.2,<5.0" \
  djangorestframework \
  djangorestframework-simplejwt \
  django-cors-headers \
  whitenoise \
  argon2-cffi \
  Pillow \
  requests \
  django-celery-beat \
  django-celery-results \
  celery

echo "→ Generating migrations from models..."
python manage.py makemigrations accounts vendors listings auctions orders messaging filemanager

echo "→ Applying migrations..."
python manage.py migrate

echo "→ Seeding platform data..."
python manage.py setup_toasterpants

echo "→ Collecting static files..."
python manage.py collectstatic --noinput --verbosity 0

echo ""
echo "✅  Setup complete!"
echo "   superadmin / password configured via DJANGO_SUPERUSER_PASSWORD"
echo "   http://localhost:8000"
echo "   http://localhost:8000/admin-panel/"
echo ""
python manage.py runserver
