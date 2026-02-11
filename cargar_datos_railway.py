"""
Script para cargar datos de prueba en PostgreSQL de Railway
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prestamos_config.settings')
os.environ['DATABASE_URL'] = 'postgresql://postgres:iZwZIFPPHThinbHTlGSAOrQKuvlIXlAK@metro.proxy.rlwy.net:17571/railway'

django.setup()

from django.contrib.auth.models import User
from core.models import Cliente, PerfilUsuario
from decimal import Decimal
import random

print("Conectando a PostgreSQL de Railway...")

# Crear usuarios
usuarios_data = [
    ('gonza', '123'),
    ('chacho', '123'),
    ('coco', '123'),
]

print("\n=== CREANDO USUARIOS ===")
for username, password in usuarios_data:
    user, created = User.objects.get_or_create(username=username)
    user.set_password(password)
    user.save()
    PerfilUsuario.objects.get_or_create(user=user)
    status = "CREADO" if created else "ACTUALIZADO"
    print(f"  {username}: {status}")

# Clientes de prueba para cada usuario
clientes_data = [
    # Para gonza
    [('Juan', 'Perez'), ('Maria', 'Garcia'), ('Carlos', 'Lopez'), ('Ana', 'Martinez'), ('Pedro', 'Gomez')],
    # Para chacho
    [('Laura', 'Sanchez'), ('Diego', 'Rodriguez'), ('Sofia', 'Fernandez'), ('Pablo', 'Diaz'), ('Lucia', 'Torres')],
    # Para coco
    [('Martin', 'Ruiz'), ('Valentina', 'Flores'), ('Nicolas', 'Castro'), ('Camila', 'Morales'), ('Mateo', 'Herrera')],
]

telefonos = ['3511234567', '3512345678', '3513456789', '3514567890', '3515678901']
direcciones = ['Av. Colon 1234', 'San Martin 567', 'Dean Funes 890', 'Chacabuco 123', 'Velez Sarsfield 456']

print("\n=== CREANDO CLIENTES ===")
for idx, (username, _) in enumerate(usuarios_data):
    user = User.objects.get(username=username)
    print(f"\nClientes para {username}:")
    for i, (nombre, apellido) in enumerate(clientes_data[idx]):
        # Verificar si ya existe por nombre y apellido
        if not Cliente.objects.filter(nombre=nombre, apellido=apellido).exists():
            Cliente.objects.create(
                nombre=nombre,
                apellido=apellido,
                telefono=telefonos[i % len(telefonos)],
                direccion=direcciones[i % len(direcciones)],
                limite_credito=Decimal(random.choice([50000, 100000, 150000, 200000])),
            )
            print(f"  + {nombre} {apellido}")
        else:
            print(f"  - {nombre} {apellido} ya existe")

print("\n=== RESUMEN ===")
print(f"Total usuarios: {User.objects.count()}")
print(f"Total clientes: {Cliente.objects.count()}")

print("\n¡Listo! Ya puedes probar el sistema.")
