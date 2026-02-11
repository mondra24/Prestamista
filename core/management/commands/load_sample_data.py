"""
Comando para cargar datos de prueba si la base de datos está vacía.
Solo carga datos si no hay clientes en la base de datos.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta
import random


class Command(BaseCommand):
    help = 'Carga datos de prueba si la base de datos está vacía'

    def handle(self, *args, **options):
        from core.models import (
            TipoNegocio, ConfiguracionCredito, RutaCobro, 
            ConfiguracionPlanilla, Cliente, Prestamo
        )
        
        # Verificar si ya hay datos
        if Cliente.objects.exists():
            self.stdout.write(self.style.SUCCESS(
                'Ya existen datos en la base de datos. Saltando carga de prueba.'
            ))
            return
        
        self.stdout.write('=== CARGANDO DATOS DE PRUEBA ===\n')
        
        # 1. Crear tipos de negocio
        self.stdout.write('1. Creando tipos de negocio...')
        tipos_negocio_data = [
            {'nombre': 'Tienda', 'limite_credito_sugerido': Decimal('500000.00'), 'orden': 1},
            {'nombre': 'Restaurante', 'limite_credito_sugerido': Decimal('800000.00'), 'orden': 2},
            {'nombre': 'Venta Ambulante', 'limite_credito_sugerido': Decimal('300000.00'), 'orden': 3},
            {'nombre': 'Oficina', 'limite_credito_sugerido': Decimal('1000000.00'), 'orden': 4},
            {'nombre': 'Empleado', 'limite_credito_sugerido': Decimal('600000.00'), 'orden': 5},
            {'nombre': 'Otro', 'limite_credito_sugerido': Decimal('400000.00'), 'orden': 6},
        ]
        tipos_negocio = {}
        for data in tipos_negocio_data:
            obj, _ = TipoNegocio.objects.get_or_create(nombre=data['nombre'], defaults=data)
            tipos_negocio[data['nombre']] = obj
        
        # 2. Crear configuraciones de crédito
        # limite_maximo = 0 significa "sin límite por categoría" (solo aplica límite individual del cliente)
        self.stdout.write('2. Creando configuraciones de crédito...')
        configs = [
            {'categoria': 'EX', 'limite_maximo': Decimal('0.00'), 'porcentaje_sobre_deuda': 50, 'puede_renovar_con_deuda': True, 'dias_minimos_para_renovar': 7},
            {'categoria': 'RE', 'limite_maximo': Decimal('0.00'), 'porcentaje_sobre_deuda': 30, 'puede_renovar_con_deuda': True, 'dias_minimos_para_renovar': 14},
            {'categoria': 'MO', 'limite_maximo': Decimal('0.00'), 'porcentaje_sobre_deuda': 0, 'puede_renovar_con_deuda': False, 'dias_minimos_para_renovar': 30},
            {'categoria': 'NU', 'limite_maximo': Decimal('0.00'), 'porcentaje_sobre_deuda': 20, 'puede_renovar_con_deuda': True, 'dias_minimos_para_renovar': 0},
        ]
        for data in configs:
            ConfiguracionCredito.objects.get_or_create(categoria=data['categoria'], defaults=data)
        
        # 3. Crear rutas de cobro
        self.stdout.write('3. Creando rutas de cobro...')
        rutas_data = [
            {'nombre': 'Centro', 'descripcion': 'Zona centro', 'orden': 1, 'color': '#3498db'},
            {'nombre': 'Norte', 'descripcion': 'Zona norte', 'orden': 2, 'color': '#2ecc71'},
            {'nombre': 'Sur', 'descripcion': 'Zona sur', 'orden': 3, 'color': '#e74c3c'},
            {'nombre': 'Oriente', 'descripcion': 'Zona oriente', 'orden': 4, 'color': '#9b59b6'},
        ]
        rutas = {}
        for data in rutas_data:
            obj, _ = RutaCobro.objects.get_or_create(nombre=data['nombre'], defaults=data)
            rutas[data['nombre']] = obj
        
        # 4. Crear configuración de planilla
        self.stdout.write('4. Creando configuración de planilla...')
        ConfiguracionPlanilla.objects.get_or_create(
            nombre='Planilla Estándar',
            defaults={
                'titulo_reporte': 'PLANILLA DE COBROS',
                'subtitulo': 'Sistema de Gestión de Préstamos',
                'mostrar_fecha': True,
                'mostrar_totales': True,
                'agrupar_por_ruta': True,
                'es_default': True
            }
        )
        
        # 5. Crear clientes de prueba
        self.stdout.write('5. Creando clientes de prueba...')
        clientes_data = [
            {'nombre': 'Juan', 'apellido': 'Pérez', 'telefono': '3001234567', 'direccion': 'Calle 10 #20-30', 'categoria': 'EX', 'tipo': 'Tienda', 'ruta': 'Centro'},
            {'nombre': 'María', 'apellido': 'García', 'telefono': '3109876543', 'direccion': 'Carrera 5 #15-20', 'categoria': 'EX', 'tipo': 'Restaurante', 'ruta': 'Norte'},
            {'nombre': 'Carlos', 'apellido': 'López', 'telefono': '3205551234', 'direccion': 'Avenida 3 #8-15', 'categoria': 'RE', 'tipo': 'Venta Ambulante', 'ruta': 'Sur'},
            {'nombre': 'Ana', 'apellido': 'Martínez', 'telefono': '3157778899', 'direccion': 'Calle 25 #10-05', 'categoria': 'NU', 'tipo': 'Empleado', 'ruta': 'Centro'},
            {'nombre': 'Pedro', 'apellido': 'Rodríguez', 'telefono': '3184443322', 'direccion': 'Carrera 12 #30-40', 'categoria': 'RE', 'tipo': 'Tienda', 'ruta': 'Oriente'},
            {'nombre': 'Laura', 'apellido': 'Sánchez', 'telefono': '3006667788', 'direccion': 'Calle 8 #5-10', 'categoria': 'EX', 'tipo': 'Oficina', 'ruta': 'Norte'},
            {'nombre': 'Diego', 'apellido': 'Hernández', 'telefono': '3112223344', 'direccion': 'Avenida 15 #22-33', 'categoria': 'NU', 'tipo': 'Otro', 'ruta': 'Sur'},
            {'nombre': 'Sofia', 'apellido': 'Torres', 'telefono': '3209998877', 'direccion': 'Carrera 20 #18-25', 'categoria': 'RE', 'tipo': 'Restaurante', 'ruta': 'Centro'},
        ]
        
        clientes = []
        for data in clientes_data:
            cliente = Cliente.objects.create(
                nombre=data['nombre'],
                apellido=data['apellido'],
                telefono=data['telefono'],
                direccion=data['direccion'],
                categoria=data['categoria'],
                tipo_negocio=tipos_negocio.get(data['tipo']),
                ruta=rutas.get(data['ruta']),
                limite_credito=Decimal('500000.00')
            )
            clientes.append(cliente)
            self.stdout.write(f'   ✓ {cliente.nombre_completo}')
        
        # 6. Crear préstamos de prueba
        self.stdout.write('6. Creando préstamos de prueba...')
        hoy = date.today()
        
        prestamos_data = [
            {'cliente': 0, 'monto': 100000, 'tasa': 20, 'cuotas': 30, 'frecuencia': 'DI', 'dias_atras': 10},
            {'cliente': 1, 'monto': 200000, 'tasa': 20, 'cuotas': 30, 'frecuencia': 'DI', 'dias_atras': 5},
            {'cliente': 2, 'monto': 50000, 'tasa': 20, 'cuotas': 20, 'frecuencia': 'DI', 'dias_atras': 15},
            {'cliente': 3, 'monto': 80000, 'tasa': 20, 'cuotas': 30, 'frecuencia': 'DI', 'dias_atras': 3},
            {'cliente': 4, 'monto': 150000, 'tasa': 20, 'cuotas': 30, 'frecuencia': 'DI', 'dias_atras': 20},
            {'cliente': 5, 'monto': 300000, 'tasa': 20, 'cuotas': 30, 'frecuencia': 'DI', 'dias_atras': 7},
        ]
        
        for data in prestamos_data:
            cliente = clientes[data['cliente']]
            fecha_inicio = hoy - timedelta(days=data['dias_atras'])
            
            prestamo = Prestamo.objects.create(
                cliente=cliente,
                monto_solicitado=Decimal(str(data['monto'])),
                tasa_interes_porcentaje=Decimal(str(data['tasa'])),
                cuotas_pactadas=data['cuotas'],
                frecuencia=data['frecuencia'],
                fecha_inicio=fecha_inicio
            )
            
            # Pagar algunas cuotas aleatoriamente
            cuotas_a_pagar = min(data['dias_atras'] - 2, data['cuotas'] - 5)
            if cuotas_a_pagar > 0:
                cuotas = prestamo.cuotas.filter(estado='PE').order_by('numero_cuota')[:cuotas_a_pagar]
                for cuota in cuotas:
                    cuota.registrar_pago()
            
            self.stdout.write(f'   ✓ Préstamo #{prestamo.pk} - {cliente.nombre_completo} - ${data["monto"]:,}')
        
        self.stdout.write(self.style.SUCCESS('\n=== DATOS DE PRUEBA CARGADOS ==='))
        self.stdout.write(f'   Clientes: {Cliente.objects.count()}')
        self.stdout.write(f'   Préstamos: {Prestamo.objects.count()}')
