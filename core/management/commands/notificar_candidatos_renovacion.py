"""
Job programado (Railway Cron Job): corre cerca del final del día (mismo
horario que alertar_cobradores_sin_actividad, ~21:00 ART, antes de medianoche
para que "hoy" siga siendo el día cuyos pagos se acaban de cerrar) y detecta
préstamos que terminaron de pagarse hoy con buen historial, para ofrecerles
una renovación.
"""
from django.core.management.base import BaseCommand

from core.models import Notificacion


class Command(BaseCommand):
    help = 'Notifica a los administradores los préstamos finalizados hoy que son buenos candidatos a renovación'

    def handle(self, *args, **options):
        detectados = Notificacion.notificar_candidatos_renovacion()

        if detectados:
            self.stdout.write(self.style.SUCCESS(
                f'{detectados} préstamo(s) finalizado(s) hoy son buenos candidatos a renovación.'
            ))
        else:
            self.stdout.write('Ningún préstamo finalizado hoy califica como candidato a renovación.')
