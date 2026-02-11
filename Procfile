web: python manage.py collectstatic --noinput && python manage.py migrate && python manage.py create_superuser_if_not_exists && python manage.py load_sample_data && gunicorn prestamos_config.wsgi
