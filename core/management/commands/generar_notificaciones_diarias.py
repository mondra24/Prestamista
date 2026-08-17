"""
Job programado (Railway Cron Job): revisa las cuotas todas las noches y genera
las notificaciones de vencidas / por vencer, sin depender de que alguien entre
al sistema y dispare /api/generar-notificaciones/ manualmente.
"""
from django.core.management.base import BaseCommand

from core.models import Notificacion


class Command(BaseCommand):
    help = 'Genera notificaciones de cuotas vencidas y por vencer (uso: Cron Job diario a las 00:00 ART)'

    def handle(self, *args, **options):
        vencidas = Notificacion.notificar_cuotas_vencidas()
        por_vencer = Notificacion.notificar_cuotas_por_vencer()

        self.stdout.write(self.style.SUCCESS(
            f'Notificaciones generadas: {vencidas} de cuotas vencidas, {por_vencer} de cuotas por vencer.'
        ))
