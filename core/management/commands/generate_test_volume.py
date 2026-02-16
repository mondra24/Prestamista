"""
Comando para generar datos de volumen para testing.
Crea ~400 clientes con préstamos activos distribuidos entre los usuarios existentes.

Uso:
    python manage.py generate_test_volume
    python manage.py generate_test_volume --clientes 400
    python manage.py generate_test_volume --clientes 400 --limpiar
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import date, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Genera datos de volumen para testing (clientes, préstamos, cuotas)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clientes',
            type=int,
            default=400,
            help='Cantidad de clientes a crear (default: 400)'
        )
        parser.add_argument(
            '--limpiar',
            action='store_true',
            help='Eliminar datos de test anteriores antes de crear nuevos'
        )

    def handle(self, *args, **options):
        from core.models import (
            Cliente, Prestamo, Cuota, RutaCobro, TipoNegocio,
            ConfiguracionCredito, ConfiguracionMora, PerfilUsuario
        )

        cantidad_clientes = options['clientes']

        # ==================== LIMPIEZA OPCIONAL ====================
        if options['limpiar']:
            self.stdout.write('Eliminando datos de test anteriores...')
            # Solo eliminar clientes cuyo nombre empieza con "Test_"
            clientes_test = Cliente.objects.filter(nombre__startswith='Test_')
            count = clientes_test.count()
            # Los préstamos y cuotas se eliminan en cascada
            clientes_test.delete()
            self.stdout.write(f'   Eliminados {count} clientes de test')

        # ==================== VERIFICAR USUARIOS ====================
        usuarios_cobradores = ['nacho', 'martin', 'gonza', 'chacho', 'coco']
        usuarios = []

        for username in usuarios_cobradores:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': username.capitalize(),
                    'last_name': 'Test',
                    'is_active': True,
                }
            )
            if created:
                user.set_password('123')
                user.save()
                PerfilUsuario.objects.get_or_create(user=user)
                self.stdout.write(f'   Creado usuario: {username}')
            usuarios.append(user)

        # ==================== DATOS BASE ====================
        self.stdout.write('Creando datos base...')

        # Rutas de cobro
        rutas_nombres = ['Centro', 'Norte', 'Sur', 'Oriente', 'Poniente']
        rutas = []
        for i, nombre in enumerate(rutas_nombres):
            ruta, _ = RutaCobro.objects.get_or_create(
                nombre=nombre,
                defaults={'orden': i + 1, 'color': f'#{random.randint(0, 0xFFFFFF):06x}'}
            )
            rutas.append(ruta)

        # Tipos de negocio
        tipos_nombres = ['Tienda', 'Restaurante', 'Venta Ambulante', 'Oficina', 'Empleado', 'Kiosco', 'Taller']
        tipos = []
        for i, nombre in enumerate(tipos_nombres):
            tipo, _ = TipoNegocio.objects.get_or_create(
                nombre=nombre,
                defaults={'orden': i + 1, 'limite_credito_sugerido': Decimal(str(random.choice([100000, 200000, 500000])))}
            )
            tipos.append(tipo)

        # Configuración de crédito
        for cat in ['EX', 'RE', 'MO', 'NU']:
            ConfiguracionCredito.objects.get_or_create(
                categoria=cat,
                defaults={
                    'limite_maximo': Decimal('0.00'),
                    'porcentaje_sobre_deuda': Decimal('30'),
                    'puede_renovar_con_deuda': True,
                    'dias_minimos_para_renovar': 7,
                }
            )

        # Configuración de mora
        ConfiguracionMora.objects.get_or_create(
            nombre='Configuración Principal',
            defaults={
                'porcentaje_diario': Decimal('0.50'),
                'dias_gracia': 3,
                'aplicar_automaticamente': True,
                'activo': True,
            }
        )

        # ==================== NOMBRES DE PRUEBA ====================
        nombres = [
            'Juan', 'María', 'Carlos', 'Ana', 'Pedro', 'Laura', 'Diego', 'Sofía',
            'Mateo', 'Valentina', 'Nicolás', 'Camila', 'Martín', 'Lucía', 'Pablo',
            'Isabella', 'Santiago', 'Florencia', 'Tomás', 'Catalina', 'Facundo',
            'Agustina', 'Joaquín', 'Julieta', 'Lautaro', 'Micaela', 'Bautista',
            'Delfina', 'Thiago', 'Morena', 'Benjamín', 'Abril', 'Lucas', 'Mía',
            'Emiliano', 'Alma', 'Maximiliano', 'Renata', 'Franco', 'Olivia',
        ]
        apellidos = [
            'García', 'Rodríguez', 'López', 'Martínez', 'González', 'Pérez',
            'Sánchez', 'Ramírez', 'Torres', 'Flores', 'Rivera', 'Gómez',
            'Díaz', 'Cruz', 'Morales', 'Reyes', 'Gutiérrez', 'Ortiz',
            'Hernández', 'Castillo', 'Romero', 'Álvarez', 'Ruiz', 'Vargas',
            'Mendoza', 'Acosta', 'Silva', 'Castro', 'Fernández', 'Molina',
            'Quiroga', 'Aguirre', 'Cabrera', 'Medina', 'Rojas', 'Vega',
            'Suárez', 'Navarro', 'Ramos', 'Domínguez',
        ]
        calles = [
            'Av. Colón', 'San Martín', 'Dean Funes', 'Chacabuco', 'Vélez Sársfield',
            'Av. General Paz', 'Bv. San Juan', 'Maipú', 'Rivadavia', 'Belgrano',
            'Av. Hipólito Yrigoyen', 'Santa Rosa', 'Obispo Trejo', 'Caseros',
            'Duarte Quirós', 'La Cañada', '27 de Abril', 'Ituzaingó', 'Tucumán',
            'Av. Marcelo T. de Alvear',
        ]
        categorias = ['EX', 'EX', 'RE', 'RE', 'RE', 'NU', 'NU', 'MO']  # Distribución realista
        frecuencias = ['DI', 'DI', 'DI', 'SE', 'SE', 'QU', 'ME']  # Más diarios

        # ==================== GENERAR CLIENTES Y PRÉSTAMOS ====================
        self.stdout.write(f'\nGenerando {cantidad_clientes} clientes con préstamos...\n')

        hoy = date.today()
        clientes_creados = 0
        prestamos_creados = 0
        cuotas_creadas = 0
        pagos_registrados = 0

        for i in range(cantidad_clientes):
            # Datos del cliente
            nombre = random.choice(nombres)
            apellido = random.choice(apellidos)
            usuario = random.choice(usuarios)
            ruta = random.choice(rutas)
            tipo = random.choice(tipos)
            categoria = random.choice(categorias)

            cliente = Cliente.objects.create(
                nombre=f'Test_{nombre}',
                apellido=f'{apellido}_{i}',
                telefono=f'351{random.randint(1000000, 9999999)}',
                direccion=f'{random.choice(calles)} {random.randint(100, 9999)}',
                categoria=categoria,
                tipo_negocio=tipo,
                ruta=ruta,
                limite_credito=Decimal(str(random.choice([0, 50000, 100000, 200000, 500000]))),
                usuario=usuario,
            )
            clientes_creados += 1

            # ==================== CREAR PRÉSTAMOS ====================
            # 70% tiene 1 préstamo activo, 20% tiene 1 activo + 1 finalizado, 10% solo finalizado
            chance = random.random()

            if chance < 0.7:
                # 1 préstamo activo
                p = self._crear_prestamo_activo(cliente, hoy, frecuencias)
                prestamos_creados += 1
                cuotas_creadas += p.cuotas.count()

                # Pagar algunas cuotas vencidas
                pagos = self._pagar_cuotas_vencidas(p, usuario, hoy)
                pagos_registrados += pagos

            elif chance < 0.9:
                # 1 finalizado + 1 activo
                p_fin = self._crear_prestamo_finalizado(cliente, hoy)
                prestamos_creados += 1
                cuotas_creadas += p_fin.cuotas.count()

                p_act = self._crear_prestamo_activo(cliente, hoy, frecuencias)
                prestamos_creados += 1
                cuotas_creadas += p_act.cuotas.count()

                pagos = self._pagar_cuotas_vencidas(p_act, usuario, hoy)
                pagos_registrados += pagos
            else:
                # Solo finalizado
                p_fin = self._crear_prestamo_finalizado(cliente, hoy)
                prestamos_creados += 1
                cuotas_creadas += p_fin.cuotas.count()

            # Progreso cada 50 clientes
            if (i + 1) % 50 == 0:
                self.stdout.write(f'   Progreso: {i + 1}/{cantidad_clientes} clientes...')

        # ==================== RESUMEN ====================
        self.stdout.write(self.style.SUCCESS(f'\n{"="*50}'))
        self.stdout.write(self.style.SUCCESS(f'  DATOS DE VOLUMEN GENERADOS'))
        self.stdout.write(self.style.SUCCESS(f'{"="*50}'))
        self.stdout.write(f'  Clientes creados:   {clientes_creados}')
        self.stdout.write(f'  Préstamos creados:  {prestamos_creados}')
        self.stdout.write(f'  Cuotas generadas:   {cuotas_creadas}')
        self.stdout.write(f'  Pagos registrados:  {pagos_registrados}')
        self.stdout.write(f'')
        self.stdout.write(f'  TOTALES EN BD:')
        self.stdout.write(f'  Clientes total:     {Cliente.objects.count()}')

        from core.models import Prestamo, Cuota
        self.stdout.write(f'  Préstamos total:    {Prestamo.objects.count()}')
        self.stdout.write(f'  Cuotas total:       {Cuota.objects.count()}')
        self.stdout.write(f'')

        # Distribución por usuario
        self.stdout.write(f'  DISTRIBUCIÓN POR USUARIO:')
        for u in usuarios:
            count = Cliente.objects.filter(usuario=u).count()
            self.stdout.write(f'    {u.username}: {count} clientes')

        self.stdout.write(self.style.SUCCESS(f'\n  ¡Listo! Ahora podés ejecutar los tests de carga.'))

    def _crear_prestamo_activo(self, cliente, hoy, frecuencias):
        """Crea un préstamo activo con fechas variadas"""
        from core.models import Prestamo

        dias_atras = random.randint(3, 45)  # Variación de fechas para tener vencidas
        fecha_inicio = hoy - timedelta(days=dias_atras)
        frecuencia = random.choice(frecuencias)

        # Ajustar cuotas según frecuencia
        if frecuencia == 'DI':
            cuotas = random.choice([15, 20, 25, 30])
        elif frecuencia == 'SE':
            cuotas = random.choice([4, 8, 12])
        elif frecuencia == 'QU':
            cuotas = random.choice([4, 6, 8])
        else:  # ME
            cuotas = random.choice([3, 6, 12])

        monto = Decimal(str(random.choice([
            5000, 10000, 15000, 20000, 30000, 50000,
            75000, 100000, 150000, 200000, 300000,
        ])))
        tasa = Decimal(str(random.choice([5, 8, 10, 12, 15, 20])))

        return Prestamo.objects.create(
            cliente=cliente,
            monto_solicitado=monto,
            tasa_interes_porcentaje=tasa,
            cuotas_pactadas=cuotas,
            frecuencia=frecuencia,
            fecha_inicio=fecha_inicio,
        )

    def _crear_prestamo_finalizado(self, cliente, hoy):
        """Crea un préstamo ya completamente pagado"""
        from core.models import Prestamo

        dias_atras = random.randint(60, 180)
        fecha_inicio = hoy - timedelta(days=dias_atras)

        monto = Decimal(str(random.choice([5000, 10000, 20000, 50000])))

        prestamo = Prestamo.objects.create(
            cliente=cliente,
            monto_solicitado=monto,
            tasa_interes_porcentaje=Decimal('10'),
            cuotas_pactadas=random.choice([10, 15, 20]),
            frecuencia='DI',
            fecha_inicio=fecha_inicio,
        )

        # Pagar todas las cuotas
        for cuota in prestamo.cuotas.all():
            cuota.estado = 'PA'
            cuota.monto_pagado = cuota.monto_cuota
            cuota.fecha_pago_real = cuota.fecha_vencimiento
            cuota.metodo_pago = random.choice(['EF', 'TR', 'MX'])
            if cuota.metodo_pago == 'EF':
                cuota.monto_efectivo = cuota.monto_cuota
            elif cuota.metodo_pago == 'TR':
                cuota.monto_transferencia = cuota.monto_cuota
            else:
                mitad = cuota.monto_cuota / 2
                cuota.monto_efectivo = mitad
                cuota.monto_transferencia = cuota.monto_cuota - mitad
            cuota.save()

        prestamo.estado = 'FI'
        prestamo.save(update_fields=['estado'])
        return prestamo

    def _pagar_cuotas_vencidas(self, prestamo, cobrador, hoy):
        """Paga algunas cuotas vencidas del préstamo (simula uso real)"""
        cuotas_vencidas = prestamo.cuotas.filter(
            estado='PE',
            fecha_vencimiento__lt=hoy
        ).order_by('numero_cuota')

        # Pagar entre 50-90% de las cuotas vencidas (dejar algunas sin pagar para mora)
        count = cuotas_vencidas.count()
        if count == 0:
            return 0

        cuotas_a_pagar = max(1, int(count * random.uniform(0.5, 0.9)))
        pagos = 0

        for cuota in cuotas_vencidas[:cuotas_a_pagar]:
            metodo = random.choice(['EF', 'EF', 'EF', 'TR', 'MX'])  # Más efectivo

            # Algunos pagos parciales (10% de probabilidad)
            if random.random() < 0.1:
                monto = cuota.monto_cuota * Decimal(str(random.uniform(0.3, 0.8)))
                monto = monto.quantize(Decimal('1'))
            else:
                monto = cuota.monto_cuota

            kwargs = {
                'monto': monto,
                'metodo_pago': metodo,
                'cobrador': cobrador,
            }

            if metodo == 'TR':
                kwargs['monto_transferencia'] = monto
                kwargs['referencia_transferencia'] = f'TR-TEST-{random.randint(1000, 9999)}'
            elif metodo == 'MX':
                mitad = monto / 2
                kwargs['monto_efectivo'] = mitad.quantize(Decimal('1'))
                kwargs['monto_transferencia'] = (monto - mitad).quantize(Decimal('1'))
                kwargs['referencia_transferencia'] = f'MX-TEST-{random.randint(1000, 9999)}'

            try:
                cuota.registrar_pago(**kwargs)
                pagos += 1
            except Exception as e:
                pass  # Ignorar errores en datos de prueba

        return pagos
