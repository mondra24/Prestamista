"""
Modelos del Sistema de Gestión de Préstamos
"""
from django.db import models, transaction
from django.core.cache import cache
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
from decimal import Decimal
import uuid


def fecha_local_hoy():
    """Retorna la fecha local (Argentina) en vez de UTC"""
    return timezone.localtime(timezone.now()).date()


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
        """
        Obtiene la configuración para una categoría específica.
        Cacheada 60s: esta consulta se repite varias veces por cliente en
        listados grandes (ver Cliente.puede_renovar y afines) y solo hay un
        puñado de categorías posibles, así que cachear evita un N+1 severo.
        """
        cache_key = f'config_credito_{categoria}'
        config = cache.get(cache_key)
        if config is not None:
            return config
        try:
            config = cls.objects.get(categoria=categoria, activo=True)
        except cls.DoesNotExist:
            return None
        cache.set(cache_key, config, 60)
        return config


class ConfiguracionCategorizacion(models.Model):
    """
    Configuración global: si la categoría del cliente (Excelente/Regular/Moroso)
    se recalcula sola según su historial de pagos, o queda 100% en manos del
    admin/cobrador (por defecto). Solo debe existir una fila.
    """
    categorizacion_automatica = models.BooleanField(
        default=False,
        verbose_name='Categorización automática',
        help_text='Si está activo, el sistema recalcula la categoría del cliente solo al finalizar cada préstamo. '
                   'Si está apagado (por defecto), la categoría la definen manualmente el admin o el cobrador.'
    )

    class Meta:
        verbose_name = 'Configuración de Categorización'
        verbose_name_plural = 'Configuración de Categorización'

    def __str__(self):
        return 'Categorización automática: ' + ('activada' if self.categorizacion_automatica else 'desactivada')

    @classmethod
    def esta_activa(cls):
        """Retorna si la categorización automática está activa (crea la config con default si no existe)"""
        config, _ = cls.objects.get_or_create(pk=1)
        return config.categorizacion_automatica


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
    dni = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='DNI',
        help_text='Documento Nacional de Identidad'
    )
    telefono = models.CharField(max_length=20, verbose_name='Teléfono')
    direccion = models.TextField(verbose_name='Dirección')
    
    # Contactos de referencia
    referencia1_nombre = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Referencia 1 - Nombre/Parentesco',
        help_text='Nombre y parentesco del contacto de referencia'
    )
    referencia1_telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Referencia 1 - Teléfono'
    )
    referencia2_nombre = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Referencia 2 - Nombre/Parentesco',
        help_text='Nombre y parentesco del contacto de referencia'
    )
    referencia2_telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name='Referencia 2 - Teléfono'
    )
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
        verbose_name='Estado',
        db_index=True
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
        help_text='Máximo que se le puede prestar. 0 = sin límite (ilimitado)'
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
        on_delete=models.SET_NULL,
        related_name='clientes',
        verbose_name='Usuario/Cobrador',
        help_text='Usuario que gestiona este cliente',
        null=True,
        blank=True,
        db_index=True
    )
    token_publico = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Token Público del Cliente'
    )
    token_activo = models.BooleanField(
        default=True,
        verbose_name='Link Público del Cliente Activo'
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
    def prestamos_activos(self):
        """
        Retorna TODOS los préstamos activos del cliente (puede tener más de uno).
        Si 'prestamos' viene prefetched (ver PrestamoCreateView, exportar_prestamos_excel),
        filtra en Python sobre esa caché en vez de disparar una query nueva -
        evita un N+1 severo en listados que recorren muchos clientes.
        """
        if 'prestamos' in getattr(self, '_prefetched_objects_cache', {}):
            return [p for p in self.prestamos.all() if p.estado == 'AC']
        return self.prestamos.filter(estado='AC')

    @property
    def prestamo_activo(self):
        """
        Retorna un préstamo activo del cliente para los lugares que solo
        necesitan 'el' préstamo activo (ej. renovación individual). Si tiene
        más de uno, se toma el más reciente.
        """
        activos = self.prestamos_activos
        if not activos:
            return None
        if hasattr(activos, 'order_by'):
            return activos.order_by('-fecha_inicio').first()
        return max(activos, key=lambda p: p.fecha_inicio)

    @property
    def credito_usado(self):
        """
        Retorna el monto total de crédito actualmente en uso, sumando TODOS
        los préstamos activos (un cliente puede tener más de uno a la vez).
        """
        return sum(
            (p.monto_pendiente for p in self.prestamos_activos),
            Decimal('0.00')
        )
    
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
        """El máximo que se le puede prestar. Solo aplica límite individual si está definido."""
        # Solo se limita si el cliente tiene un límite individual > 0
        if self.limite_credito > 0:
            disponible = self.limite_credito - self.credito_usado
            return max(Decimal('0.00'), disponible)
        return None  # Sin límite = ilimitado
    
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
                dias_pagando = (fecha_local_hoy() - prestamo.fecha_inicio).days
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
            dias_pagando = (fecha_local_hoy() - prestamo.fecha_inicio).days
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
    
    @property
    def historial_pagos(self):
        """
        Resumen de puntualidad de pago sobre los préstamos ya finalizados:
        cuántas cuotas pagó a tiempo de las totales. Se usa tanto para
        recalcular la categoría (si la automática está activa) como para
        mostrarlo de un vistazo en la ficha del cliente.
        """
        total_cuotas = 0
        cuotas_a_tiempo = 0
        for prestamo in self.prestamos.filter(estado='FI'):
            for cuota in prestamo.cuotas.all():
                total_cuotas += 1
                if cuota.pagada_en_termino:
                    cuotas_a_tiempo += 1

        porcentaje = (cuotas_a_tiempo / total_cuotas * 100) if total_cuotas > 0 else None
        return {
            'total': total_cuotas,
            'a_tiempo': cuotas_a_tiempo,
            'porcentaje': porcentaje,
        }

    def actualizar_categoria(self):
        """
        Actualiza la categoría del cliente basado en su historial de pagos.
        No hace nada si la categorización automática está desactivada
        (ConfiguracionCategorizacion) — por defecto la categoría es 100% manual.
        """
        if not ConfiguracionCategorizacion.esta_activa():
            return

        resumen = self.historial_pagos
        if resumen['porcentaje'] is None:
            return

        porcentaje = resumen['porcentaje']
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
        PAGO_UNICO = 'PU', 'Pago Único'
    
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
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Tasa de Interés (%)',
        help_text='Porcentaje de interés sobre el capital. Ej: 20 = 20%'
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
        null=True,
        blank=True,
        verbose_name='Fecha de Finalización',
        help_text='Dejar vacío para calcular automáticamente según frecuencia y cuotas'
    )
    fecha_finalizacion_manual = models.BooleanField(
        default=False,
        verbose_name='Fecha de finalización manual',
        help_text='Indica si la fecha fue establecida manualmente'
    )
    estado = models.CharField(
        max_length=2,
        choices=Estado.choices,
        default=Estado.ACTIVO,
        verbose_name='Estado',
        db_index=True
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
    cobrador = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prestamos_creados',
        verbose_name='Cobrador',
        help_text='Usuario/cobrador que creó y gestiona este préstamo',
        db_index=True
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    notas = models.TextField(blank=True, null=True, verbose_name='Notas')
    token_publico = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name='Token Público'
    )
    token_activo = models.BooleanField(
        default=True,
        verbose_name='Link Público Activo'
    )

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
        
        # Para pago único, forzar 1 cuota
        if self.frecuencia == self.Frecuencia.PAGO_UNICO:
            self.cuotas_pactadas = 1
        
        # Calcular fecha de finalización solo si no fue establecida manualmente
        if not self.fecha_finalizacion_manual or not self.fecha_finalizacion:
            self.fecha_finalizacion = self.calcular_fecha_finalizacion()
        
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Generar cuotas automáticamente solo si es nuevo
        if is_new:
            self.generar_cuotas()
    
    def calcular_fecha_finalizacion(self):
        """Calcula la fecha de finalización del préstamo"""
        fecha = self.fecha_inicio
        
        # Pago único: la fecha de finalización es la fecha_finalizacion manual
        if self.frecuencia == self.Frecuencia.PAGO_UNICO:
            if self.fecha_finalizacion:
                return self.fecha_finalizacion
            # Si no hay fecha manual, por defecto 28 días
            return fecha + timedelta(days=28)
        
        # Para diarios, la primera cuota es el mismo día de inicio
        if self.frecuencia == self.Frecuencia.DIARIO:
            # Asegurar que fecha_inicio no sea domingo
            if fecha.weekday() == 6:
                fecha += timedelta(days=1)
            dias_agregados = 1  # La primera cuota es hoy
            while dias_agregados < self.cuotas_pactadas:
                fecha += timedelta(days=1)
                if fecha.weekday() == 6:  # Saltar domingos
                    continue
                dias_agregados += 1
        else:
            dias_agregados = 0
            while dias_agregados < self.cuotas_pactadas:
                if self.frecuencia == self.Frecuencia.SEMANAL:
                    fecha += timedelta(weeks=1)
                elif self.frecuencia == self.Frecuencia.QUINCENAL:
                    fecha += timedelta(days=14)
                elif self.frecuencia == self.Frecuencia.MENSUAL:
                    fecha += timedelta(days=28)
                elif self.frecuencia == self.Frecuencia.PAGO_UNICO:
                    pass  # La fecha ya es la fecha de finalización
                dias_agregados += 1
        
        return fecha
    
    def generar_cuotas(self):
        """Genera todas las cuotas del préstamo automáticamente"""
        # Pago único: genera 1 cuota con la fecha de vencimiento del préstamo
        if self.frecuencia == self.Frecuencia.PAGO_UNICO:
            self._generar_cuota_pago_unico()
            return
        
        monto_cuota = self.monto_total_a_pagar / self.cuotas_pactadas
        fecha_vencimiento = self.fecha_inicio
        
        if self.fecha_finalizacion_manual and self.fecha_finalizacion:
            # Distribuir cuotas uniformemente entre fecha_inicio y fecha_finalizacion
            self._generar_cuotas_con_fecha_fin(monto_cuota)
        else:
            # Distribución normal por frecuencia
            for numero in range(1, self.cuotas_pactadas + 1):
                if numero == 1 and self.frecuencia == self.Frecuencia.DIARIO:
                    # Primera cuota diaria: mismo día de inicio
                    # Asegurar que no caiga domingo
                    while fecha_vencimiento.weekday() == 6:
                        fecha_vencimiento += timedelta(days=1)
                else:
                    # Calcular fecha de vencimiento según frecuencia
                    if self.frecuencia == self.Frecuencia.DIARIO:
                        fecha_vencimiento += timedelta(days=1)
                        # Saltar domingos
                        while fecha_vencimiento.weekday() == 6:
                            fecha_vencimiento += timedelta(days=1)
                    elif self.frecuencia == self.Frecuencia.SEMANAL:
                        fecha_vencimiento += timedelta(weeks=1)
                    elif self.frecuencia == self.Frecuencia.QUINCENAL:
                        fecha_vencimiento += timedelta(days=14)
                    elif self.frecuencia == self.Frecuencia.MENSUAL:
                        fecha_vencimiento += timedelta(days=28)
                    elif self.frecuencia == self.Frecuencia.PAGO_UNICO:
                        pass  # Fecha ya calculada
                
                Cuota.objects.create(
                    prestamo=self,
                    numero_cuota=numero,
                    monto_cuota=round(monto_cuota, 2),
                    fecha_vencimiento=fecha_vencimiento
                )
    
    def _generar_cuotas_con_fecha_fin(self, monto_cuota):
        """Genera cuotas distribuyéndolas uniformemente hasta la fecha de finalización"""
        total_dias = (self.fecha_finalizacion - self.fecha_inicio).days
        if total_dias <= 0:
            total_dias = 1
        
        for numero in range(1, self.cuotas_pactadas + 1):
            # Distribuir proporcionalmente
            dias_offset = int(round(total_dias * numero / self.cuotas_pactadas))
            fecha_vencimiento = self.fecha_inicio + timedelta(days=dias_offset)
            
            # Si es frecuencia diaria, saltar domingos
            if self.frecuencia == self.Frecuencia.DIARIO:
                while fecha_vencimiento.weekday() == 6:
                    fecha_vencimiento += timedelta(days=1)
            
            Cuota.objects.create(
                prestamo=self,
                numero_cuota=numero,
                monto_cuota=round(monto_cuota, 2),
                fecha_vencimiento=fecha_vencimiento
            )
    
    def siguiente_fecha_cuota(self, fecha_actual):
        """
        Calcula la fecha de vencimiento de la próxima cuota a partir de una
        fecha dada, según la frecuencia del préstamo. Misma regla que usa
        generar_cuotas(), extraída para poder agregar cuotas sueltas al
        final de un cronograma existente (ver PrestamoUpdateView).
        """
        if self.frecuencia == self.Frecuencia.DIARIO:
            fecha = fecha_actual + timedelta(days=1)
            while fecha.weekday() == 6:
                fecha += timedelta(days=1)
            return fecha
        elif self.frecuencia == self.Frecuencia.SEMANAL:
            return fecha_actual + timedelta(weeks=1)
        elif self.frecuencia == self.Frecuencia.QUINCENAL:
            return fecha_actual + timedelta(days=14)
        elif self.frecuencia == self.Frecuencia.MENSUAL:
            return fecha_actual + timedelta(days=28)
        return fecha_actual

    def _generar_cuota_pago_unico(self):
        """
        Genera la cuota para pago único.
        La fecha de vencimiento es la fecha de finalización del préstamo.
        """
        Cuota.objects.create(
            prestamo=self,
            numero_cuota=1,
            monto_cuota=round(self.monto_total_a_pagar, 2),
            fecha_vencimiento=self.fecha_finalizacion
        )
    
    @property
    def es_pago_unico(self):
        """Indica si el préstamo es de pago único"""
        return self.frecuencia == self.Frecuencia.PAGO_UNICO
    
    @property
    def es_semanal(self):
        """Indica si el préstamo es semanal"""
        return self.frecuencia == self.Frecuencia.SEMANAL
    
    @property
    def dias_gracia(self):
        """Días de gracia para préstamos semanales (7 días desde la fecha de inicio)"""
        return 7
    
    @property
    def fecha_limite_gracia(self):
        """Fecha límite del período de gracia (7 días después del inicio)"""
        if self.es_semanal:
            return self.fecha_inicio + timedelta(days=self.dias_gracia)
        return None
    
    @property
    def penalizacion_50(self):
        """Monto de penalización (50% del préstamo) si no paga dentro del período de gracia"""
        if self.es_semanal:
            return round(self.monto_total_a_pagar * Decimal('0.50'), 2)
        return Decimal('0.00')
    
    @property
    def monto_con_penalizacion(self):
        """Monto total incluyendo penalización si aplica (solo semanales)"""
        if self.es_semanal and self.estado == self.Estado.ACTIVO:
            hoy = fecha_local_hoy()
            if hoy > self.fecha_limite_gracia and self.monto_pagado == Decimal('0.00'):
                return self.monto_total_a_pagar + self.penalizacion_50
        return self.monto_total_a_pagar
    
    @property
    def tiene_penalizacion(self):
        """Indica si el préstamo semanal tiene penalización activa"""
        if self.es_semanal and self.estado == self.Estado.ACTIVO:
            hoy = fecha_local_hoy()
            return hoy > self.fecha_limite_gracia and self.monto_pagado == Decimal('0.00')
        return False

    @property
    def monto_pagado(self):
        """
        Suma de todos los pagos realizados. Si 'cuotas' viene prefetched
        (ver exportar_prestamos_excel, PrestamoCreateView), suma en Python
        sobre esa caché en vez de un aggregate() nuevo por préstamo - evita
        un N+1 severo en listados/exportaciones con muchos préstamos.
        """
        if 'cuotas' in getattr(self, '_prefetched_objects_cache', {}):
            return sum(
                (c.monto_pagado for c in self.cuotas.all() if c.estado in ('PA', 'PC')),
                Decimal('0.00')
            )
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
    def mora_pendiente_total(self):
        """Suma de mora pendiente de todas las cuotas vencidas y no pagadas completamente"""
        total = Decimal('0.00')
        for cuota in self.cuotas.filter(estado__in=['PE', 'PC']):
            total += cuota.interes_mora_pendiente
        return total

    @property
    def monto_pendiente_con_mora(self):
        """Monto pendiente incluyendo mora acumulada de cuotas vencidas"""
        return self.monto_pendiente + self.mora_pendiente_total

    @property
    def cuotas_pagadas(self):
        """Número de cuotas completamente pagadas"""
        if 'cuotas' in getattr(self, '_prefetched_objects_cache', {}):
            return sum(1 for c in self.cuotas.all() if c.estado == 'PA')
        return self.cuotas.filter(estado='PA').count()
    
    @property
    def progreso_porcentaje(self):
        """Porcentaje de progreso del préstamo"""
        if self.cuotas_pactadas == 0:
            return 0
        return int((self.cuotas_pagadas / self.cuotas_pactadas) * 100)
    
    @property
    def proxima_cuota(self):
        """Retorna la próxima cuota pendiente (incluye parciales, no solo las que no se tocaron)"""
        return self.cuotas.filter(estado__in=['PE', 'PC']).order_by('numero_cuota').first()

    @property
    def notas_vigentes(self):
        """
        Notas de seguimiento activas (no vencidas). Si 'notas_seguimiento'
        viene prefetched (ver CobrosView), filtra en Python en vez de una
        query nueva por préstamo - mismo criterio que el resto de las
        propiedades que evitan N+1 en listados grandes.
        """
        if 'notas_seguimiento' in getattr(self, '_prefetched_objects_cache', {}):
            return [n for n in self.notas_seguimiento.all() if n.vigente]
        hoy = fecha_local_hoy()
        return list(self.notas_seguimiento.filter(
            models.Q(fecha_vencimiento__isnull=True) | models.Q(fecha_vencimiento__gte=hoy)
        ))

    def liquidar_prestamo(self):
        """Liquida el préstamo marcando todas las cuotas como pagadas"""
        self.cuotas.filter(estado='PE').update(
            estado='PA',
            fecha_pago_real=fecha_local_hoy()
        )
        self.estado = self.Estado.FINALIZADO
        self.save()
        self.cliente.actualizar_categoria()
    
    def calcular_saldo_para_renovacion(self):
        """Calcula el saldo pendiente para renovación"""
        return self.monto_pendiente
    
    @classmethod
    @transaction.atomic
    def renovar_prestamo(cls, prestamo_anterior, nuevo_monto, nueva_tasa, nuevas_cuotas, nueva_frecuencia, cobrador=None, fecha_finalizacion=None):
        """
        Renueva un préstamo existente.
        El saldo pendiente se suma al nuevo capital.
        Si se proporciona fecha_finalizacion, se marca como manual.
        """
        saldo_pendiente = prestamo_anterior.calcular_saldo_para_renovacion()
        
        # Cancelar todas las cuotas pendientes del préstamo anterior
        # Actualizamos cada cuota individualmente para evitar problemas con F()
        cuotas_pendientes = prestamo_anterior.cuotas.filter(estado__in=['PE', 'PC'])
        for cuota in cuotas_pendientes:
            cuota.estado = 'PA'
            cuota.fecha_pago_real = fecha_local_hoy()
            cuota.monto_pagado = cuota.monto_cuota
            cuota.save()
        
        # Marcar préstamo anterior como renovado
        prestamo_anterior.estado = cls.Estado.RENOVADO
        prestamo_anterior.save(update_fields=['estado'])
        
        # Crear nuevo préstamo con capital = nuevo_monto + saldo_pendiente
        nuevo_capital = nuevo_monto + saldo_pendiente
        
        create_kwargs = dict(
            cliente=prestamo_anterior.cliente,
            monto_solicitado=nuevo_capital,
            tasa_interes_porcentaje=nueva_tasa,
            cuotas_pactadas=nuevas_cuotas,
            frecuencia=nueva_frecuencia,
            fecha_inicio=fecha_local_hoy(),
            es_renovacion=True,
            prestamo_anterior=prestamo_anterior,
            cobrador=cobrador or prestamo_anterior.cobrador,
            notas=f"Renovación del préstamo #{prestamo_anterior.pk}. Saldo anterior: ${saldo_pendiente}"
        )
        
        if fecha_finalizacion:
            create_kwargs['fecha_finalizacion'] = fecha_finalizacion
            create_kwargs['fecha_finalizacion_manual'] = True
        
        nuevo_prestamo = cls.objects.create(**create_kwargs)

        return nuevo_prestamo


