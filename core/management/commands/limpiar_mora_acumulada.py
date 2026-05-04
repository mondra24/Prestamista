"""
Limpia la mora acumulada que se cargó cuando el sistema calculaba interés
por mora automáticamente.

El cliente confirmó que esa plata nunca entró: la mora "cobrada" que quedó
en BD es producto del cálculo automático, no de un cobro real. Este comando
deja en cero esos campos en todas las tablas afectadas.

Uso:
    python manage.py limpiar_mora_acumulada              # dry-run (no toca nada)
    python manage.py limpiar_mora_acumulada --apply      # ejecuta
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from core.models import Cuota, HistorialModificacionPago, InteresMora


class Command(BaseCommand):
    help = 'Limpia toda la mora cargada por cálculo automático (Cuota.interes_mora_cobrado, HistorialModificacionPago.interes_mora, tabla InteresMora). Por default es dry-run.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Aplica los cambios. Sin este flag corre en modo dry-run.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']

        cuotas_qs = Cuota.objects.filter(interes_mora_cobrado__gt=0)
        cuotas_count = cuotas_qs.count()
        cuotas_total = cuotas_qs.aggregate(total=Sum('interes_mora_cobrado'))['total'] or Decimal('0.00')

        hist_qs = HistorialModificacionPago.objects.filter(interes_mora__gt=0)
        hist_count = hist_qs.count()
        hist_total = hist_qs.aggregate(total=Sum('interes_mora'))['total'] or Decimal('0.00')

        interes_count = InteresMora.objects.count()

        modo = 'DRY-RUN (sin tocar nada)' if not apply_changes else 'APLICANDO CAMBIOS'
        self.stdout.write('=' * 60)
        self.stdout.write(f'  LIMPIEZA DE MORA AUTOMÁTICA — {modo}')
        self.stdout.write('=' * 60)
        self.stdout.write(f'  Cuota.interes_mora_cobrado > 0      : {cuotas_count} cuotas (${cuotas_total})')
        self.stdout.write(f'  HistorialModificacionPago.interes_mora > 0 : {hist_count} registros (${hist_total})')
        self.stdout.write(f'  InteresMora (tabla legacy)          : {interes_count} registros (se borran todos)')
        self.stdout.write('=' * 60)

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                '\nNo se aplicaron cambios. Para ejecutar de verdad correr:\n'
                '    python manage.py limpiar_mora_acumulada --apply\n'
            ))
            return

        with transaction.atomic():
            cuotas_actualizadas = cuotas_qs.update(interes_mora_cobrado=Decimal('0.00'))
            hist_actualizados = hist_qs.update(interes_mora=Decimal('0.00'))
            interes_borrados, _ = InteresMora.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(
            f'\n✔ Cuota.interes_mora_cobrado puesto en 0   : {cuotas_actualizadas} filas'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'✔ HistorialModificacionPago.interes_mora=0 : {hist_actualizados} filas'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'✔ InteresMora borrada                       : {interes_borrados} filas'
        ))
