"""
Script para cargar datos de prueba en el sistema PrestaFácil
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prestamos_config.settings')
django.setup()

from core.models import Cliente, Prestamo
from datetime import date
from decimal import Decimal

def cargar_datos():
    """Carga datos de prueba en la base de datos"""
    
    # Clientes de prueba
    clientes_data = [
        {
            'nombre': 'Juan',
            'apellido': 'Perez',
            'telefono': '3001234567',
            'direccion': 'Calle 10 #20-30, Barrio Centro',
            'categoria': 'EX'
        },
        {
            'nombre': 'Maria',
            'apellido': 'Garcia',
            'telefono': '3009876543',
            'direccion': 'Carrera 5 #15-25, Barrio Norte',
            'categoria': 'NU'
        },
        {
            'nombre': 'Carlos',
            'apellido': 'Rodriguez',
            'telefono': '3205551234',
            'direccion': 'Av. Principal #45-60, Centro',
            'categoria': 'RE'
        },
        {
            'nombre': 'Ana',
            'apellido': 'Martinez',
            'telefono': '3181112233',
            'direccion': 'Calle 20 #10-15, Barrio Sur',
            'categoria': 'NU'
        },
    ]
    
    print("Cargando datos de prueba...")
    print("-" * 40)
    
    for data in clientes_data:
        cliente, created = Cliente.objects.get_or_create(
            telefono=data['telefono'],
            defaults=data
        )
        
        if created:
            print(f"+ Cliente creado: {cliente.nombre_completo}")
            
            # Crear prestamo para el cliente
            prestamo = Prestamo.objects.create(
                cliente=cliente,
                monto_solicitado=Decimal('500000'),
                tasa_interes_porcentaje=Decimal('20'),
                cuotas_pactadas=20,
                frecuencia='DI',
                fecha_inicio=date.today()
            )
            print(f"  -> Prestamo #{prestamo.pk} creado: ${prestamo.monto_total_a_pagar} en 20 cuotas")
        else:
            print(f"= Cliente existente: {cliente.nombre_completo}")
    
    print("-" * 40)
    print(f"Total clientes: {Cliente.objects.count()}")
    print(f"Total prestamos: {Prestamo.objects.count()}")
    print("\nDatos de prueba cargados correctamente!")

if __name__ == '__main__':
    cargar_datos()
