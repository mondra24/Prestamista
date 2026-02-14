"""
Script para crear préstamos variados de prueba en Railway
Para testing de flujo de la aplicación
"""
import os
import django
from datetime import date, timedelta
from decimal import Decimal
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prestamos_config.settings')
os.environ['DATABASE_URL'] = 'postgresql://postgres:iZwZIFPPHThinbHTlGSAOrQKuvlIXlAK@metro.proxy.rlwy.net:17571/railway'

django.setup()

from django.contrib.auth.models import User
from core.models import Cliente, Prestamo, Cuota, RutaCobro, TipoNegocio, PerfilUsuario

print("=" * 60)
print("  CREANDO PRÉSTAMOS VARIADOS PARA TESTING")
print("=" * 60)

# Verificar usuarios
admin_user = User.objects.filter(is_superuser=True).first()
coco_user = User.objects.filter(username='coco').first()

if not admin_user:
    print("\n⚠ No hay usuario admin. Creando...")
    admin_user = User.objects.create_superuser('admin', '', 'admin123')
    print(f"  ✓ Admin creado (user: admin, pass: admin123)")

if not coco_user:
    print("\n⚠ No hay usuario coco. Creando...")
    coco_user = User.objects.create_user('coco', password='123')
    PerfilUsuario.objects.get_or_create(user=coco_user)
    print(f"  ✓ Coco creado (user: coco, pass: 123)")

print(f"\n👤 Admin: {admin_user.username} (superuser={admin_user.is_superuser})")
print(f"👤 Coco: {coco_user.username}")

# Asegurar rutas y tipos de negocio
rutas_nombres = ['Centro', 'Norte', 'Sur', 'Oriente']
rutas = {}
for i, nombre in enumerate(rutas_nombres, 1):
    ruta, _ = RutaCobro.objects.get_or_create(nombre=nombre, defaults={'orden': i, 'activa': True})
    rutas[nombre] = ruta

tipos_nombres = ['Tienda', 'Restaurante', 'Venta Ambulante', 'Empleado', 'Oficina']
tipos = {}
for i, nombre in enumerate(tipos_nombres, 1):
    tipo, _ = TipoNegocio.objects.get_or_create(nombre=nombre, defaults={'orden': i, 'activo': True})
    tipos[nombre] = tipo

hoy = date.today()

# ==========================================
# CLIENTES Y PRÉSTAMOS PARA ADMIN
# ==========================================
print("\n" + "=" * 50)
print("  CLIENTES Y PRÉSTAMOS PARA ADMIN")
print("=" * 50)

clientes_admin = [
    {'nombre': 'Roberto', 'apellido': 'Fernández', 'telefono': '3516001001', 'direccion': 'Av. Colón 1500', 'ruta': 'Centro', 'tipo': 'Tienda'},
    {'nombre': 'Gabriela', 'apellido': 'Moreno', 'telefono': '3516002002', 'direccion': 'San Martín 320', 'ruta': 'Centro', 'tipo': 'Restaurante'},
    {'nombre': 'Hernán', 'apellido': 'Bustos', 'telefono': '3516003003', 'direccion': 'Bv. San Juan 890', 'ruta': 'Norte', 'tipo': 'Empleado'},
    {'nombre': 'Silvia', 'apellido': 'Aguirre', 'telefono': '3516004004', 'direccion': 'Duarte Quirós 445', 'ruta': 'Sur', 'tipo': 'Oficina'},
    {'nombre': 'Facundo', 'apellido': 'Ríos', 'telefono': '3516005005', 'direccion': 'Gral. Paz 1200', 'ruta': 'Norte', 'tipo': 'Venta Ambulante'},
    {'nombre': 'Patricia', 'apellido': 'Luna', 'telefono': '3516006006', 'direccion': 'Corrientes 780', 'ruta': 'Oriente', 'tipo': 'Tienda'},
    {'nombre': 'Esteban', 'apellido': 'Molina', 'telefono': '3516007007', 'direccion': 'La Cañada 500', 'ruta': 'Sur', 'tipo': 'Empleado'},
]

