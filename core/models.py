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


class RutaCobro(models.Model):
    """Modelo para categorizar rutas de cobro en la planilla"""
    nombre = models.CharField(max_length=100, verbose_name='Nombre de la Ruta')
    descripcion = models.TextField(blank=True, null=True, verbose_name='Descripción')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden de Prioridad')
    color = models.CharField(max_length=7, default='#0d6efd', verbose_name='Color', help_text='Color en formato hexadecimal')
    activa = models.BooleanField(default=True, verbose_name='Activa')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    
    class Meta:
        verbose_name = 'Ruta de Cobro'
        verbose_name_plural = 'Rutas de Cobro'
        ordering = ['orden', 'nombre']
    
    def __str__(self):
        return self.nombre


class TipoNegocio(models.Model):
    """Tipos de negocio/comercio administrables desde el admin"""
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    descripcion = models.TextField(blank=True, null=True, verbose_name='Descripción')
    limite_credito_sugerido = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Límite de Crédito Sugerido',
        help_text='Límite sugerido para este tipo de negocio (0 = sin límite)'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden')
    
    class Meta:
        verbose_name = 'Tipo de Negocio'
        verbose_name_plural = 'Tipos de Negocio'
        ordering = ['orden', 'nombre']
    
    def __str__(self):
        return self.nombre


class ConfiguracionCredito(models.Model):
    """Configuración de límites de crédito por categoría de cliente"""
    
    CATEGORIA_CHOICES = [
        ('EX', 'Excelente'),
        ('RE', 'Regular'),
        ('MO', 'Moroso'),
        ('NU', 'Nuevo'),
    ]
    
    categoria = models.CharField(
        max_length=2,
        choices=CATEGORIA_CHOICES,
        unique=True,
        verbose_name='Categoría de Cliente'
    )
    limite_maximo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Límite Máximo de Préstamo',
        help_text='Monto máximo que se puede prestar a esta categoría (0 = sin límite)'
    )
    porcentaje_sobre_deuda = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('500.00'))],
        verbose_name='% Adicional sobre Deuda',
        help_text='Porcentaje adicional que se puede prestar sobre deuda actual. Ej: 50 = hasta 50% más de lo que debe'
    )
    puede_renovar_con_deuda = models.BooleanField(
        default=True,
        verbose_name='Puede Renovar con Deuda',
        help_text='Si puede renovar préstamos con saldo pendiente'
    )
    dias_minimos_para_renovar = models.PositiveIntegerField(
        default=0,
        verbose_name='Días Mínimos para Renovar',
        help_text='Días mínimos que debe haber pagado antes de renovar (0 = sin restricción)'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    
    class Meta:
        verbose_name = 'Configuración de Crédito'
        verbose_name_plural = 'Configuraciones de Crédito'
        ordering = ['categoria']
    
    def __str__(self):
        return f"Config. {self.get_categoria_display()}"
    
    @classmethod
    def obtener_config(cls, categoria):
        """Obtiene la configuración para una categoría específica"""
        try:
            return cls.objects.get(categoria=categoria, activo=True)
        except cls.DoesNotExist:
            return None


class ColumnaPlanilla(models.Model):
    """Columnas personalizables para la planilla de cobros"""
    
    COLUMNAS_DISPONIBLES = [
        ('numero', '# (Número de fila)'),
        ('nombre_cliente', 'Nombre del Cliente'),
        ('telefono', 'Teléfono'),
        ('direccion', 'Dirección'),
        ('categoria', 'Categoría del Cliente'),
        ('tipo_negocio', 'Tipo de Negocio'),
        ('ruta', 'Ruta de Cobro'),
        ('dia_pago', 'Día de Pago Preferido'),
        ('cuota_actual', 'Número de Cuota (X/N)'),
        ('monto_cuota', 'Monto de Cuota'),
        ('fecha_vencimiento', 'Fecha de Vencimiento'),
        ('fecha_cobro', 'Fecha de Cobro'),
        ('monto_solicitado', 'Monto Solicitado'),
        ('monto_total', 'Total a Pagar'),
        ('monto_pendiente', 'Saldo Pendiente'),
        ('fecha_fin_prestamo', 'Fecha Finalización Est.'),
        ('prestamo_pagado', 'Préstamo Pagado'),
        ('es_renovacion', 'Es Renovación'),
        ('espacio_cobrado', 'Espacio para Cobrado'),
        ('espacio_firma', 'Espacio para Firma'),
        ('espacio_notas', 'Espacio para Notas'),
    ]
    
    nombre_columna = models.CharField(
        max_length=50,
        choices=COLUMNAS_DISPONIBLES,
        verbose_name='Columna'
    )
    titulo_personalizado = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Título Personalizado',
        help_text='Dejar vacío para usar el título por defecto'
    )
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden')
    ancho = models.CharField(
        max_length=10,
        default='auto',
        verbose_name='Ancho',
        help_text='Ej: auto, 100px, 15%'
    )
    activa = models.BooleanField(default=True, verbose_name='Activa')
    
    class Meta:
        verbose_name = 'Columna de Planilla'
        verbose_name_plural = 'Columnas de Planilla'
        ordering = ['orden']
    
    def __str__(self):
        return self.get_nombre_columna_display()
    
    @property
    def titulo(self):
        return self.titulo_personalizado or self.get_nombre_columna_display()
    
    @classmethod
    def obtener_columnas_activas(cls):
        return cls.objects.filter(activa=True).order_by('orden')


