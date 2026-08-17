"""
Job programado (Railway Cron Job): arma el Excel semanal de morosidad y
proyección (C2) y lo guarda en reportes/. Requiere que exista el mecanismo
de C1 (misma carpeta de reportes); pensado para correr una vez por semana,
los lunes a la mañana, para arrancar la semana con la foto del fin de
semana/semana anterior.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import fecha_local_hoy
from core.views import construir_excel_morosidad


class Command(BaseCommand):
    help = 'Genera el Excel semanal de morosidad y proyección (Cron Job semanal, lunes ~08:00 ART)'

    def handle(self, *args, **options):
        fecha = fecha_local_hoy()
        wb = construir_excel_morosidad(fecha)

        reportes_dir = os.path.join(settings.BASE_DIR, 'reportes')
        os.makedirs(reportes_dir, exist_ok=True)
        nombre = f'morosidad_{fecha.strftime("%Y%m%d")}.xlsx'
        wb.save(os.path.join(reportes_dir, nombre))

        self.stdout.write(self.style.SUCCESS(f'Reporte de morosidad generado: {nombre}'))