prestamos_admin = [
    # Roberto: Préstamo diario grande, empezó hace 10 días, algunas cuotas pagadas
    {'cliente_idx': 0, 'monto': 50000, 'tasa': 20, 'cuotas': 20, 'frecuencia': 'DI', 'dias_inicio': 10, 'cuotas_a_pagar': 7},
    # Gabriela: Préstamo semanal, empezó hace 3 semanas, al día con pagos
    {'cliente_idx': 1, 'monto': 80000, 'tasa': 25, 'cuotas': 12, 'frecuencia': 'SE', 'dias_inicio': 21, 'cuotas_a_pagar': 3},
    # Hernán: Préstamo diario chico, empezó hace 5 días, ninguna cuota pagada (moroso)
    {'cliente_idx': 2, 'monto': 15000, 'tasa': 15, 'cuotas': 15, 'frecuencia': 'DI', 'dias_inicio': 5, 'cuotas_a_pagar': 0},
    # Silvia: Préstamo mensual grande, empezó hace 2 meses, 2 cuotas pagadas
    {'cliente_idx': 3, 'monto': 200000, 'tasa': 30, 'cuotas': 6, 'frecuencia': 'ME', 'dias_inicio': 60, 'cuotas_a_pagar': 2},
    # Facundo: Préstamo quincenal, empezó hace 1 mes, 1 pago parcial
    {'cliente_idx': 4, 'monto': 30000, 'tasa': 20, 'cuotas': 8, 'frecuencia': 'QU', 'dias_inicio': 30, 'cuotas_a_pagar': 1, 'pago_parcial': True},
    # Patricia: Préstamo diario, empezó hoy (nuevo, sin pagos)
    {'cliente_idx': 5, 'monto': 25000, 'tasa': 18, 'cuotas': 25, 'frecuencia': 'DI', 'dias_inicio': 0, 'cuotas_a_pagar': 0},
    # Esteban: Préstamo semanal casi terminado
    {'cliente_idx': 6, 'monto': 40000, 'tasa': 22, 'cuotas': 8, 'frecuencia': 'SE', 'dias_inicio': 49, 'cuotas_a_pagar': 6},
]

# ==========================================
# CLIENTES Y PRÉSTAMOS PARA COCO
# ==========================================
print("\n" + "=" * 50)
print("  CLIENTES Y PRÉSTAMOS PARA COCO")
print("=" * 50)

clientes_coco = [
    {'nombre': 'Ramiro', 'apellido': 'Sosa', 'telefono': '3517001001', 'direccion': 'Av. Vélez Sarsfield 1800', 'ruta': 'Centro', 'tipo': 'Tienda'},
    {'nombre': 'Claudia', 'apellido': 'Peralta', 'telefono': '3517002002', 'direccion': 'Humberto Primo 650', 'ruta': 'Norte', 'tipo': 'Restaurante'},
    {'nombre': 'Alejandro', 'apellido': 'Vega', 'telefono': '3517003003', 'direccion': 'Av. Sabatini 2300', 'ruta': 'Sur', 'tipo': 'Venta Ambulante'},
    {'nombre': 'Romina', 'apellido': 'Acosta', 'telefono': '3517004004', 'direccion': 'Chacabuco 900', 'ruta': 'Centro', 'tipo': 'Empleado'},
    {'nombre': 'Tomás', 'apellido': 'Méndez', 'telefono': '3517005005', 'direccion': 'Rivadavia 1100', 'ruta': 'Oriente', 'tipo': 'Oficina'},
    {'nombre': 'Florencia', 'apellido': 'Paz', 'telefono': '3517006006', 'direccion': 'Dean Funes 340', 'ruta': 'Norte', 'tipo': 'Tienda'},
]

