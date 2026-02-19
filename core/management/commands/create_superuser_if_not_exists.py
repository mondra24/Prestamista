"""
Comando para crear superusuario automáticamente si no existe.
Usa variables de entorno DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os


class Command(BaseCommand):
    help = 'Crea un superusuario si no existe, usando variables de entorno'

    def handle(self, *args, **options):
        User = get_user_model()
        
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        
        self.stdout.write(f'[DEBUG] Username: "{username}", Password length: {len(password) if password else 0}')
        
        if not password:
            self.stdout.write(self.style.WARNING(
                'DJANGO_SUPERUSER_PASSWORD no está configurada. Saltando creación de superusuario.'
            ))
            return
        
        if User.objects.filter(username=username).exists():
            # Forzar actualización de contraseña por si cambió
            user = User.objects.get(username=username)
            user.set_password(password)
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.save()
            # Verificar que la contraseña se guardó bien
            user.refresh_from_db()
            check = user.check_password(password)
            self.stdout.write(self.style.SUCCESS(
                f'Superusuario "{username}" actualizado. Password check: {check}, is_active: {user.is_active}'
            ))
        else:
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            check = user.check_password(password)
            self.stdout.write(self.style.SUCCESS(
                f'Superusuario "{username}" creado. Password check: {check}, is_active: {user.is_active}'
            ))