class ConfiguracionPlanilla(models.Model):
    """Configuración general de la planilla"""
    nombre = models.CharField(max_length=100, default='Planilla Principal', verbose_name='Nombre')
    titulo_reporte = models.CharField(max_length=200, default='PLANILLA DE COBROS', verbose_name='Título del Reporte')
    subtitulo = models.CharField(max_length=200, blank=True, null=True, verbose_name='Subtítulo')
    mostrar_logo = models.BooleanField(default=True, verbose_name='Mostrar Logo')
    mostrar_fecha = models.BooleanField(default=True, verbose_name='Mostrar Fecha')
    mostrar_totales = models.BooleanField(default=True, verbose_name='Mostrar Totales')
    mostrar_firmas = models.BooleanField(default=True, verbose_name='Mostrar Espacio para Firmas')
    agrupar_por_ruta = models.BooleanField(default=True, verbose_name='Agrupar por Ruta')
    agrupar_por_categoria = models.BooleanField(default=False, verbose_name='Agrupar por Categoría')
    incluir_vencidas = models.BooleanField(default=True, verbose_name='Incluir Cuotas Vencidas')
    filtrar_por_ruta = models.ForeignKey(
        RutaCobro,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Filtrar por Ruta',
        help_text='Dejar vacío para mostrar todas las rutas'
    )
    es_default = models.BooleanField(default=False, verbose_name='Es Configuración por Defecto')
    
    class Meta:
        verbose_name = 'Configuración de Planilla'
        verbose_name_plural = 'Configuraciones de Planilla'
    
    def __str__(self):
        return self.nombre
    
    def save(self, *args, **kwargs):
        if self.es_default:
            # Desmarcar otros defaults
            ConfiguracionPlanilla.objects.filter(es_default=True).update(es_default=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def obtener_default(cls):
        try:
            return cls.objects.get(es_default=True)
        except cls.DoesNotExist:
            return cls.objects.first()


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
    # Nuevos campos
    tipo_comercio = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Tipo de Comercio/Negocio (texto)',
        help_text='Campo de texto libre (usar Tipo Negocio para categorías)'
    )
    tipo_negocio = models.ForeignKey(
        TipoNegocio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clientes',
        verbose_name='Tipo de Negocio',
        help_text='Categoría de negocio administrable'
    )
    limite_credito = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Límite de Crédito',
        help_text='Máximo que se le puede prestar a este cliente'
    )
    ruta = models.ForeignKey(
        RutaCobro,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clientes',
        verbose_name='Ruta de Cobro'
    )
    dia_pago_preferido = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Día de Pago Preferido',
        help_text='Ej: Lunes, Martes, etc.'
    )
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')
    notas = models.TextField(blank=True, null=True, verbose_name='Notas')
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='clientes',
        verbose_name='Usuario/Cobrador',
        help_text='Usuario que gestiona este cliente',
        null=True,
        blank=True
    )
    
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
    
    @property
    def credito_usado(self):
        """Retorna el monto total de crédito actualmente en uso"""
        prestamo = self.prestamo_activo
        if prestamo:
            return prestamo.monto_pendiente
        return Decimal('0.00')
    
    @property
    def deuda_total(self):
        """Alias de credito_usado - Retorna la deuda total del cliente"""
        return self.credito_usado
    
    @property
    def credito_disponible(self):
        """Retorna cuánto más se le puede prestar al cliente"""
        if self.limite_credito <= 0:
            return None  # Sin límite definido
        disponible = self.limite_credito - self.credito_usado
        return max(disponible, Decimal('0.00'))
    
    @property
    def porcentaje_credito_usado(self):
        """Retorna el porcentaje del límite de crédito usado"""
        if self.limite_credito <= 0:
            return 0
        return min(100, int((self.credito_usado / self.limite_credito) * 100))
    
    @property
    def config_credito(self):
        """Obtiene la configuración de crédito según la categoría"""
        return ConfiguracionCredito.obtener_config(self.categoria)
    
    @property
    def limite_por_categoria(self):
        """Límite máximo según su categoría"""
        config = self.config_credito
        if config and config.limite_maximo > 0:
            return config.limite_maximo
        return None
    
    @property
    def limite_sobre_deuda(self):
        """Cuánto más puede pedir basado en su deuda actual"""
        config = self.config_credito
        if config and config.porcentaje_sobre_deuda > 0:
            deuda = self.credito_usado
            return deuda * (config.porcentaje_sobre_deuda / 100)
        return None
    
    @property
    def limite_por_tipo_negocio(self):
        """Límite según su tipo de negocio"""
        if self.tipo_negocio and self.tipo_negocio.limite_credito_sugerido > 0:
            return self.tipo_negocio.limite_credito_sugerido
        return None
    
    @property
    def maximo_prestable(self):
        """El máximo que se le puede prestar considerando todas las reglas"""
        limites = []
        deuda_actual = self.credito_usado
        
        # 1. Límite individual del cliente
        if self.limite_credito > 0:
            limites.append(self.limite_credito - deuda_actual)
        
        # 2. Límite por categoría
        limite_cat = self.limite_por_categoria
        if limite_cat:
            limites.append(limite_cat - deuda_actual)
        
        # 3. Límite por tipo de negocio
        limite_neg = self.limite_por_tipo_negocio
        if limite_neg:
            limites.append(limite_neg - deuda_actual)
        
        # 4. Límite basado en % sobre deuda
        limite_deuda = self.limite_sobre_deuda
        if limite_deuda and deuda_actual > 0:
            limites.append(limite_deuda)
        
        if limites:
            return max(Decimal('0.00'), min(limites))
        return None  # Sin límite definido
    
    @property
    def puede_renovar(self):
        """Verifica si el cliente puede renovar su préstamo"""
        config = self.config_credito
        prestamo = self.prestamo_activo
        
        if not prestamo:
            return True  # Sin préstamo activo, puede crear nuevo
        
        if config:
            # Verificar si puede renovar con deuda
            if not config.puede_renovar_con_deuda and self.credito_usado > 0:
                return False
            # Verificar días mínimos
            if config.dias_minimos_para_renovar > 0:
                dias_pagando = (timezone.now().date() - prestamo.fecha_inicio).days
                if dias_pagando < config.dias_minimos_para_renovar:
                    return False
        
        return True
    
    @property
    def dias_para_poder_renovar(self):
        """Días que faltan para poder renovar"""
        config = self.config_credito
        prestamo = self.prestamo_activo
        
        if not prestamo or not config:
            return 0
        
        if config.dias_minimos_para_renovar > 0:
            dias_pagando = (timezone.now().date() - prestamo.fecha_inicio).days
            dias_faltantes = config.dias_minimos_para_renovar - dias_pagando
            return max(0, dias_faltantes)
        return 0
    
    @property
    def fecha_fin_prestamo_activo(self):
        """Fecha de finalización del préstamo activo"""
        prestamo = self.prestamo_activo
        if prestamo:
            return prestamo.fecha_finalizacion
        return None
    
    @property
    def info_limite_credito(self):
        """Información completa de límites para mostrar"""
        return {
            'limite_individual': self.limite_credito if self.limite_credito > 0 else None,
            'limite_categoria': self.limite_por_categoria,
            'limite_tipo_negocio': self.limite_por_tipo_negocio,
            'limite_sobre_deuda': self.limite_sobre_deuda,
            'maximo_prestable': self.maximo_prestable,
            'deuda_actual': self.credito_usado,
            'puede_renovar': self.puede_renovar,
            'dias_para_renovar': self.dias_para_poder_renovar,
            'fecha_fin_actual': self.fecha_fin_prestamo_activo,
        }
    
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
    es_renovacion = models.BooleanField(
        default=False,
        verbose_name='Es Renovación',
        help_text='Indica si este préstamo es una renovación de otro'
    )
    prestamo_anterior = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='renovaciones',
        verbose_name='Préstamo Anterior'
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
    
    class MetodoPago(models.TextChoices):
        EFECTIVO = 'EF', 'Efectivo'
        TRANSFERENCIA = 'TR', 'Transferencia'
        MIXTO = 'MX', 'Mixto'
    
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
    # Campos para método de pago
    metodo_pago = models.CharField(
        max_length=2,
        choices=MetodoPago.choices,
        default=MetodoPago.EFECTIVO,
        blank=True,
        null=True,
        verbose_name='Método de Pago'
    )
    monto_efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        blank=True,
        null=True,
        verbose_name='Monto en Efectivo'
    )
    monto_transferencia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        blank=True,
        null=True,
        verbose_name='Monto en Transferencia'
    )
    referencia_transferencia = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Referencia de Transferencia',
        help_text='Número de operación o referencia bancaria'
    )
    # Campo para interés por mora cobrado
    interes_mora_cobrado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Interés por Mora Cobrado'
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
    
    @property
    def interes_mora_pendiente(self):
        """Calcula el interés por mora pendiente de esta cuota"""
        if not self.esta_vencida:
            return Decimal('0.00')
        
        config = ConfiguracionMora.obtener_config_activa()
        if not config:
            return Decimal('0.00')
        
        return config.calcular_interes(self.monto_restante, self.dias_vencida)
    
    @property
    def monto_total_con_mora(self):
        """Monto total a pagar incluyendo interés por mora"""
        return self.monto_restante + self.interes_mora_pendiente
    
    def registrar_pago(self, monto=None, accion_restante='ignorar', fecha_especial=None,
                       metodo_pago='EF', monto_efectivo=None, monto_transferencia=None,
                       referencia_transferencia=None, interes_mora=None):
        """
        Registra un pago en la cuota.
        Si no se especifica monto, se paga el total.
        
        accion_restante puede ser:
        - 'ignorar': El monto restante queda pendiente en esta cuota
        - 'proxima': Suma el restante a la próxima cuota
        - 'especial': Crea una cuota especial en fecha_especial con el monto restante
        
        metodo_pago puede ser:
        - 'EF': Efectivo
        - 'TR': Transferencia
        - 'MX': Mixto
        """
        if monto is None:
            monto = self.monto_restante
        
        monto = Decimal(str(monto))
        monto_restante_anterior = self.monto_restante
        
        self.monto_pagado += monto
        self.fecha_pago_real = timezone.now().date()
        
        # Registrar método de pago
        self.metodo_pago = metodo_pago
        if metodo_pago == 'EF':
            self.monto_efectivo = monto
            self.monto_transferencia = Decimal('0.00')
        elif metodo_pago == 'TR':
            self.monto_efectivo = Decimal('0.00')
            self.monto_transferencia = monto
            self.referencia_transferencia = referencia_transferencia
        elif metodo_pago == 'MX':
            self.monto_efectivo = Decimal(str(monto_efectivo or 0))
            self.monto_transferencia = Decimal(str(monto_transferencia or 0))
            self.referencia_transferencia = referencia_transferencia
        
        # Registrar interés por mora si se proporcionó
        if interes_mora is not None and Decimal(str(interes_mora)) > 0:
            self.interes_mora_cobrado = Decimal(str(interes_mora))
        
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
            # Sumar a la próxima cuota pendiente o parcial
            proxima = self.prestamo.cuotas.filter(
                estado__in=['PE', 'PC'],
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


# ==================== SISTEMA DE AUDITORÍA ====================

class RegistroAuditoria(models.Model):
    """
    Modelo para registrar todas las acciones importantes del sistema.
    Permite rastrear quién hizo qué y cuándo.
    """
    
    class TipoAccion(models.TextChoices):
        CREAR = 'CR', 'Crear'
        EDITAR = 'ED', 'Editar'
        ELIMINAR = 'EL', 'Eliminar'
        COBRO = 'CO', 'Cobro'
        RENOVACION = 'RE', 'Renovación'
        LOGIN = 'LO', 'Inicio de Sesión'
        LOGOUT = 'LU', 'Cierre de Sesión'
        CAMBIO_ESTADO = 'CE', 'Cambio de Estado'
        RESPALDO = 'RS', 'Respaldo'
        OTRO = 'OT', 'Otro'
    
    class TipoModelo(models.TextChoices):
        CLIENTE = 'CL', 'Cliente'
        PRESTAMO = 'PR', 'Préstamo'
        CUOTA = 'CU', 'Cuota'
        USUARIO = 'US', 'Usuario'
        CONFIGURACION = 'CF', 'Configuración'
        SISTEMA = 'SI', 'Sistema'
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registros_auditoria',
        verbose_name='Usuario'
    )
    tipo_accion = models.CharField(
        max_length=2,
        choices=TipoAccion.choices,
        verbose_name='Tipo de Acción'
    )
    tipo_modelo = models.CharField(
        max_length=2,
        choices=TipoModelo.choices,
        verbose_name='Tipo de Modelo'
    )
    modelo_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name='ID del Registro'
    )
    descripcion = models.TextField(
        verbose_name='Descripción'
    )
    datos_anteriores = models.TextField(
        null=True,
        blank=True,
        verbose_name='Datos Anteriores',
        help_text='JSON con los datos antes del cambio'
    )
    datos_nuevos = models.TextField(
        null=True,
        blank=True,
        verbose_name='Datos Nuevos',
        help_text='JSON con los datos después del cambio'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='Dirección IP'
    )
    fecha_hora = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora'
    )
    
    class Meta:
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        ordering = ['-fecha_hora']
        indexes = [
            models.Index(fields=['-fecha_hora']),
            models.Index(fields=['tipo_accion']),
            models.Index(fields=['usuario']),
            models.Index(fields=['tipo_modelo', 'modelo_id']),
        ]
    
    def __str__(self):
        usuario_str = self.usuario.username if self.usuario else 'Sistema'
        return f"[{self.fecha_hora.strftime('%d/%m/%Y %H:%M')}] {usuario_str}: {self.get_tipo_accion_display()}"
    
    @classmethod
    def registrar(cls, usuario, tipo_accion, tipo_modelo, descripcion, 
                  modelo_id=None, datos_anteriores=None, datos_nuevos=None, ip_address=None):
        """Método de conveniencia para crear registros de auditoría"""
        return cls.objects.create(
            usuario=usuario,
            tipo_accion=tipo_accion,
            tipo_modelo=tipo_modelo,
            modelo_id=modelo_id,
            descripcion=descripcion,
            datos_anteriores=datos_anteriores,
            datos_nuevos=datos_nuevos,
            ip_address=ip_address
        )


