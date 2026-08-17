"""
Job programado (Railway Cron Job): arma solo el Excel de cierre de caja del
día (C1) y lo deja guardado en reportes/ para descargar desde el panel.
Por ahora no se envía por ningún canal (eso se conecta cuando exista
WhatsApp/B1); reutiliza construir_excel_cierre_caja(), la misma función que
usa la exportación manual.
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Cuota, fecha_local_hoy
from core.views import construir_excel_cierre_caja


class Command(BaseCommand):
    help = 'Genera el Excel de cierre de caja del día y lo guarda en reportes/ (Cron Job diario, ~22:00 ART)'

    def handle(self, *args, **options):
        fecha = fecha_local_hoy()

        pagos = Cuota.objects.filter(
            fecha_pago_real=fecha,
            estado__in=['PA', 'PC']
        ).select_related('prestamo', 'prestamo__cliente', 'prestamo__cliente__ruta', 'cobrado_por').order_by(
            'prestamo__cliente__apellido'
        )

        wb = construir_excel_cierre_caja(fecha, pagos)

        reportes_dir = os.path.join(settings.BASE_DIR, 'reportes')
        os.makedirs(reportes_dir, exist_ok=True)
        nombre = f'cierre_{fecha.strftime("%Y%m%d")}.xlsx'
        wb.save(os.path.join(reportes_dir, nombre))

        self.stdout.write(self.style.SUCCESS(f'Cierre de caja generado: {nombre} ({pagos.count()} cobros)'))