class NotaSeguimiento(models.Model):
    """
    Recordatorio corto atado a un préstamo (ej. "hablé con el cliente por
    WhatsApp, paga el 25") para que no se pierda en el chat. Pensado para
    durar poco: vence sola después de un tiempo o se borra a mano cuando ya
    se resolvió, no es un historial permanente.
    """

    class Duracion(models.TextChoices):
        TRES_DIAS = '3D', '3 días'
        UNA_SEMANA = '7D', '1 semana'
        QUINCE_DIAS = '15D', '15 días'
        PROXIMA_CUOTA = 'PC', 'Hasta la próxima cuota'
        SIN_VENCIMIENTO = 'SV', 'Sin vencimiento'

    prestamo = models.ForeignKey(
        Prestamo,
        on_delete=models.CASCADE,
        related_name='notas_seguimiento',
        verbose_name='Préstamo'
    )
    texto = models.CharField(max_length=280, verbose_name='Nota')
    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Creado por'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    fecha_vencimiento = models.DateField(
        null=True, blank=True,
        verbose_name='Vence el',
        help_text='Vacío = no vence sola, hay que borrarla a mano'
    )

    class Meta:
        verbose_name = 'Nota de Seguimiento'
        verbose_name_plural = 'Notas de Seguimiento'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'{self.prestamo} - {self.texto[:40]}'

    @property
    def vigente(self):
        return self.fecha_vencimiento is None or self.fecha_vencimiento >= fecha_local_hoy()

    @classmethod
    def calcular_vencimiento(cls, duracion, prestamo):
        """Traduce la opción de duración elegida a una fecha concreta (o None = sin vencer)."""
        hoy = fecha_local_hoy()
        if duracion == cls.Duracion.TRES_DIAS:
            return hoy + timedelta(days=3)
        if duracion == cls.Duracion.UNA_SEMANA:
            return hoy + timedelta(days=7)
        if duracion == cls.Duracion.QUINCE_DIAS:
            return hoy + timedelta(days=15)
        if duracion == cls.Duracion.PROXIMA_CUOTA:
            proxima = prestamo.proxima_cuota
            return proxima.fecha_vencimiento if proxima else None
        return None  # SIN_VENCIMIENTO o valor desconocido


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
    fecha_vencimiento = models.DateField(verbose_name='Fecha de Vencimiento', db_index=True)
    estado = models.CharField(
        max_length=2,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        verbose_name='Estado',
        db_index=True
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
    # Quién cobró esta cuota
    cobrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuotas_cobradas',
        verbose_name='Cobrado por'
    )
    
    class Meta:
        verbose_name = 'Cuota'
        verbose_name_plural = 'Cuotas'
        ordering = ['prestamo', 'numero_cuota']
        unique_together = ['prestamo', 'numero_cuota']
        indexes = [
            models.Index(fields=['estado', 'fecha_vencimiento']),
            models.Index(fields=['fecha_pago_real']),
        ]
    
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
        return self.fecha_vencimiento < fecha_local_hoy()
    
    @property
    def dias_vencida(self):
        """Días de vencimiento de la cuota"""
        if not self.esta_vencida:
            return 0
        return (fecha_local_hoy() - self.fecha_vencimiento).days

    DIAS_GRACIA_PUNTUALIDAD = 6

    @property
    def pagada_en_termino(self):
        """
        Se considera 'pagada a tiempo' si se abonó hasta DIAS_GRACIA_PUNTUALIDAD
        días después del vencimiento. Pedido explícito del cliente: él le da ese
        margen a sus clientes y no quiere que cuenten como atraso en las
        estadísticas de puntualidad ni en la detección de buenos pagadores.
        """
        if not self.fecha_pago_real:
            return False
        return (self.fecha_pago_real - self.fecha_vencimiento).days <= self.DIAS_GRACIA_PUNTUALIDAD

    @property
    def interes_mora_pendiente(self):
        """Mora calculada automáticamente. Desactivada por pedido del cliente:
        la mora la registra el cobrador a mano desde el modal del lápiz."""
        return Decimal('0.00')
    
    @property
    def monto_total_con_mora(self):
        """Monto total a pagar incluyendo interés por mora"""
        return self.monto_restante + self.interes_mora_pendiente
    
    @transaction.atomic
    def registrar_pago(self, monto=None, accion_restante='ignorar', fecha_especial=None,
                       metodo_pago='EF', monto_efectivo=None, monto_transferencia=None,
                       referencia_transferencia=None, interes_mora=None, cobrador=None):
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
        from core.models import HistorialModificacionPago

        if monto is None:
            monto = self.monto_restante
        
        monto = Decimal(str(monto))
        monto_cuota_original = self.monto_cuota
        monto_restante_anterior = self.monto_restante
        
        self.monto_pagado += monto
        
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
        
        # Registrar quién cobró
        if cobrador is not None:
            self.cobrado_por = cobrador
        
        if self.monto_pagado >= self.monto_cuota:
            self.estado = self.Estado.PAGADO
            self.monto_pagado = self.monto_cuota  # Evitar sobrepagos
            self.fecha_pago_real = fecha_local_hoy()
        elif monto > 0:
            # Solo marcar como parcial si efectivamente se pagó algo de cuota
            self.estado = self.Estado.PARCIAL
            self.fecha_pago_real = fecha_local_hoy()
        # Si monto == 0 (solo mora), no cambiar estado ni fecha_pago_real
        
        self.save()
        
        # Calcular lo que quedó sin pagar de esta cuota
        restante = monto_restante_anterior - monto
        
        # Manejar el monto restante según la acción elegida
        mora_pendiente = Decimal(str(interes_mora or 0))
        monto_a_transferir = restante + mora_pendiente  # Capital restante + mora no pagada
        
        # --- HISTORIAL: Registrar el pago en esta cuota ---
        if monto == 0 and mora_pendiente > 0:
            tipo_pago = 'RM'  # Solo registro de mora
        elif monto < monto_restante_anterior:
            tipo_pago = 'PP'  # Pago parcial
        else:
            tipo_pago = 'PA'  # Pago completo
        
        HistorialModificacionPago.objects.create(
            cuota=self,
            usuario=cobrador,
            tipo_modificacion=tipo_pago,
            monto_cuota_anterior=monto_cuota_original,
            monto_cuota_nuevo=self.monto_cuota,
            monto_pagado=monto,
            monto_restante_transferido=monto_a_transferir if monto_a_transferir > 0 and accion_restante != 'ignorar' else Decimal('0.00'),
            interes_mora=mora_pendiente,
            metodo_pago=metodo_pago,
            notas=f'Acción restante: {accion_restante}' if tipo_pago == 'PP' or mora_pendiente > 0 else ''
        )
        
        if monto_a_transferir > 0 and accion_restante == 'proxima':
            # Sumar a la próxima cuota pendiente o parcial
            proxima = self.prestamo.cuotas.filter(
                estado__in=['PE', 'PC'],
                numero_cuota__gt=self.numero_cuota
            ).order_by('numero_cuota').first()
            
            if proxima:
                monto_proxima_anterior = proxima.monto_cuota
                proxima.monto_cuota += monto_a_transferir
                proxima.save()
                
                # --- HISTORIAL: Registrar que la próxima cuota recibió monto ---
                HistorialModificacionPago.objects.create(
                    cuota=proxima,
                    cuota_relacionada=self,
                    usuario=cobrador,
                    tipo_modificacion='MR',
                    monto_cuota_anterior=monto_proxima_anterior,
                    monto_cuota_nuevo=proxima.monto_cuota,
                    monto_pagado=Decimal('0.00'),
                    monto_restante_transferido=monto_a_transferir,
                    interes_mora=mora_pendiente,
                    metodo_pago='',
                    notas=f'Recibió ${monto_a_transferir:,.0f} de cuota #{self.numero_cuota} (restante: ${restante:,.0f}, mora: ${mora_pendiente:,.0f})'
                )
                
                # --- HISTORIAL: Registrar que esta cuota transfirió monto ---
                HistorialModificacionPago.objects.create(
                    cuota=self,
                    cuota_relacionada=proxima,
                    usuario=cobrador,
                    tipo_modificacion='TR',
                    monto_cuota_anterior=monto_cuota_original,
                    monto_cuota_nuevo=self.monto_cuota,
                    monto_pagado=Decimal('0.00'),
                    monto_restante_transferido=monto_a_transferir,
                    interes_mora=mora_pendiente,
                    metodo_pago='',
                    notas=f'Transferido ${monto_a_transferir:,.0f} a cuota #{proxima.numero_cuota}'
                )
                
                # Marcar esta cuota como pagada ya que se transfirió el restante
                if restante > 0:
                    self.estado = self.Estado.PAGADO
                    self.save()
        
        elif monto_a_transferir > 0 and accion_restante == 'especial' and fecha_especial:
            # Crear cuota especial
            ultimo_numero = self.prestamo.cuotas.aggregate(
                max_num=models.Max('numero_cuota')
            )['max_num'] or 0
            
            cuota_especial = Cuota.objects.create(
                prestamo=self.prestamo,
                numero_cuota=ultimo_numero + 1,
                monto_cuota=monto_a_transferir,
                fecha_vencimiento=fecha_especial,
                estado=self.Estado.PENDIENTE
            )
            # Actualizar número de cuotas pactadas
            self.prestamo.cuotas_pactadas = ultimo_numero + 1
            self.prestamo.save(update_fields=['cuotas_pactadas'])
            
            # --- HISTORIAL: Registrar cuota especial creada ---
            HistorialModificacionPago.objects.create(
                cuota=self,
                cuota_relacionada=cuota_especial,
                usuario=cobrador,
                tipo_modificacion='CE',
                monto_cuota_anterior=monto_cuota_original,
                monto_cuota_nuevo=self.monto_cuota,
                monto_pagado=Decimal('0.00'),
                monto_restante_transferido=monto_a_transferir,
                interes_mora=mora_pendiente,
                metodo_pago='',
                notas=f'Cuota especial #{cuota_especial.numero_cuota} creada por ${monto_a_transferir:,.0f}'
            )
            
            # --- HISTORIAL: Registrar en la cuota especial ---
            HistorialModificacionPago.objects.create(
                cuota=cuota_especial,
                cuota_relacionada=self,
                usuario=cobrador,
                tipo_modificacion='MR',
                monto_cuota_anterior=Decimal('0.00'),
                monto_cuota_nuevo=monto_a_transferir,
                monto_pagado=Decimal('0.00'),
                monto_restante_transferido=monto_a_transferir,
                interes_mora=mora_pendiente,
                metodo_pago='',
                notas=f'Cuota especial. Recibió ${monto_a_transferir:,.0f} de cuota #{self.numero_cuota}'
            )
            
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
    
    @transaction.atomic
    def cancelar_pago(self, usuario=None):
        """
        Cancela/revierte el pago de esta cuota.
        Devuelve la cuota al estado pendiente con monto_pagado = 0.
        También revierte transferencias a próxima cuota y elimina cuotas especiales.
        """
        from core.models import HistorialModificacionPago
        
        if self.estado not in ['PA', 'PC']:
            raise ValueError('Solo se pueden anular pagos de cuotas pagadas o con pago parcial.')
        
        monto_pagado_anterior = self.monto_pagado
        estado_anterior = self.estado
        notas_anulacion = f'Pago anulado. Estado anterior: {self.get_estado_display()}. Monto revertido: ${monto_pagado_anterior:,.0f}'
        
        # --- REVERTIR TRANSFERENCIAS A PRÓXIMA CUOTA ---
        transferencias = HistorialModificacionPago.objects.filter(
            cuota=self,
            tipo_modificacion='TR',
            cuota_relacionada__isnull=False
        ).select_related('cuota_relacionada')
        
        for tr in transferencias:
            cuota_destino = tr.cuota_relacionada
            monto_transferido = tr.monto_restante_transferido
            if monto_transferido > 0 and cuota_destino:
                monto_destino_anterior = cuota_destino.monto_cuota
                cuota_destino.monto_cuota = max(Decimal('0.00'), cuota_destino.monto_cuota - monto_transferido)
                cuota_destino.save()
                notas_anulacion += f'. Revertida transferencia de ${monto_transferido:,.0f} a cuota #{cuota_destino.numero_cuota}'
                
                # Registrar en historial de la cuota destino
                HistorialModificacionPago.objects.create(
                    cuota=cuota_destino,
                    cuota_relacionada=self,
                    usuario=usuario,
                    tipo_modificacion='AN',
                    monto_cuota_anterior=monto_destino_anterior,
                    monto_cuota_nuevo=cuota_destino.monto_cuota,
                    monto_pagado=Decimal('0.00'),
                    monto_restante_transferido=monto_transferido,
                    interes_mora=Decimal('0.00'),
                    metodo_pago='',
                    notas=f'Revertida recepción de ${monto_transferido:,.0f} de cuota #{self.numero_cuota} (pago anulado)'
                )
        
        # --- REVERTIR CUOTAS ESPECIALES ---
        cuotas_especiales = HistorialModificacionPago.objects.filter(
            cuota=self,
            tipo_modificacion='CE',
            cuota_relacionada__isnull=False
        ).select_related('cuota_relacionada')
        
        for ce in cuotas_especiales:
            cuota_esp = ce.cuota_relacionada
            if cuota_esp and cuota_esp.estado == 'PE' and cuota_esp.monto_pagado == 0:
                notas_anulacion += f'. Eliminada cuota especial #{cuota_esp.numero_cuota}'
                cuota_esp.delete()
        
        # Registrar en historial antes de revertir
        HistorialModificacionPago.objects.create(
            cuota=self,
            usuario=usuario,
            tipo_modificacion='AN',
            monto_cuota_anterior=self.monto_cuota,
            monto_cuota_nuevo=self.monto_cuota,
            monto_pagado=monto_pagado_anterior,
            monto_restante_transferido=Decimal('0.00'),
            interes_mora=self.interes_mora_cobrado,
            metodo_pago=self.metodo_pago or '',
            notas=notas_anulacion
        )
        
        # Revertir la cuota
        self.monto_pagado = Decimal('0.00')
        self.estado = self.Estado.PENDIENTE
        self.fecha_pago_real = None
        self.metodo_pago = None
        self.monto_efectivo = Decimal('0.00')
        self.monto_transferencia = Decimal('0.00')
        self.referencia_transferencia = None
        self.interes_mora_cobrado = Decimal('0.00')
        self.cobrado_por = None
        self.save()
        
        # Si el préstamo estaba finalizado, reactivarlo
        prestamo = self.prestamo
        if prestamo.estado == Prestamo.Estado.FINALIZADO:
            prestamo.estado = Prestamo.Estado.ACTIVO
            prestamo.save(update_fields=['estado'])
        
        return self


