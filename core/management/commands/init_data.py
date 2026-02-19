"""
Comando para inicializar datos básicos del sistema.
Crea configuraciones por defecto necesarias para que el sistema funcione.
Se ejecuta automáticamente en el Procfile después de migrate.
"""
from django.core.management.base import BaseCommand
from decimal import Decimal


class Command(BaseCommand):
    help = 'Inicializa datos básicos del sistema (configuraciones, rutas, tipos de negocio)'

    def handle(self, *args, **options):
        from core.models import (
            ConfiguracionCredito, ConfiguracionMora, ConfiguracionRespaldo,
            ConfiguracionPlanilla, ColumnaPlanilla, RutaCobro, TipoNegocio
        )

        creados = []

        # --- Configuraciones de Crédito por categoría ---
        categorias = [
            ('NU', 'Nuevo', Decimal('50000'), Decimal('0'), False, 0),
            ('RE', 'Regular', Decimal('100000'), Decimal('30'), True, 5),
            ('EX', 'Excelente', Decimal('500000'), Decimal('50'), True, 0),
            ('MO', 'Moroso', Decimal('0'), Decimal('0'), False, 0),
        ]
        for cat, nombre, limite, pct, renovar, dias in categorias:
            obj, created = ConfiguracionCredito.objects.get_or_create(
                categoria=cat,
                defaults={
                    'limite_maximo': limite,
                    'porcentaje_sobre_deuda': pct,
                    'puede_renovar_con_deuda': renovar,
                    'dias_minimos_para_renovar': dias,
                }
            )
            if created:
                creados.append(f'ConfiguracionCredito: {nombre}')

        # --- Configuración de Mora ---
        obj, created = ConfiguracionMora.objects.get_or_create(
            nombre='Configuración Principal',
            defaults={
                'porcentaje_diario': Decimal('0.50'),
                'dias_gracia': 0,
                'aplicar_automaticamente': True,
                'monto_minimo_mora': Decimal('0'),
            }
        )
        if created:
            creados.append('ConfiguracionMora')

        # --- Configuración de Respaldo ---
        obj, created = ConfiguracionRespaldo.objects.get_or_create(
            nombre='Respaldo Automático',
            defaults={
                'frecuencia_horas': 24,
                'mantener_ultimos': 7,
            }
        )
        if created:
            creados.append('ConfiguracionRespaldo')

        # --- Configuración de Planilla ---
        obj, created = ConfiguracionPlanilla.objects.get_or_create(
            nombre='Planilla Principal',
            defaults={
                'titulo_reporte': 'Planilla de Cobros',
                'es_default': True,
                'mostrar_logo': True,
                'mostrar_fecha': True,
                'mostrar_totales': True,
                'mostrar_firmas': False,
                'agrupar_por_ruta': True,
                'agrupar_por_categoria': False,
                'incluir_vencidas': True,
            }
        )
        if created:
            creados.append('ConfiguracionPlanilla')

        # --- Columnas de Planilla por defecto ---
        columnas_default = [
            ('numero', 1, '5%'),
            ('nombre_cliente', 2, 'auto'),
            ('telefono', 3, '12%'),
            ('cuota_actual', 4, '10%'),
            ('monto_cuota', 5, '12%'),
            ('monto_pendiente', 6, '12%'),
            ('espacio_cobrado', 7, '10%'),
        ]
        if not ColumnaPlanilla.objects.exists():
            for col, orden, ancho in columnas_default:
                ColumnaPlanilla.objects.create(
                    nombre_columna=col, orden=orden, ancho=ancho, activa=True
                )
            creados.append(f'ColumnaPlanilla ({len(columnas_default)} columnas)')

        # --- Rutas de cobro por defecto ---
        rutas_default = [
            ('Ruta Centro', '#0d6efd', 1),
            ('Ruta Norte', '#198754', 2),
            ('Ruta Sur', '#dc3545', 3),
        ]
        if not RutaCobro.objects.exists():
            for nombre, color, orden in rutas_default:
                RutaCobro.objects.create(nombre=nombre, color=color, orden=orden)
            creados.append(f'RutaCobro ({len(rutas_default)} rutas)')

        # --- Tipos de negocio por defecto ---
        tipos_default = [
            'Comercio',
            'Kiosco',
            'Almacén',
            'Particular',
            'Verdulería',
            'Carnicería',
        ]
        if not TipoNegocio.objects.exists():
            for i, nombre in enumerate(tipos_default):
                TipoNegocio.objects.create(nombre=nombre, orden=i + 1)
            creados.append(f'TipoNegocio ({len(tipos_default)} tipos)')

        # --- Resumen ---
        if creados:
            self.stdout.write(self.style.SUCCESS(
                f'✓ Datos iniciales creados: {", ".join(creados)}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                '✓ Datos iniciales ya existen, nada que crear.'
            ))
