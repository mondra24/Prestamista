"""
Comando para actualizar los límites de crédito por categoría a 0 (sin límite).
Esto permite que solo aplique el límite individual de cada cliente.
"""
from django.core.management.base import BaseCommand
from decimal import Decimal


class Command(BaseCommand):
    help = 'Actualiza los límites de crédito por categoría a 0 (sin límite por categoría)'

    def handle(self, *args, **options):
        from core.models import ConfiguracionCredito
        
        self.stdout.write('=== ACTUALIZANDO LÍMITES DE CRÉDITO POR CATEGORÍA ===\n')
        
        # Actualizar todos los límites a 0
        updated = ConfiguracionCredito.objects.all().update(limite_maximo=Decimal('0.00'))
        
        if updated > 0:
            self.stdout.write(self.style.SUCCESS(
                f'Se actualizaron {updated} configuraciones de crédito.'
            ))
            self.stdout.write('Ahora solo aplica el límite individual de cada cliente.')
        else:
            self.stdout.write(self.style.WARNING(
                'No había configuraciones de crédito para actualizar.'
            ))
        
        # Mostrar configuraciones actuales
        self.stdout.write('\nConfiguraciones actuales:')
        for config in ConfiguracionCredito.objects.all():
            self.stdout.write(
                f'  {config.get_categoria_display()}: límite_maximo = {config.limite_maximo}'
            )