# ==================== SISTEMA DE NOTIFICACIONES ====================

class Notificacion(models.Model):
    """
    Modelo para gestionar notificaciones y alertas del sistema.
    """
    
    class TipoNotificacion(models.TextChoices):
        CUOTA_VENCIDA = 'CV', 'Cuota Vencida'
        CUOTA_POR_VENCER = 'CP', 'Cuota por Vencer'
        PRESTAMO_FINALIZADO = 'PF', 'Préstamo Finalizado'
        CLIENTE_MOROSO = 'CM', 'Cliente Moroso'
        COBRO_REALIZADO = 'CR', 'Cobro Realizado'
        RENOVACION = 'RN', 'Renovación'
        ALERTA_SISTEMA = 'AS', 'Alerta del Sistema'
        INFO = 'IN', 'Información'
    
    class Prioridad(models.TextChoices):
        ALTA = 'AL', 'Alta'
        MEDIA = 'ME', 'Media'
        BAJA = 'BA', 'Baja'
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notificaciones',
        verbose_name='Usuario',
        help_text='Usuario destinatario. Si es null, es para todos.'
    )
    tipo = models.CharField(
        max_length=2,
        choices=TipoNotificacion.choices,
        verbose_name='Tipo'
    )
    prioridad = models.CharField(
        max_length=2,
        choices=Prioridad.choices,
        default=Prioridad.MEDIA,
        verbose_name='Prioridad'
    )
    titulo = models.CharField(
        max_length=200,
        verbose_name='Título'
    )
    mensaje = models.TextField(
        verbose_name='Mensaje'
    )
    enlace = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='Enlace',
        help_text='URL para redireccionar al hacer clic'
    )
    leida = models.BooleanField(
        default=False,
        verbose_name='Leída'
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    fecha_lectura = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Lectura'
    )
    
    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.titulo} - {self.get_tipo_display()}"
    
    def marcar_como_leida(self):
        """Marca la notificación como leída"""
        if not self.leida:
            self.leida = True
            self.fecha_lectura = timezone.now()
            self.save()
    
    @classmethod
    def crear_notificacion(cls, tipo, titulo, mensaje, usuario=None, prioridad='ME', enlace=None):
        """Método de conveniencia para crear notificaciones"""
        return cls.objects.create(
            usuario=usuario,
            tipo=tipo,
            prioridad=prioridad,
            titulo=titulo,
            mensaje=mensaje,
            enlace=enlace
        )
    
    @classmethod
    def notificar_cuotas_vencidas(cls):
        """Crea notificaciones para cuotas vencidas"""
        hoy = timezone.now().date()
        cuotas_vencidas = Cuota.objects.filter(
            fecha_vencimiento__lt=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).select_related('prestamo', 'prestamo__cliente')
        
        for cuota in cuotas_vencidas:
            # Verificar si ya existe notificación para esta cuota
            existe = cls.objects.filter(
                tipo='CV',
                titulo__contains=f'#{cuota.pk}',
                fecha_creacion__date=hoy,
                leida=False
            ).exists()
            
            if not existe:
                dias = (hoy - cuota.fecha_vencimiento).days
                cls.crear_notificacion(
                    tipo='CV',
                    titulo=f'Cuota #{cuota.pk} vencida - {cuota.prestamo.cliente.nombre_completo}',
                    mensaje=f'La cuota {cuota.numero_cuota}/{cuota.prestamo.cuotas_pactadas} de {cuota.prestamo.cliente.nombre_completo} tiene {dias} días vencida. Monto pendiente: ${cuota.monto_restante}',
                    prioridad='AL' if dias > 7 else 'ME',
                    enlace=f'/prestamos/{cuota.prestamo.pk}/'
                )
    
    @classmethod
    def notificar_cuotas_por_vencer(cls, dias_anticipacion=1):
        """Crea notificaciones para cuotas que vencen pronto"""
        hoy = timezone.now().date()
        fecha_limite = hoy + timedelta(days=dias_anticipacion)
        
        cuotas = Cuota.objects.filter(
            fecha_vencimiento=fecha_limite,
            estado='PE',
            prestamo__estado='AC'
        ).select_related('prestamo', 'prestamo__cliente')
        
        for cuota in cuotas:
            existe = cls.objects.filter(
                tipo='CP',
                titulo__contains=f'#{cuota.pk}',
                fecha_creacion__date=hoy
            ).exists()
            
            if not existe:
                cls.crear_notificacion(
                    tipo='CP',
                    titulo=f'Cuota por vencer - {cuota.prestamo.cliente.nombre_completo}',
                    mensaje=f'La cuota {cuota.numero_cuota}/{cuota.prestamo.cuotas_pactadas} vence mañana. Monto: ${cuota.monto_cuota}',
                    prioridad='BA',
                    enlace=f'/cobros/'
                )


