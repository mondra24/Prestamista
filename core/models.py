"""
Modelos del Sistema de Gestión de Préstamos
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
from decimal import Decimal


class PerfilUsuario(models.Model):
    """Perfil extendido para usuarios con roles"""
    
    class Rol(models.TextChoices):
        ADMIN = 'AD', 'Administrador'
        COBRADOR = 'CO', 'Cobrador'
        SUPERVISOR = 'SU', 'Supervisor'
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name='Usuario'
    )
    rol = models.CharField(
        max_length=2,
        choices=Rol.choices,
        default=Rol.COBRADOR,
        verbose_name='Rol'
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Teléfono'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    
    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_rol_display()}"
    
    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN or self.user.is_superuser
    
    @property
    def es_supervisor(self):
        return self.rol in [self.Rol.ADMIN, self.Rol.SUPERVISOR] or self.user.is_superuser
    
    @property
    def puede_crear_usuarios(self):
        return self.es_admin
    
    @property
    def puede_ver_reportes(self):
        return self.rol in [self.Rol.ADMIN, self.Rol.SUPERVISOR] or self.user.is_superuser


@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    """Crea automáticamente un perfil cuando se crea un usuario"""
    if created:
        PerfilUsuario.objects.create(user=instance)


@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
    """Guarda el perfil cuando se guarda el usuario"""
    if hasattr(instance, 'perfil'):
        instance.perfil.save()


class Cliente(models.Model):
    """Modelo para gestionar clientes del sistema de préstamos"""
    
    class Categoria(models.TextChoices):
        EXCELENTE = 'EX', 'Excelente'
        REGULAR = 'RE', 'Regular'
        MOROSO = 'MO', 'Moroso'
        NUEVO = 'NU', 'Nuevo'
    
    class Estado(models.TextChoices):
        ACTIVO = 'AC', 'Activo'
        INACTIVO = 'IN', 'Inactivo'
    
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    apellido = models.CharField(max_length=100, verbose_name='Apellido')
    telefono = models.CharField(max_length=20, verbose_name='Teléfono')
    direccion = models.TextField(verbose_name='Dirección')
    categoria = models.CharField(
        max_length=2,
        choices=Categoria.choices,
        default=Categoria.NUEVO,
        verbose_name='Categoría'
    )
    estado = models.CharField(
        max_length=2,
        choices=Estado.choices,
        default=Estado.ACTIVO,
        verbose_name='Estado'
    )
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')
    notas = models.TextField(blank=True, null=True, verbose_name='Notas')
    
    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['apellido', 'nombre']
    
    def __str__(self):
        return f"{self.nombre} {self.apellido}"
    
    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"
    
    @property
    def tiene_prestamo_activo(self):
        """Verifica si el cliente tiene un préstamo activo"""
        return self.prestamos.filter(estado='AC').exists()
    
    @property
    def prestamo_activo(self):
        """Retorna el préstamo activo del cliente"""
        return self.prestamos.filter(estado='AC').first()
    
    def actualizar_categoria(self):
        """Actualiza la categoría del cliente basado en su historial de pagos"""
        prestamos_finalizados = self.prestamos.filter(estado='FI')
        if not prestamos_finalizados.exists():
            return
        
        # Calcular porcentaje de pagos a tiempo
        total_cuotas = 0
        cuotas_a_tiempo = 0
        for prestamo in prestamos_finalizados:
            for cuota in prestamo.cuotas.all():
                total_cuotas += 1
                if cuota.fecha_pago_real and cuota.fecha_pago_real <= cuota.fecha_vencimiento:
                    cuotas_a_tiempo += 1
        
        if total_cuotas > 0:
            porcentaje = (cuotas_a_tiempo / total_cuotas) * 100
            if porcentaje >= 95:
                self.categoria = self.Categoria.EXCELENTE
            elif porcentaje >= 70:
                self.categoria = self.Categoria.REGULAR
            else:
                self.categoria = self.Categoria.MOROSO
            self.save()


class Prestamo(models.Model):
    """Modelo para gestionar préstamos"""
    
    class Frecuencia(models.TextChoices):
        DIARIO = 'DI', 'Diario'
        SEMANAL = 'SE', 'Semanal'
        QUINCENAL = 'QU', 'Quincenal'
        MENSUAL = 'ME', 'Mensual'
    
    class Estado(models.TextChoices):
        ACTIVO = 'AC', 'Activo'
        FINALIZADO = 'FI', 'Finalizado'
        CANCELADO = 'CA', 'Cancelado'
        RENOVADO = 'RE', 'Renovado'
    
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='prestamos',
        verbose_name='Cliente'
    )
    monto_solicitado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],
        verbose_name='Monto Solicitado'
    )
    tasa_interes_porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name='Tasa de Interés (%)'
    )
    monto_total_a_pagar = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        verbose_name='Monto Total a Pagar'
    )
    cuotas_pactadas = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Número de Cuotas'
    )
    frecuencia = models.CharField(
        max_length=2,
        choices=Frecuencia.choices,
        default=Frecuencia.DIARIO,
        verbose_name='Frecuencia de Pago'
    )
    fecha_inicio = models.DateField(verbose_name='Fecha de Inicio')
    fecha_finalizacion = models.DateField(
        editable=False,
        null=True,
        verbose_name='Fecha de Finalización'
    )
    estado = models.CharField(
        max_length=2,
        choices=Estado.choices,
        default=Estado.ACTIVO,
        verbose_name='Estado'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    notas = models.TextField(blank=True, null=True, verbose_name='Notas')
    
    class Meta:
        verbose_name = 'Préstamo'
        verbose_name_plural = 'Préstamos'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"Préstamo #{self.pk} - {self.cliente}"
    
    def save(self, *args, **kwargs):
        # Calcular monto total a pagar
        interes = self.monto_solicitado * (self.tasa_interes_porcentaje / 100)
        self.monto_total_a_pagar = self.monto_solicitado + interes
        
        # Calcular fecha de finalización
        self.fecha_finalizacion = self.calcular_fecha_finalizacion()
        
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Generar cuotas automáticamente solo si es nuevo
        if is_new:
            self.generar_cuotas()
    
    def calcular_fecha_finalizacion(self):
        """Calcula la fecha de finalización del préstamo"""
        fecha = self.fecha_inicio
        dias_agregados = 0
        
        while dias_agregados < self.cuotas_pactadas:
            if self.frecuencia == self.Frecuencia.DIARIO:
                fecha += timedelta(days=1)
                # Saltar domingos para préstamos diarios
                if fecha.weekday() == 6:  # Domingo
                    continue
            elif self.frecuencia == self.Frecuencia.SEMANAL:
                fecha += timedelta(weeks=1)
            elif self.frecuencia == self.Frecuencia.QUINCENAL:
                fecha += timedelta(days=15)
            elif self.frecuencia == self.Frecuencia.MENSUAL:
                fecha += timedelta(days=30)
            dias_agregados += 1
        
        return fecha
    
    def generar_cuotas(self):
        """Genera todas las cuotas del préstamo automáticamente"""
        monto_cuota = self.monto_total_a_pagar / self.cuotas_pactadas
        fecha_vencimiento = self.fecha_inicio
        
        for numero in range(1, self.cuotas_pactadas + 1):
            # Calcular fecha de vencimiento según frecuencia
            if self.frecuencia == self.Frecuencia.DIARIO:
                fecha_vencimiento += timedelta(days=1)
                # Saltar domingos
                while fecha_vencimiento.weekday() == 6:
                    fecha_vencimiento += timedelta(days=1)
            elif self.frecuencia == self.Frecuencia.SEMANAL:
                fecha_vencimiento += timedelta(weeks=1)
            elif self.frecuencia == self.Frecuencia.QUINCENAL:
                fecha_vencimiento += timedelta(days=15)
            elif self.frecuencia == self.Frecuencia.MENSUAL:
                fecha_vencimiento += timedelta(days=30)
            
            Cuota.objects.create(
                prestamo=self,
                numero_cuota=numero,
                monto_cuota=round(monto_cuota, 2),
                fecha_vencimiento=fecha_vencimiento
            )
    
    @property
    def monto_pagado(self):
        """Suma de todos los pagos realizados"""
        return self.cuotas.filter(
            estado__in=['PA', 'PC']
        ).aggregate(
            total=models.Sum('monto_pagado')
        )['total'] or Decimal('0.00')
    
    @property
    def monto_pendiente(self):
        """Monto pendiente por pagar"""
        return self.monto_total_a_pagar - self.monto_pagado
    
    @property
    def cuotas_pagadas(self):
        """Número de cuotas completamente pagadas"""
        return self.cuotas.filter(estado='PA').count()
    
    @property
    def progreso_porcentaje(self):
        """Porcentaje de progreso del préstamo"""
        if self.cuotas_pactadas == 0:
            return 0
        return int((self.cuotas_pagadas / self.cuotas_pactadas) * 100)
    
    @property
    def proxima_cuota(self):
        """Retorna la próxima cuota pendiente"""
        return self.cuotas.filter(estado='PE').order_by('numero_cuota').first()
    
    def liquidar_prestamo(self):
        """Liquida el préstamo marcando todas las cuotas como pagadas"""
        self.cuotas.filter(estado='PE').update(
            estado='PA',
            fecha_pago_real=timezone.now().date()
        )
        self.estado = self.Estado.FINALIZADO
        self.save()
        self.cliente.actualizar_categoria()
    
    def calcular_saldo_para_renovacion(self):
        """Calcula el saldo pendiente para renovación"""
        return self.monto_pendiente
    
    @classmethod
    def renovar_prestamo(cls, prestamo_anterior, nuevo_monto, nueva_tasa, nuevas_cuotas, nueva_frecuencia):
        """
        Renueva un préstamo existente.
        El saldo pendiente se suma al nuevo capital.
        """
        saldo_pendiente = prestamo_anterior.calcular_saldo_para_renovacion()
        
        # Cancelar todas las cuotas pendientes del préstamo anterior
        # Actualizamos cada cuota individualmente para evitar problemas con F()
        cuotas_pendientes = prestamo_anterior.cuotas.filter(estado__in=['PE', 'PC'])
        for cuota in cuotas_pendientes:
            cuota.estado = 'PA'
            cuota.fecha_pago_real = timezone.now().date()
            cuota.monto_pagado = cuota.monto_cuota
            cuota.save()
        
        # Marcar préstamo anterior como renovado
        prestamo_anterior.estado = cls.Estado.RENOVADO
        prestamo_anterior.save(update_fields=['estado'])
        
        # Crear nuevo préstamo con capital = nuevo_monto + saldo_pendiente
        nuevo_capital = nuevo_monto + saldo_pendiente
        
        nuevo_prestamo = cls.objects.create(
            cliente=prestamo_anterior.cliente,
            monto_solicitado=nuevo_capital,
            tasa_interes_porcentaje=nueva_tasa,
            cuotas_pactadas=nuevas_cuotas,
            frecuencia=nueva_frecuencia,
            fecha_inicio=timezone.now().date(),
            notas=f"Renovación del préstamo #{prestamo_anterior.pk}. Saldo anterior: ${saldo_pendiente}"
        )
        
        return nuevo_prestamo


class Cuota(models.Model):
    """Modelo para gestionar las cuotas de un préstamo"""
    
    class Estado(models.TextChoices):
        PENDIENTE = 'PE', 'Pendiente'
        PAGADO = 'PA', 'Pagado'
        PARCIAL = 'PC', 'Pago Parcial'
    
    prestamo = models.ForeignKey(
        Prestamo,
        on_delete=models.CASCADE,
        related_name='cuotas',
        verbose_name='Préstamo'
    )
    numero_cuota = models.PositiveIntegerField(verbose_name='Número de Cuota')
    monto_cuota = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Monto de Cuota'
    )
    monto_pagado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Monto Pagado'
    )
    fecha_vencimiento = models.DateField(verbose_name='Fecha de Vencimiento')
    estado = models.CharField(
        max_length=2,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        verbose_name='Estado'
    )
    fecha_pago_real = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Pago Real'
    )
    
    class Meta:
        verbose_name = 'Cuota'
        verbose_name_plural = 'Cuotas'
        ordering = ['prestamo', 'numero_cuota']
        unique_together = ['prestamo', 'numero_cuota']
    
    def __str__(self):
        return f"Cuota {self.numero_cuota}/{self.prestamo.cuotas_pactadas} - {self.prestamo.cliente}"
    
    @property
    def monto_restante(self):
        """Monto restante por pagar de esta cuota"""
        return self.monto_cuota - self.monto_pagado
    
    @property
    def esta_vencida(self):
        """Verifica si la cuota está vencida"""
        if self.estado == self.Estado.PAGADO:
            return False
        return self.fecha_vencimiento < timezone.now().date()
    
    @property
    def dias_vencida(self):
        """Días de vencimiento de la cuota"""
        if not self.esta_vencida:
            return 0
        return (timezone.now().date() - self.fecha_vencimiento).days
    
    def registrar_pago(self, monto=None, accion_restante='ignorar', fecha_especial=None):
        """
        Registra un pago en la cuota.
        Si no se especifica monto, se paga el total.
        
        accion_restante puede ser:
        - 'ignorar': El monto restante queda pendiente en esta cuota
        - 'proxima': Suma el restante a la próxima cuota
        - 'especial': Crea una cuota especial en fecha_especial con el monto restante
        """
        if monto is None:
            monto = self.monto_restante
        
        monto = Decimal(str(monto))
        monto_restante_anterior = self.monto_restante
        
        self.monto_pagado += monto
        self.fecha_pago_real = timezone.now().date()
        
        if self.monto_pagado >= self.monto_cuota:
            self.estado = self.Estado.PAGADO
            self.monto_pagado = self.monto_cuota  # Evitar sobrepagos
        else:
            self.estado = self.Estado.PARCIAL
        
        self.save()
        
        # Calcular lo que quedó sin pagar de esta cuota
        restante = monto_restante_anterior - monto
        
        # Manejar el monto restante según la acción elegida
        if restante > 0 and accion_restante == 'proxima':
            # Sumar a la próxima cuota pendiente
            proxima = self.prestamo.cuotas.filter(
                estado='PE',
                numero_cuota__gt=self.numero_cuota
            ).order_by('numero_cuota').first()
            
            if proxima:
                proxima.monto_cuota += restante
                proxima.save()
                # Marcar esta cuota como pagada ya que se transfirió el restante
                self.estado = self.Estado.PAGADO
                self.save()
        
        elif restante > 0 and accion_restante == 'especial' and fecha_especial:
            # Crear cuota especial
            ultimo_numero = self.prestamo.cuotas.aggregate(
                max_num=models.Max('numero_cuota')
            )['max_num'] or 0
            
            Cuota.objects.create(
                prestamo=self.prestamo,
                numero_cuota=ultimo_numero + 1,
                monto_cuota=restante,
                fecha_vencimiento=fecha_especial,
                estado=self.Estado.PENDIENTE
            )
            # Actualizar número de cuotas pactadas
            self.prestamo.cuotas_pactadas = ultimo_numero + 1
            self.prestamo.save(update_fields=['cuotas_pactadas'])
            # Marcar esta cuota como pagada
            self.estado = self.Estado.PAGADO
            self.save()
        
        # Verificar si el préstamo está completamente pagado
        prestamo = self.prestamo
        if not prestamo.cuotas.filter(estado__in=['PE', 'PC']).exists():
            prestamo.estado = Prestamo.Estado.FINALIZADO
            prestamo.save()
            prestamo.cliente.actualizar_categoria()
        
        return self