prestamos_coco = [
    # Ramiro: Diario mediano, empezó hace 8 días, 5 cuotas pagadas
    {'cliente_idx': 0, 'monto': 35000, 'tasa': 20, 'cuotas': 20, 'frecuencia': 'DI', 'dias_inicio': 8, 'cuotas_a_pagar': 5},
    # Claudia: Semanal grande, empezó hace 2 semanas, 2 pagadas
    {'cliente_idx': 1, 'monto': 100000, 'tasa': 25, 'cuotas': 10, 'frecuencia': 'SE', 'dias_inicio': 14, 'cuotas_a_pagar': 2},
    # Alejandro: Diario chico, empezó hace 12 días, moroso con ninguna pagada
    {'cliente_idx': 2, 'monto': 10000, 'tasa': 15, 'cuotas': 10, 'frecuencia': 'DI', 'dias_inicio': 12, 'cuotas_a_pagar': 0},
    # Romina: Quincenal, empezó hace 45 días, 3 cuotas pagadas
    {'cliente_idx': 3, 'monto': 60000, 'tasa': 22, 'cuotas': 6, 'frecuencia': 'QU', 'dias_inicio': 45, 'cuotas_a_pagar': 3},
    # Tomás: Mensual grande, empezó hace 25 días, sin pagos aún (próximo vence pronto)
    {'cliente_idx': 4, 'monto': 150000, 'tasa': 28, 'cuotas': 4, 'frecuencia': 'ME', 'dias_inicio': 25, 'cuotas_a_pagar': 0},
    # Florencia: Diario, empezó hace 3 días, 2 cuotas pagadas hoy
    {'cliente_idx': 5, 'monto': 20000, 'tasa': 18, 'cuotas': 20, 'frecuencia': 'DI', 'dias_inicio': 3, 'cuotas_a_pagar': 2, 'pagar_hoy': True},
]


def crear_clientes(datos_clientes, usuario):
    """Crea clientes y los devuelve como lista"""
    clientes = []
    for data in datos_clientes:
        cliente, created = Cliente.objects.get_or_create(
            nombre=data['nombre'],
            apellido=data['apellido'],
            defaults={
                'telefono': data['telefono'],
                'direccion': data['direccion'],
                'ruta': rutas.get(data['ruta']),
                'tipo_negocio': tipos.get(data['tipo']),
                'usuario': usuario,
            }
        )
        if not created:
            cliente.usuario = usuario
            cliente.ruta = rutas.get(data['ruta'], cliente.ruta)
            cliente.tipo_negocio = tipos.get(data['tipo'], cliente.tipo_negocio)
            cliente.save()
        clientes.append(cliente)
        status = "✓ Creado" if created else "~ Actualizado"
        print(f"  {status}: {cliente.nombre_completo} → {usuario.username}")
    return clientes


def crear_prestamo_con_pagos(cliente, config):
    """Crea un préstamo y simula pagos según la configuración"""
    fecha_inicio = hoy - timedelta(days=config['dias_inicio'])
    
    # Verificar si ya tiene préstamo activo
    if cliente.prestamos.filter(estado='AC').exists():
        print(f"    ⚠ {cliente.nombre_completo} ya tiene préstamo activo, omitiendo...")
        return None
    
    # Crear préstamo
    prestamo = Prestamo(
        cliente=cliente,
        monto_solicitado=Decimal(str(config['monto'])),
        tasa_interes_porcentaje=Decimal(str(config['tasa'])),
        cuotas_pactadas=config['cuotas'],
        frecuencia=config['frecuencia'],
        fecha_inicio=fecha_inicio,
    )
    prestamo.save()
    
    print(f"\n  📋 Préstamo #{prestamo.pk} para {cliente.nombre_completo}:")
    print(f"     Capital: ${config['monto']:,} | Tasa: {config['tasa']}% | Total: ${float(prestamo.monto_total_a_pagar):,.0f}")
    print(f"     {config['cuotas']} cuotas {prestamo.get_frecuencia_display()} | Inicio: {fecha_inicio.strftime('%d/%m/%Y')} | Fin: {prestamo.fecha_finalizacion.strftime('%d/%m/%Y')}")
    
    # Simular pagos
    cuotas_a_pagar = config.get('cuotas_a_pagar', 0)
    pago_parcial = config.get('pago_parcial', False)
    pagar_hoy = config.get('pagar_hoy', False)
    
    if cuotas_a_pagar > 0:
        cuotas = prestamo.cuotas.order_by('numero_cuota')[:cuotas_a_pagar]
        for cuota in cuotas:
            if pago_parcial and cuota.numero_cuota == cuotas_a_pagar:
                # Último pago es parcial (pagar la mitad)
                monto_parcial = cuota.monto_cuota / 2
                cuota.monto_pagado = monto_parcial
                cuota.estado = 'PC'
                if pagar_hoy:
                    cuota.fecha_pago_real = hoy
                else:
                    cuota.fecha_pago_real = cuota.fecha_vencimiento
                cuota.metodo_pago = 'EF'
                cuota.monto_efectivo = monto_parcial
                cuota.save()
                print(f"     💰 Cuota {cuota.numero_cuota}: PARCIAL ${float(monto_parcial):,.0f} de ${float(cuota.monto_cuota):,.0f}")
            else:
                cuota.monto_pagado = cuota.monto_cuota
                cuota.estado = 'PA'
                if pagar_hoy:
                    cuota.fecha_pago_real = hoy
                else:
                    cuota.fecha_pago_real = cuota.fecha_vencimiento
                cuota.metodo_pago = random.choice(['EF', 'TR', 'EF', 'EF'])  # Más efectivo
                cuota.monto_efectivo = cuota.monto_cuota if cuota.metodo_pago == 'EF' else Decimal('0')
                cuota.monto_transferencia = cuota.monto_cuota if cuota.metodo_pago == 'TR' else Decimal('0')
                cuota.save()
                print(f"     ✅ Cuota {cuota.numero_cuota}: PAGADA ${float(cuota.monto_cuota):,.0f} ({cuota.get_metodo_pago_display()})")
        
        cuotas_pend = prestamo.cuotas.filter(estado__in=['PE', 'PC']).count()
        print(f"     📊 Progreso: {prestamo.cuotas_pagadas}/{prestamo.cuotas_pactadas} | Pendientes: {cuotas_pend}")
    else:
        print(f"     ⏳ Sin pagos realizados (todas las cuotas pendientes)")
    
    return prestamo