# ==================== CONFIGURACIÓN DE RESPALDOS ====================

class ConfiguracionRespaldo(models.Model):
    """Configuración para respaldos automáticos"""
    
    nombre = models.CharField(
        max_length=100,
        default='Respaldo Automático',
        verbose_name='Nombre'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    frecuencia_horas = models.PositiveIntegerField(
        default=24,
        verbose_name='Frecuencia (horas)',
        help_text='Cada cuántas horas hacer respaldo'
    )
    ruta_destino = models.CharField(
        max_length=500,
        default='backups/',
        verbose_name='Ruta de Destino',
        help_text='Carpeta donde se guardarán los respaldos'
    )
    mantener_ultimos = models.PositiveIntegerField(
        default=7,
        verbose_name='Mantener Últimos',
        help_text='Cantidad de respaldos a mantener (los más antiguos se eliminan)'
    )
    ultimo_respaldo = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Último Respaldo'
    )
    incluir_media = models.BooleanField(
        default=False,
        verbose_name='Incluir Archivos Media'
    )
    
    class Meta:
        verbose_name = 'Configuración de Respaldo'
        verbose_name_plural = 'Configuraciones de Respaldo'
    
    def __str__(self):
        return self.nombre

# ==================== CONFIGURACIÓN DE MORA ====================

