#!/usr/bin/env bash
# ToasterPants — Fix Migrations Script
# Run this from inside your toasterpants/ directory
# ================================================

echo "🍞 Fixing ToasterPants migrations..."
echo ""

# Step 1: Remove the bad hand-written migration files
echo "→ Removing old migration files..."
find apps/ -path "*/migrations/0001_initial.py" -delete 2>/dev/null
find apps/ -path "*/migrations/0002_*.py" -delete 2>/dev/null
echo "  Done."

# Step 2: Remove old database (it has the wrong schema from before)
if [ -f "db.sqlite3" ]; then
    echo "→ Removing old database..."
    rm db.sqlite3
    echo "  Done."
fi

# Step 3: Generate fresh migrations from the actual models
echo "→ Running makemigrations..."
python manage.py makemigrations accounts
python manage.py makemigrations vendors
python manage.py makemigrations listings
python manage.py makemigrations auctions
python manage.py makemigrations orders
python manage.py makemigrations messaging
python manage.py makemigrations filemanager
echo "  Done."

# Step 4: Apply all migrations
echo "→ Running migrate..."
python manage.py migrate
echo "  Done."

# Step 5: Re-run setup
echo "→ Running setup_toasterpants..."
python manage.py setup_toasterpants
echo ""
echo "✅ All done! Run: python manage.py runserver"