# ==================== HISTORIAL DE MODIFICACIONES DE PAGO ====================

class HistorialModificacionPago(models.Model):
    """
    Registra cada modificación en cuotas durante el proceso de pago.
    Permite rastrear pagos parciales, transferencias de montos a cuotas siguientes,
    y creación de cuotas especiales.
    """
    
    class TipoModificacion(models.TextChoices):
        PAGO_PARCIAL = 'PP', 'Pago Parcial'
        PAGO_COMPLETO = 'PA', 'Pago Completo'
        TRANSFERENCIA_RESTANTE = 'TR', 'Restante a Próxima Cuota'
        CUOTA_ESPECIAL = 'CE', 'Cuota Especial Creada'
        MONTO_RECIBIDO = 'MR', 'Monto Recibido de Otra Cuota'
        ANULACION = 'AN', 'Pago Anulado'
        EDICION = 'ED', 'Cobro Editado'
        REGISTRO_MORA = 'RM', 'Registro de Mora'
    
    cuota = models.ForeignKey(
        'Cuota',
        on_delete=models.CASCADE,
        related_name='historial_modificaciones',
        verbose_name='Cuota'
    )
    cuota_relacionada = models.ForeignKey(
        'Cuota',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='modificaciones_relacionadas',
        verbose_name='Cuota Relacionada',
        help_text='Cuota origen o destino de la transferencia de monto'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Usuario'
    )
    fecha_modificacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Modificación'
    )
    tipo_modificacion = models.CharField(
        max_length=2,
        choices=TipoModificacion.choices,
        verbose_name='Tipo de Modificación'
    )
    
    # Montos antes/después
    monto_cuota_anterior = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Monto Cuota Anterior'
    )
    monto_cuota_nuevo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name='Monto Cuota Nuevo'
    )
    monto_pagado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Monto Pagado'
    )
    monto_restante_transferido = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Monto Restante Transferido',
        help_text='Monto que se transfirió a otra cuota'
    )
    interes_mora = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name='Interés por Mora'
    )
    metodo_pago = models.CharField(
        max_length=2,
        blank=True,
        default='',
        verbose_name='Método de Pago'
    )
    notas = models.TextField(
        blank=True,
        default='',
        verbose_name='Notas'
    )
    
    class Meta:
        verbose_name = 'Historial de Modificación de Pago'
        verbose_name_plural = 'Historial de Modificaciones de Pago'
        ordering = ['-fecha_modificacion']
        indexes = [
            models.Index(fields=['-fecha_modificacion']),
            models.Index(fields=['cuota']),
            models.Index(fields=['tipo_modificacion']),
        ]
    
    def __str__(self):
        return f'{self.get_tipo_modificacion_display()} - Cuota #{self.cuota.numero_cuota} - ${self.monto_pagado:,.0f}'
    
    @property
    def diferencia_monto(self):
        """Diferencia entre monto anterior y nuevo"""
        return self.monto_cuota_nuevo - self.monto_cuota_anterior
    
    @property
    def resumen(self):
        """Resumen legible de la modificación"""
        def m(val):
            """Formato argentino: punto como separador de miles"""
            return f"${int(val):,}".replace(',', '.')

        mora_texto = f' (Mora: {m(self.interes_mora)})' if self.interes_mora and self.interes_mora > 0 else ''
        if self.tipo_modificacion == 'PP':
            restante_cuota = self.monto_cuota_anterior - self.monto_pagado
            return f'Pago parcial {m(self.monto_pagado)} de {m(self.monto_cuota_anterior)}. Restante: {m(restante_cuota)}{mora_texto}'
        elif self.tipo_modificacion == 'PA':
            return f'Pago completo {m(self.monto_pagado)}{mora_texto}'
        elif self.tipo_modificacion == 'TR':
            if self.interes_mora and self.interes_mora > 0:
                capital_transferido = self.monto_restante_transferido - self.interes_mora
                return f'Transferido {m(self.monto_restante_transferido)} a próxima cuota (Capital: {m(capital_transferido)} + Mora: {m(self.interes_mora)})'
            return f'Transferido {m(self.monto_restante_transferido)} a próxima cuota'
        elif self.tipo_modificacion == 'CE':
            if self.interes_mora and self.interes_mora > 0:
                capital_transferido = self.monto_restante_transferido - self.interes_mora
                return f'Cuota especial por {m(self.monto_restante_transferido)} (Capital: {m(capital_transferido)} + Mora: {m(self.interes_mora)})'
            return f'Cuota especial por {m(self.monto_restante_transferido)}'
        elif self.tipo_modificacion == 'MR':
            origen = f'cuota #{self.cuota_relacionada.numero_cuota}' if self.cuota_relacionada else '?'
            if self.interes_mora and self.interes_mora > 0:
                capital_recibido = self.monto_restante_transferido - self.interes_mora
                return f'Recibido {m(self.monto_restante_transferido)} de {origen} (Capital: {m(capital_recibido)} + Mora: {m(self.interes_mora)})'
            return f'Recibido {m(self.monto_restante_transferido)} de {origen}'
        elif self.tipo_modificacion == 'AN':
            return f'Pago anulado. Se revirtieron {m(self.monto_pagado)}{mora_texto}'
        elif self.tipo_modificacion == 'ED':
            return f'Cobro editado. Nuevo monto: {m(self.monto_pagado)}{mora_texto}'
        elif self.tipo_modificacion == 'RM':
            return f'Mora registrada: {m(self.interes_mora)}'
        return self.notas or str(self)


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
        """Crea notificaciones para cuotas vencidas. Retorna la cantidad creada."""
        hoy = fecha_local_hoy()
        cuotas_vencidas = Cuota.objects.filter(
            fecha_vencimiento__lt=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).select_related('prestamo', 'prestamo__cliente')

        creadas = 0
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
                creadas += 1
        return creadas

    @classmethod
    def notificar_cuotas_por_vencer(cls, dias_anticipacion=1):
        """Crea notificaciones para cuotas que vencen pronto. Retorna la cantidad creada."""
        hoy = fecha_local_hoy()
        fecha_limite = hoy + timedelta(days=dias_anticipacion)

        cuotas = Cuota.objects.filter(
            fecha_vencimiento=fecha_limite,
            estado='PE',
            prestamo__estado='AC'
        ).select_related('prestamo', 'prestamo__cliente')

        creadas = 0
        for cuota in cuotas:
            existe = cls.objects.filter(
                tipo='CP',
                titulo__contains=f'#{cuota.pk}',
                fecha_creacion__date=hoy
            ).exists()

            if not existe:
                cls.crear_notificacion(
                    tipo='CP',
                    titulo=f'Cuota #{cuota.pk} por vencer - {cuota.prestamo.cliente.nombre_completo}',
                    mensaje=f'La cuota {cuota.numero_cuota}/{cuota.prestamo.cuotas_pactadas} vence mañana. Monto: ${cuota.monto_cuota}',
                    prioridad='BA',
                    enlace=f'/cobros/'
                )
                creadas += 1
        return creadas

    @classmethod
    def notificar_cobradores_sin_actividad(cls):
        """
        Alerta a los administradores si un cobrador tenía cuotas para cobrar hoy
        (vencidas o de hoy) y no registró ningún cobro en el día. Retorna la
        cantidad de cobradores detectados sin actividad.
        """
        hoy = fecha_local_hoy()

        cobradores = User.objects.filter(
            perfil__rol=PerfilUsuario.Rol.COBRADOR,
            perfil__activo=True
        )

        administradores = User.objects.filter(
            models.Q(is_superuser=True) | models.Q(perfil__rol=PerfilUsuario.Rol.ADMIN)
        ).distinct()

        detectados = 0
        for cobrador in cobradores:
            tenia_para_cobrar = Cuota.objects.filter(
                fecha_vencimiento__lte=hoy,
                estado__in=['PE', 'PC'],
                prestamo__estado='AC',
                prestamo__cobrador=cobrador
            ).exists()

            if not tenia_para_cobrar:
                continue

            registro_algun_cobro = Cuota.objects.filter(
                fecha_pago_real=hoy,
                estado__in=['PA', 'PC'],
                prestamo__cobrador=cobrador
            ).exists()

            if registro_algun_cobro:
                continue

            nombre_cobrador = cobrador.get_full_name() or cobrador.username

            for admin in administradores:
                existe = cls.objects.filter(
                    tipo='AS',
                    usuario=admin,
                    titulo__contains=f'sin cobros - {nombre_cobrador}',
                    fecha_creacion__date=hoy
                ).exists()

                if not existe:
                    cls.crear_notificacion(
                        tipo='AS',
                        titulo=f'Día sin cobros - {nombre_cobrador}',
                        mensaje=f'{nombre_cobrador} tenía cuotas pendientes para cobrar hoy y no registró ningún cobro.',
                        usuario=admin,
                        prioridad='ME',
                        enlace='/cobros/'
                    )
            detectados += 1
        return detectados

    @classmethod
    def notificar_candidatos_renovacion(cls):
        """
        Detecta préstamos que terminaron de pagarse hoy con buen historial
        (>=70% de cuotas a tiempo, mismo umbral que separa MOROSO del resto en
        Cliente.actualizar_categoria) y notifica a los administradores como
        candidatos a renovación. Retorna la cantidad de candidatos detectados.
        """
        hoy = fecha_local_hoy()

        prestamos_finalizados_hoy = Prestamo.objects.filter(
            estado=Prestamo.Estado.FINALIZADO
        ).annotate(
            ultimo_pago=models.Max('cuotas__fecha_pago_real')
        ).filter(ultimo_pago=hoy).select_related('cliente')

        administradores = User.objects.filter(
            models.Q(is_superuser=True) | models.Q(perfil__rol=PerfilUsuario.Rol.ADMIN)
        ).distinct()

        detectados = 0
        for prestamo in prestamos_finalizados_hoy:
            cuotas = list(prestamo.cuotas.all())
            if not cuotas:
                continue

            a_tiempo = sum(1 for c in cuotas if c.pagada_en_termino)
            porcentaje = (a_tiempo / len(cuotas)) * 100
            if porcentaje < 70:
                continue

            cliente = prestamo.cliente
            for admin in administradores:
                existe = cls.objects.filter(
                    tipo='RN',
                    usuario=admin,
                    titulo__contains=f'préstamo #{prestamo.pk})',
                    fecha_creacion__date=hoy
                ).exists()

                if not existe:
                    cls.crear_notificacion(
                        tipo='RN',
                        titulo=f'Candidato a renovación - {cliente.nombre_completo} (préstamo #{prestamo.pk})',
                        mensaje=f'{cliente.nombre_completo} terminó de pagar su préstamo con {porcentaje:.0f}% de cuotas a tiempo. Buen candidato para ofrecerle una renovación.',
                        usuario=admin,
                        prioridad='BA',
                        enlace=f'/clientes/{cliente.pk}/'
                    )
            detectados += 1
        return detectados


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

    def ejecutar_respaldo(self):
        """
        Crea el archivo de respaldo (JSON en Postgres, copia del archivo en SQLite),
        actualiza ultimo_respaldo y limpia respaldos viejos según mantener_ultimos.
        Usado tanto por el botón manual de respaldo como por el job automático (D4).
        Retorna (exito: bool, backup_name: str|None, error: str|None).
        """
        import os
        import shutil
        import json
        from datetime import datetime
        from django.conf import settings

        try:
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            db_engine = settings.DATABASES['default']['ENGINE']

            if 'postgresql' in db_engine:
                backup_name = f'backup_{timestamp}.json'
                backup_path = os.path.join(backup_dir, backup_name)

                from core.models import (
                    Cliente, Prestamo, Cuota, TipoNegocio, RutaCobro,
                    ConfiguracionCredito, ConfiguracionPlanilla, PerfilUsuario,
                    RegistroAuditoria, Notificacion
                )
                from django.core import serializers

                all_data = {}
                models_to_export = [
                    ('users', User),
                    ('perfiles', PerfilUsuario),
                    ('tipos_negocio', TipoNegocio),
                    ('rutas_cobro', RutaCobro),
                    ('config_credito', ConfiguracionCredito),
                    ('config_planilla', ConfiguracionPlanilla),
                    ('clientes', Cliente),
                    ('prestamos', Prestamo),
                    ('cuotas', Cuota),
                ]

                for name, model in models_to_export:
                    all_data[name] = json.loads(serializers.serialize('json', model.objects.all()))

                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)
            else:
                backup_name = f'backup_{timestamp}.sqlite3'
                backup_path = os.path.join(backup_dir, backup_name)
                db_path = settings.DATABASES['default']['NAME']
                shutil.copy2(db_path, backup_path)

            self.ultimo_respaldo = timezone.now()
            self.save(update_fields=['ultimo_respaldo'])

            backups = sorted(
                [f for f in os.listdir(backup_dir) if f.startswith('backup_')],
                reverse=True
            )
            for old_backup in backups[self.mantener_ultimos:]:
                os.remove(os.path.join(backup_dir, old_backup))

            return True, backup_name, None
        except Exception as e:
            return False, None, str(e)

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