class ConfiguracionMora(models.Model):
    """Configuración para cálculo de intereses por mora"""
    
    nombre = models.CharField(
        max_length=100,
        default='Configuración Principal',
        verbose_name='Nombre'
    )
    porcentaje_diario = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.50'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        verbose_name='Porcentaje Diario (%)',
        help_text='Porcentaje de interés que se aplica por cada día de mora'
    )
    dias_gracia = models.PositiveIntegerField(
        default=0,
        verbose_name='Días de Gracia',
        help_text='Días después del vencimiento sin aplicar interés'
    )
    aplicar_automaticamente = models.BooleanField(
        default=True,
        verbose_name='Aplicar Automáticamente',
        help_text='Calcular intereses automáticamente al registrar pagos'
    )
    monto_minimo_mora = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Monto Mínimo de Mora',
        help_text='Monto mínimo para cobrar interés por mora (0 = sin mínimo)'
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
        verbose_name = 'Configuración de Mora'
        verbose_name_plural = 'Configuraciones de Mora'
    
    def __str__(self):
        return f"{self.nombre} - {self.porcentaje_diario}% diario"
    
    @classmethod
    def obtener_config_activa(cls):
        """Obtiene la configuración de mora activa"""
        return cls.objects.filter(activo=True).first()
    
    def calcular_interes(self, monto_cuota, dias_mora):
        """Calcula el interés por mora para una cuota"""
        if dias_mora <= self.dias_gracia:
            return Decimal('0.00')
        
        dias_efectivos = dias_mora - self.dias_gracia
        interes = monto_cuota * (self.porcentaje_diario / 100) * dias_efectivos
        
        if interes < self.monto_minimo_mora:
            return Decimal('0.00')
        
        return interes.quantize(Decimal('0.01'))


