@echo off
echo.
echo 🍞  ToasterPants Local Setup (Windows)
echo ========================================
python --version >nul 2>&1 || (echo Python not found & exit /b)
if not exist "venv\" ( python -m venv venv )
call venv\Scripts\activate.bat
pip install -q --upgrade pip
pip install -q "Django>=4.2,<5.0" djangorestframework djangorestframework-simplejwt django-cors-headers whitenoise argon2-cffi Pillow requests django-celery-beat django-celery-results celery
echo Generating migrations...
python manage.py makemigrations accounts vendors listings auctions orders messaging filemanager
echo Applying migrations...
python manage.py migrate
echo Seeding data...
python manage.py setup_toasterpants
python manage.py collectstatic --noinput --verbosity 0
echo.
echo Done! superadmin / password configured via DJANGO_SUPERUSER_PASSWORD
echo http://localhost:8000
python manage.py runserver
