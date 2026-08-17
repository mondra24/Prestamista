"""
Job programado (Railway Cron Job): arma la planilla de ruta del día (C3)
para cada cobrador activo con cuotas pendientes, y la guarda en reportes/.
Requiere la carpeta de reportes de C1. Pensado para correr temprano a la
mañana, antes de que salgan a cobrar.
"""
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Cuota, PerfilUsuario, fecha_local_hoy
from core.views import construir_excel_planilla_cobrador


class Command(BaseCommand):
    help = 'Genera la planilla de ruta diaria de cada cobrador (Cron Job diario, ~07:00 ART)'

    def handle(self, *args, **options):
        fecha = fecha_local_hoy()

        reportes_dir = os.path.join(settings.BASE_DIR, 'reportes')
        os.makedirs(reportes_dir, exist_ok=True)

        cobradores = User.objects.filter(
            perfil__rol=PerfilUsuario.Rol.COBRADOR,
            perfil__activo=True
        )

        generadas = 0
        for cobrador in cobradores:
            tiene_pendientes = Cuota.objects.filter(
                prestamo__estado='AC',
                prestamo__cobrador=cobrador,
                estado__in=['PE', 'PC'],
                fecha_vencimiento__lte=fecha
            ).exists()

            if not tiene_pendientes:
                continue

            wb = construir_excel_planilla_cobrador(fecha, cobrador)
            nombre = f'planilla_{cobrador.username}_{fecha.strftime("%Y%m%d")}.xlsx'
            wb.save(os.path.join(reportes_dir, nombre))
            generadas += 1

        if generadas:
            self.stdout.write(self.style.SUCCESS(f'{generadas} planilla(s) de ruta generada(s).'))
        else:
            self.stdout.write('Ningún cobrador tenía cuotas pendientes hoy.')
