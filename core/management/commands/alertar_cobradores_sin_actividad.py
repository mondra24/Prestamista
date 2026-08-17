"""
Job programado (Railway Cron Job): corre cerca del final del día (ej. 21:00
hora Argentina, antes de medianoche) y avisa a los administradores si un
cobrador tenía cuotas para cobrar hoy y no cargó ningún pago.
"""
from django.core.management.base import BaseCommand

from core.models import Notificacion


class Command(BaseCommand):
    help = 'Alerta a los administradores si un cobrador no registró cobros en el día (uso: Cron Job diario, ~21:00 ART)'

    def handle(self, *args, **options):
        detectados = Notificacion.notificar_cobradores_sin_actividad()

        if detectados:
            self.stdout.write(self.style.WARNING(
                f'{detectados} cobrador(es) tenían cuotas para cobrar hoy y no registraron ningún pago.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS('Todos los cobradores con cuotas pendientes registraron actividad hoy.'))
