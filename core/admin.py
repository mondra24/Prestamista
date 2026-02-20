"""
Configuración del Admin para el Sistema de Gestión de Préstamos
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import (
    Cliente, Prestamo, Cuota, PerfilUsuario, RutaCobro,
    TipoNegocio, ConfiguracionCredito, ColumnaPlanilla, ConfiguracionPlanilla,
    RegistroAuditoria, Notificacion, ConfiguracionRespaldo,
    ConfiguracionMora, InteresMora, HistorialModificacionPago
)

User = get_user_model()


# ==================== RESTRINGIR ADMIN A SUPERUSUARIOS ====================

class SuperuserAdminSite(admin.AdminSite):
    """Admin site restringido solo a superusuarios (desarrolladores)"""
    def has_permission(self, request):
        return request.user.is_active and request.user.is_superuser

# Reemplazar el site default
admin.site.__class__ = SuperuserAdminSite


# ==================== ADMINISTRACIÓN DE USUARIOS ====================

class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    verbose_name = 'Perfil'
    verbose_name_plural = 'Perfil de Usuario'


class CustomUserAdmin(BaseUserAdmin):
    inlines = [PerfilUsuarioInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_rol', 'is_active', 'is_staff']
    list_filter = ['is_active', 'is_staff', 'perfil__rol']
    
    def get_rol(self, obj):
        if hasattr(obj, 'perfil'):
            return obj.perfil.get_rol_display()
        return '-'
    get_rol.short_description = 'Rol'
    get_rol.admin_order_field = 'perfil__rol'


# Desregistrar el User default y registrar con nuestro admin personalizado
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ['user', 'rol', 'fecha_creacion']
    list_filter = ['rol']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user']


# ==================== RUTAS DE COBRO ====================

@admin.register(RutaCobro)
class RutaCobroAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion', 'orden', 'color', 'activa', 'cantidad_clientes']
    list_filter = ['activa']
    search_fields = ['nombre', 'descripcion']
    ordering = ['orden', 'nombre']
    list_editable = ['orden', 'activa', 'color']
    
    def cantidad_clientes(self, obj):
        return obj.clientes.count()
    cantidad_clientes.short_description = 'Clientes'


# ==================== TIPOS DE NEGOCIO ====================

@admin.register(TipoNegocio)
class TipoNegocioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'limite_credito_sugerido', 'orden', 'activo', 'cantidad_clientes']
    list_filter = ['activo']
    search_fields = ['nombre', 'descripcion']
    ordering = ['orden', 'nombre']
    list_editable = ['orden', 'activo', 'limite_credito_sugerido']
    
    def cantidad_clientes(self, obj):
        return obj.clientes.count()
    cantidad_clientes.short_description = 'Clientes'


# ==================== CONFIGURACIÓN DE CRÉDITO ====================

@admin.register(ConfiguracionCredito)
class ConfiguracionCreditoAdmin(admin.ModelAdmin):
    list_display = ['categoria', 'limite_maximo', 'porcentaje_sobre_deuda', 
                    'puede_renovar_con_deuda', 'dias_minimos_para_renovar', 'activo']
    list_filter = ['activo', 'puede_renovar_con_deuda']
    list_editable = ['limite_maximo', 'porcentaje_sobre_deuda', 'puede_renovar_con_deuda', 
                     'dias_minimos_para_renovar', 'activo']
    
    fieldsets = (
        ('Categoría', {
            'fields': ('categoria', 'activo')
        }),
        ('Límites de Crédito', {
            'fields': ('limite_maximo', 'porcentaje_sobre_deuda'),
            'description': 'Configure cuánto puede prestar a clientes de esta categoría'
        }),
        ('Restricciones de Renovación', {
            'fields': ('puede_renovar_con_deuda', 'dias_minimos_para_renovar'),
            'description': 'Configure las reglas para renovar préstamos'
        }),
    )


# ==================== CONFIGURACIÓN DE PLANILLA ====================

class ColumnaPlanillaInline(admin.TabularInline):
    model = ColumnaPlanilla
    extra = 1
    ordering = ['orden']


@admin.register(ColumnaPlanilla)
class ColumnaPlanillaAdmin(admin.ModelAdmin):
    list_display = ['nombre_columna', 'titulo_personalizado', 'orden', 'ancho', 'activa']
    list_filter = ['activa']
    list_editable = ['orden', 'activa', 'titulo_personalizado', 'ancho']
    ordering = ['orden']


@admin.register(ConfiguracionPlanilla)
class ConfiguracionPlanillaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'titulo_reporte', 'agrupar_por_ruta', 'agrupar_por_categoria', 
                    'incluir_vencidas', 'es_default']
    list_filter = ['agrupar_por_ruta', 'agrupar_por_categoria', 'es_default']
    list_editable = ['es_default']
    
    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'es_default')
        }),
        ('Títulos', {
            'fields': ('titulo_reporte', 'subtitulo')
        }),
        ('Visualización', {
            'fields': ('mostrar_logo', 'mostrar_fecha', 'mostrar_totales', 'mostrar_firmas')
        }),
        ('Agrupación y Filtros', {
            'fields': ('agrupar_por_ruta', 'agrupar_por_categoria', 'incluir_vencidas', 'filtrar_por_ruta')
        }),
    )


# ==================== ADMINISTRACIÓN DE PRÉSTAMOS ====================

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'dni', 'telefono', 'tipo_negocio', 'categoria', 
                    'limite_credito', 'get_maximo_prestable', 'ruta', 'estado']
    list_filter = ['categoria', 'estado', 'ruta', 'tipo_negocio']
    search_fields = ['nombre', 'apellido', 'telefono', 'tipo_comercio', 'dni']
    ordering = ['apellido', 'nombre']
    list_editable = ['categoria', 'ruta']
    autocomplete_fields = ['tipo_negocio', 'ruta']
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'apellido', 'dni', 'telefono', 'direccion')
        }),
        ('Contactos de Referencia', {
            'fields': ('referencia1_nombre', 'referencia1_telefono', 'referencia2_nombre', 'referencia2_telefono'),
            'description': 'Contactos de referencia con nombre y parentesco'
        }),
        ('Tipo de Negocio', {
            'fields': ('tipo_negocio', 'tipo_comercio'),
            'description': 'Seleccione un tipo de negocio o escriba uno personalizado'
        }),
        ('Crédito y Cobro', {
            'fields': ('limite_credito', 'ruta', 'dia_pago_preferido'),
            'description': 'Límite individual (0 = usar límite de categoría/tipo negocio)'
        }),
        ('Clasificación', {
            'fields': ('categoria', 'estado', 'notas')
        }),
    )
    
    def nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido}"
    nombre_completo.short_description = 'Nombre'
    
    def get_maximo_prestable(self, obj):
        maximo = obj.maximo_prestable
        if maximo is not None:
            return f"${maximo:,.0f}"
        return "Sin límite"
    get_maximo_prestable.short_description = 'Máx. Prestable'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(usuario=request.user)
        return qs
    
    def save_model(self, request, obj, form, change):
        if not change and not request.user.is_superuser:
            obj.usuario = request.user
        super().save_model(request, obj, form, change)


class CuotaInline(admin.TabularInline):
    model = Cuota
    extra = 0
    readonly_fields = ['numero_cuota', 'monto_cuota', 'fecha_vencimiento', 'estado', 'monto_pagado', 'fecha_pago_real', 'cobrado_por']
    can_delete = False


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = ['id', 'cliente', 'monto_solicitado', 'monto_total_a_pagar', 'cuotas_pactadas', 'frecuencia', 'estado', 'fecha_inicio']
    list_filter = ['estado', 'frecuencia', 'fecha_inicio']
    search_fields = ['cliente__nombre', 'cliente__apellido']
    raw_id_fields = ['cliente']
    readonly_fields = ['monto_total_a_pagar', 'fecha_finalizacion', 'fecha_creacion']
    inlines = [CuotaInline]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(cliente__usuario=request.user)
        return qs


@admin.register(Cuota)
class CuotaAdmin(admin.ModelAdmin):
    list_display = ['prestamo', 'numero_cuota', 'monto_cuota', 'fecha_vencimiento', 'estado', 'fecha_pago_real', 'cobrado_por']
    list_filter = ['estado', 'fecha_vencimiento', 'cobrado_por']
    search_fields = ['prestamo__cliente__nombre', 'prestamo__cliente__apellido']
    raw_id_fields = ['prestamo']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.filter(prestamo__cliente__usuario=request.user)
        return qs


# ==================== AUDITORÍA Y NOTIFICACIONES ====================

@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ['fecha_hora', 'usuario', 'tipo_accion', 'tipo_modelo', 'modelo_id', 'descripcion_corta']
    list_filter = ['tipo_accion', 'tipo_modelo', 'fecha_hora']
    search_fields = ['descripcion', 'usuario__username']
    readonly_fields = ['usuario', 'tipo_accion', 'tipo_modelo', 'modelo_id', 'descripcion', 
                       'datos_anteriores', 'datos_nuevos', 'ip_address', 'fecha_hora']
    date_hierarchy = 'fecha_hora'
    
    def descripcion_corta(self, obj):
        return obj.descripcion[:100] + '...' if len(obj.descripcion) > 100 else obj.descripcion
    descripcion_corta.short_description = 'Descripción'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'tipo', 'prioridad', 'usuario', 'leida', 'fecha_creacion']
    list_filter = ['tipo', 'prioridad', 'leida', 'fecha_creacion']
    search_fields = ['titulo', 'mensaje', 'usuario__username']
    readonly_fields = ['fecha_creacion', 'fecha_lectura']
    list_editable = ['leida']
    date_hierarchy = 'fecha_creacion'
    
    actions = ['marcar_leidas', 'marcar_no_leidas']
    
    def marcar_leidas(self, request, queryset):
        queryset.update(leida=True)
    marcar_leidas.short_description = 'Marcar como leídas'
    
    def marcar_no_leidas(self, request, queryset):
        queryset.update(leida=False)
    marcar_no_leidas.short_description = 'Marcar como no leídas'


@admin.register(ConfiguracionRespaldo)
class ConfiguracionRespaldoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activo', 'frecuencia_horas', 'mantener_ultimos', 'ultimo_respaldo']
    list_editable = ['activo', 'frecuencia_horas', 'mantener_ultimos']


# ==================== CONFIGURACIÓN DE MORA ====================

@admin.register(ConfiguracionMora)
class ConfiguracionMoraAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'porcentaje_diario', 'dias_gracia', 'monto_minimo_mora', 
                    'aplicar_automaticamente', 'activo']
    list_editable = ['porcentaje_diario', 'dias_gracia', 'aplicar_automaticamente', 'activo']
    list_filter = ['activo', 'aplicar_automaticamente']
    
    fieldsets = (
        ('Configuración General', {
            'fields': ('nombre', 'activo')
        }),
        ('Cálculo de Interés', {
            'fields': ('porcentaje_diario', 'dias_gracia', 'monto_minimo_mora'),
            'description': 'Configure cómo se calculará el interés por mora'
        }),
        ('Automatización', {
            'fields': ('aplicar_automaticamente',),
            'description': 'Si está activo, el interés se calcula automáticamente al registrar pagos'
        }),
    )


@admin.register(InteresMora)
class InteresMoraAdmin(admin.ModelAdmin):
    list_display = ['cuota', 'fecha_calculo', 'dias_mora', 'porcentaje_aplicado', 
                    'monto_base', 'monto_interes', 'pagado', 'agregado_manualmente']
    list_filter = ['pagado', 'agregado_manualmente', 'fecha_calculo']
    search_fields = ['cuota__prestamo__cliente__nombre', 'cuota__prestamo__cliente__apellido']
    readonly_fields = ['fecha_calculo']
    raw_id_fields = ['cuota']
    date_hierarchy = 'fecha_calculo'


@admin.register(HistorialModificacionPago)
class HistorialModificacionPagoAdmin(admin.ModelAdmin):
    list_display = ['cuota', 'tipo_modificacion', 'monto_pagado', 'monto_restante_transferido',
                    'monto_cuota_anterior', 'monto_cuota_nuevo', 'interes_mora', 'usuario', 'fecha_modificacion']
    list_filter = ['tipo_modificacion', 'fecha_modificacion', 'metodo_pago']
    search_fields = ['cuota__prestamo__cliente__nombre', 'cuota__prestamo__cliente__apellido', 'notas']
    readonly_fields = ['fecha_modificacion']
    raw_id_fields = ['cuota', 'cuota_relacionada']
    date_hierarchy = 'fecha_modificacion'