class InteresMora(models.Model):
    """Registro de intereses por mora aplicados a cuotas"""
    
    cuota = models.ForeignKey(
        'Cuota',
        on_delete=models.CASCADE,
        related_name='intereses_mora',
        verbose_name='Cuota'
    )
    fecha_calculo = models.DateField(
        auto_now_add=True,
        verbose_name='Fecha de Cálculo'
    )
    dias_mora = models.PositiveIntegerField(
        verbose_name='Días de Mora'
    )
    porcentaje_aplicado = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Porcentaje Aplicado'
    )
    monto_base = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Monto Base',
        help_text='Monto sobre el cual se calculó el interés'
    )
    monto_interes = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Monto de Interés'
    )
    agregado_manualmente = models.BooleanField(
        default=False,
        verbose_name='Agregado Manualmente'
    )
    pagado = models.BooleanField(
        default=False,
        verbose_name='Pagado'
    )
    fecha_pago = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Pago'
    )
    notas = models.TextField(
        blank=True,
        null=True,
        verbose_name='Notas'
    )
    
    class Meta:
        verbose_name = 'Interés por Mora'
        verbose_name_plural = 'Intereses por Mora'
        ordering = ['-fecha_calculo']
    
    def __str__(self):
        return f"Mora Cuota #{self.cuota.pk} - ${self.monto_interes}"
    
    @classmethod
    def calcular_y_registrar(cls, cuota, manual=False, porcentaje_manual=None, monto_manual=None):
        """
        Calcula y registra el interés por mora para una cuota.
        Si manual=True, usar porcentaje_manual o monto_manual.
        """
        if not cuota.esta_vencida:
            return None
        
        dias_mora = cuota.dias_vencida
        monto_base = cuota.monto_restante
        
        if manual and monto_manual is not None:
            # Interés ingresado manualmente
            monto_interes = Decimal(str(monto_manual))
            porcentaje = Decimal('0.00')
        elif manual and porcentaje_manual is not None:
            # Porcentaje ingresado manualmente
            porcentaje = Decimal(str(porcentaje_manual))
            monto_interes = monto_base * (porcentaje / 100) * dias_mora
        else:
            # Usar configuración automática
            config = ConfiguracionMora.obtener_config_activa()
            if not config or not config.aplicar_automaticamente:
                return None
            
            porcentaje = config.porcentaje_diario
            monto_interes = config.calcular_interes(monto_base, dias_mora)
        
        if monto_interes <= 0:
            return None
        
        # Crear registro
        interes = cls.objects.create(
            cuota=cuota,
            dias_mora=dias_mora,
            porcentaje_aplicado=porcentaje,
            monto_base=monto_base,
            monto_interes=monto_interes.quantize(Decimal('0.01')),
            agregado_manualmente=manual
        )
        
        return interes