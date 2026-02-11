"""
Comando para asignar clientes a usuarios.
Cada usuario tendrá su lista separada de clientes.
Solo se ejecuta si no hay clientes con usuario asignado.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Asigna clientes existentes a usuarios o crea nuevos clientes por usuario'

    def handle(self, *args, **options):
        from core.models import Cliente, PerfilUsuario
        
        # Verificar si ya hay clientes con usuario asignado - NO hacer nada
        if Cliente.objects.filter(usuario__isnull=False).exists():
            self.stdout.write(self.style.SUCCESS(
                'Ya existen clientes asignados a usuarios. Saltando...'
            ))
            return
        
        self.stdout.write('=== ASIGNANDO CLIENTES A USUARIOS ===\n')
        
        # Usuarios a crear/actualizar (sin admin)
        usuarios_data = [
            ('gonza', '123'),
            ('chacho', '123'),
            ('coco', '123'),
        ]
        
        # Clientes para cada usuario
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
        
        # Crear usuarios
        self.stdout.write('Creando/actualizando usuarios...')
        for username, password in usuarios_data:
            user, created = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.save()
            PerfilUsuario.objects.get_or_create(user=user)
            status = "CREADO" if created else "ACTUALIZADO"
            self.stdout.write(f'  {username}: {status}')
        
        # Crear/asignar clientes
        self.stdout.write('\nAsignando clientes a usuarios...')
        for idx, (username, _) in enumerate(usuarios_data):
            user = User.objects.get(username=username)
            self.stdout.write(f'\nClientes para {username}:')
            
            for i, (nombre, apellido) in enumerate(clientes_data[idx]):
                cliente = Cliente.objects.filter(nombre=nombre, apellido=apellido).first()
                
                if cliente:
                    # Asignar usuario si el cliente ya existe
                    cliente.usuario = user
                    cliente.save()
                    self.stdout.write(f'  ~ {nombre} {apellido} (asignado)')
                else:
                    # Crear cliente nuevo
                    Cliente.objects.create(
                        nombre=nombre,
                        apellido=apellido,
                        telefono=telefonos[i % len(telefonos)],
                        direccion=direcciones[i % len(direcciones)],
                        limite_credito=Decimal(random.choice([50000, 100000, 150000, 200000])),
                        usuario=user
                    )
                    self.stdout.write(f'  + {nombre} {apellido} (creado)')
        
        self.stdout.write(self.style.SUCCESS(
            f'\n¡Listo! Total usuarios: {User.objects.count()}, Total clientes: {Cliente.objects.count()}'
        ))