# ==================== WHATSAPP (B1) ====================

class ConfiguracionWhatsApp(models.Model):
    """
    Configuración global de los mensajes automáticos por WhatsApp. Las
    credenciales de Meta (token, phone_number_id) NO viven acá — van por
    variable de entorno (ver core/whatsapp.py). Fila única (pk=1).
    """
    activo = models.BooleanField(
        default=False,
        verbose_name='WhatsApp activo',
        help_text='Activar recién cuando el número ya esté verificado en Meta y la plantilla aprobada. '
                   'Mientras esté apagado, los comandos de envío no hacen nada.'
    )
    template_recordatorio = models.CharField(
        max_length=100,
        default='recordatorio_cuota',
        verbose_name='Nombre de la plantilla (recordatorio B1)',
        help_text='Debe coincidir exactamente con el nombre de la plantilla ya aprobada en Meta'
    )
    idioma_plantillas = models.CharField(max_length=10, default='es_AR', verbose_name='Idioma de las plantillas')
    hora_envio_recordatorio = models.TimeField(
        default='10:00',
        verbose_name='Hora de envío del recordatorio',
        help_text='Informativo: el horario real lo define el Cron Job en Railway, esto es solo para referencia'
    )

    class Meta:
        verbose_name = 'Configuración de WhatsApp'
        verbose_name_plural = 'Configuración de WhatsApp'

    def __str__(self):
        return 'WhatsApp: ' + ('activo' if self.activo else 'inactivo')

    @classmethod
    def esta_activo(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config.activo

    @classmethod
    def obtener(cls):
        config, _ = cls.objects.get_or_create(pk=1)
        return config


class EnvioWhatsApp(models.Model):
    """
    Registro de cada intento de envío por WhatsApp — auditoría de qué se
    mandó, cuándo, y si funcionó. También sirve para no mandar el mismo
    recordatorio dos veces el mismo día si el Cron Job se corre a mano.
    """
    class Tipo(models.TextChoices):
        RECORDATORIO = 'RE', 'Recordatorio de cuota (B1)'

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='envios_whatsapp',
        verbose_name='Cliente'
    )
    cuota = models.ForeignKey(
        Cuota,
        on_delete=models.CASCADE,
        related_name='envios_whatsapp',
        null=True,
        blank=True,
        verbose_name='Cuota'
    )
    tipo = models.CharField(max_length=2, choices=Tipo.choices, verbose_name='Tipo')
    fecha_envio = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Envío')
    exitoso = models.BooleanField(default=False, verbose_name='Exitoso')
    error = models.TextField(blank=True, null=True, verbose_name='Error')
    message_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='ID de mensaje (Meta)')

    class Meta:
        verbose_name = 'Envío de WhatsApp'
        verbose_name_plural = 'Envíos de WhatsApp'
        ordering = ['-fecha_envio']
        indexes = [
            models.Index(fields=['cuota', 'tipo', 'fecha_envio']),
        ]

    def __str__(self):
        estado = 'OK' if self.exitoso else 'ERROR'
        return f'{self.get_tipo_display()} a {self.cliente.nombre_completo} - {estado}'

    @classmethod
    def ya_enviado_hoy(cls, cuota, tipo):
        """Evita mandar el mismo recordatorio dos veces el mismo día (cada envío es una conversación facturable)"""
        return cls.objects.filter(
            cuota=cuota,
            tipo=tipo,
            fecha_envio__date=fecha_local_hoy(),
            exitoso=True
        ).exists()