"""
Job programado (Railway Cron Job): corre el respaldo diario de la base de
datos y avisa a los superadmins solo si algo falló (D4 - vigilancia del
respaldo). Reutiliza ConfiguracionRespaldo.ejecutar_respaldo(), la misma
lógica que ya usa el botón manual de "Crear respaldo".
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from core.models import ConfiguracionRespaldo, Notificacion


class Command(BaseCommand):
    help = 'Ejecuta el respaldo diario de la base de datos y alerta a los superadmins si falla'

    def handle(self, *args, **options):
        config, _ = ConfiguracionRespaldo.objects.get_or_create(
            defaults={'nombre': 'Respaldo Automático'}
        )

        if not config.activo:
            self.stdout.write(self.style.WARNING('Respaldo automático desactivado en configuración, no se ejecuta.'))
            return

        exito, backup_name, error = config.ejecutar_respaldo()

        if exito:
            self.stdout.write(self.style.SUCCESS(f'Respaldo creado correctamente: {backup_name}'))
            return

        for admin in User.objects.filter(is_superuser=True):
            Notificacion.crear_notificacion(
                tipo='AS',
                titulo='Falló el respaldo automático de la base de datos',
                mensaje=f'El respaldo diario programado no se pudo completar. Detalle: {error}',
                usuario=admin,
                prioridad='AL',
                enlace='/respaldos/'
            )

        raise CommandError(f'Falló el respaldo automático: {error}')
