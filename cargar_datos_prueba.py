"""
Script para cargar datos de prueba en el sistema de préstamos
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prestamos_config.settings')
django.setup()

from decimal import Decimal
from core.models import TipoNegocio, ConfiguracionCredito, RutaCobro, ConfiguracionPlanilla, Cliente

print("=== CARGANDO DATOS DE PRUEBA ===\n")

# 1. Crear tipos de negocio
print("1. Creando tipos de negocio...")
tipos_negocio = [
    {'nombre': 'Tienda', 'limite_credito_sugerido': Decimal('50000.00'), 'orden': 1, 'activo': True},
    {'nombre': 'Restaurante', 'limite_credito_sugerido': Decimal('80000.00'), 'orden': 2, 'activo': True},
    {'nombre': 'Venta Ambulante', 'limite_credito_sugerido': Decimal('30000.00'), 'orden': 3, 'activo': True},
    {'nombre': 'Oficina', 'limite_credito_sugerido': Decimal('100000.00'), 'orden': 4, 'activo': True},
    {'nombre': 'Empleado', 'limite_credito_sugerido': Decimal('60000.00'), 'orden': 5, 'activo': True},
    {'nombre': 'Otro', 'limite_credito_sugerido': Decimal('40000.00'), 'orden': 6, 'activo': True},
]
for data in tipos_negocio:
    obj, created = TipoNegocio.objects.get_or_create(nombre=data['nombre'], defaults=data)
    print(f"   {'✓ Creado' if created else '- Existe'}: {obj.nombre}")
print(f"   Total tipos de negocio: {TipoNegocio.objects.count()}")

# 2. Crear configuraciones de crédito por categoría
# limite_maximo = 0 significa "sin límite por categoría" (solo aplica el límite individual del cliente)
print("\n2. Creando configuraciones de crédito...")
configs_credito = [
    {'categoria': 'EX', 'limite_maximo': Decimal('0.00'), 'porcentaje_sobre_deuda': 50, 'puede_renovar_con_deuda': True, 'dias_minimos_para_renovar': 7, 'activo': True},
    {'categoria': 'RE', 'limite_maximo': Decimal('0.00'), 'porcentaje_sobre_deuda': 30, 'puede_renovar_con_deuda': True, 'dias_minimos_para_renovar': 14, 'activo': True},
    {'categoria': 'MO', 'limite_maximo': Decimal('0.00'), 'porcentaje_sobre_deuda': 0, 'puede_renovar_con_deuda': False, 'dias_minimos_para_renovar': 30, 'activo': True},
    {'categoria': 'NU', 'limite_maximo': Decimal('0.00'), 'porcentaje_sobre_deuda': 20, 'puede_renovar_con_deuda': True, 'dias_minimos_para_renovar': 0, 'activo': True},
]
for data in configs_credito:
    obj, created = ConfiguracionCredito.objects.get_or_create(categoria=data['categoria'], defaults=data)
    print(f"   {'✓ Creado' if created else '- Existe'}: {obj.get_categoria_display()}")
print(f"   Total configuraciones: {ConfiguracionCredito.objects.count()}")

# 3. Crear rutas de cobro
print("\n3. Creando rutas de cobro...")
rutas = [
    {'nombre': 'Centro', 'descripcion': 'Zona centro de la ciudad', 'orden': 1, 'color': '#3498db', 'activa': True},
    {'nombre': 'Norte', 'descripcion': 'Zona norte', 'orden': 2, 'color': '#2ecc71', 'activa': True},
    {'nombre': 'Sur', 'descripcion': 'Zona sur', 'orden': 3, 'color': '#e74c3c', 'activa': True},
    {'nombre': 'Oriente', 'descripcion': 'Zona oriente', 'orden': 4, 'color': '#9b59b6', 'activa': True},
]
for data in rutas:
    obj, created = RutaCobro.objects.get_or_create(nombre=data['nombre'], defaults=data)
    print(f"   {'✓ Creado' if created else '- Existe'}: {obj.nombre}")
print(f"   Total rutas: {RutaCobro.objects.filter(activa=True).count()}")

# 4. Verificar/crear configuración de planilla
print("\n4. Verificando configuración de planilla...")
planilla, created = ConfiguracionPlanilla.objects.get_or_create(
    nombre='Planilla Estándar',
    defaults={
        'titulo_reporte': 'PLANILLA DE COBROS',
        'subtitulo': 'Sistema de Gestión de Préstamos',
        'mostrar_logo': False,
        'mostrar_fecha': True,
        'mostrar_totales': True,
        'mostrar_firmas': True,
        'agrupar_por_ruta': True,
        'agrupar_por_categoria': False,
        'incluir_vencidas': False,
        'es_default': True
    }
)
print(f"   {'✓ Creado' if created else '- Existe'}: {planilla.nombre}")

# 5. Asignar datos a clientes existentes
print("\n5. Actualizando clientes...")
clientes = Cliente.objects.all()
tipo_tienda = TipoNegocio.objects.filter(nombre='Tienda').first()
ruta_centro = RutaCobro.objects.filter(nombre='Centro').first()

for i, cliente in enumerate(clientes):
    updated = False
    if not cliente.tipo_negocio and tipo_tienda:
        cliente.tipo_negocio = tipo_tienda
        updated = True
    if not cliente.ruta and ruta_centro:
        cliente.ruta = ruta_centro
        updated = True
    if updated:
        cliente.save()
        print(f"   ✓ Actualizado: {cliente.nombre_completo}")
    else:
        print(f"   - Sin cambios: {cliente.nombre_completo}")

print("\n=== DATOS CARGADOS EXITOSAMENTE ===")
print(f"\nResumen:")
print(f"   - Tipos de negocio: {TipoNegocio.objects.count()}")
print(f"   - Configuraciones de crédito: {ConfiguracionCredito.objects.count()}")
print(f"   - Rutas de cobro: {RutaCobro.objects.filter(activa=True).count()}")
print(f"   - Configuraciones de planilla: {ConfiguracionPlanilla.objects.count()}")
print(f"   - Clientes: {Cliente.objects.count()}")