# ==========================================
# EJECUTAR
# ==========================================

# Crear clientes de admin
print("\n--- Creando clientes de admin ---")
lista_clientes_admin = crear_clientes(clientes_admin, admin_user)

# Crear clientes de coco
print("\n--- Creando clientes de coco ---")
lista_clientes_coco = crear_clientes(clientes_coco, coco_user)

# Crear préstamos de admin
print("\n" + "=" * 50)
print("  CREANDO PRÉSTAMOS DE ADMIN")
print("=" * 50)
for config in prestamos_admin:
    cliente = lista_clientes_admin[config['cliente_idx']]
    crear_prestamo_con_pagos(cliente, config)

# Crear préstamos de coco
print("\n" + "=" * 50)
print("  CREANDO PRÉSTAMOS DE COCO")
print("=" * 50)
for config in prestamos_coco:
    cliente = lista_clientes_coco[config['cliente_idx']]
    crear_prestamo_con_pagos(cliente, config)

# ==========================================
# RESUMEN FINAL
# ==========================================
print("\n" + "=" * 60)
print("  RESUMEN FINAL")
print("=" * 60)
print(f"\n  Total usuarios: {User.objects.count()}")
print(f"  Total clientes: {Cliente.objects.count()}")
print(f"  Total préstamos: {Prestamo.objects.count()}")
print(f"  Préstamos activos: {Prestamo.objects.filter(estado='AC').count()}")
print(f"  Total cuotas: {Cuota.objects.count()}")
print(f"  Cuotas pagadas: {Cuota.objects.filter(estado='PA').count()}")
print(f"  Cuotas parciales: {Cuota.objects.filter(estado='PC').count()}")
print(f"  Cuotas pendientes: {Cuota.objects.filter(estado='PE').count()}")

# Resumen por usuario
for user in [admin_user, coco_user]:
    clientes = Cliente.objects.filter(usuario=user)
    prestamos = Prestamo.objects.filter(cliente__usuario=user, estado='AC')
    print(f"\n  👤 {user.username}:")
    print(f"     Clientes: {clientes.count()}")
    print(f"     Préstamos activos: {prestamos.count()}")
    for p in prestamos:
        print(f"       #{p.pk} {p.cliente.nombre_completo}: ${float(p.monto_total_a_pagar):,.0f} ({p.cuotas_pagadas}/{p.cuotas_pactadas} cuotas)")

print(f"\n{'=' * 60}")
print("  ✅ DATOS DE PRUEBA CARGADOS EXITOSAMENTE")
print(f"{'=' * 60}\n")
