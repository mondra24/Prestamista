web: python manage.py flush --no-input && python manage.py migrate && python manage.py create_superuser_if_not_exists && python manage.py collectstatic --noinput && gunicorn prestamos_config.wsgi
