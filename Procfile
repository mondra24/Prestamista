release: python manage.py migrate && python manage.py create_superuser_if_not_exists && python manage.py load_sample_data
web: python manage.py collectstatic --noinput && gunicorn prestamos_config.wsgi
