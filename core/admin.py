"""
Configuración del Admin para el Sistema de Gestión de Préstamos
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import (
    Cliente, Prestamo, Cuota, PerfilUsuario, RutaCobro,
    TipoNegocio, ConfiguracionCredito, ColumnaPlanilla, ConfiguracionPlanilla
)

User = get_user_model()


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
    list_display = ['nombre_completo', 'telefono', 'tipo_negocio', 'categoria', 
                    'limite_credito', 'get_maximo_prestable', 'ruta', 'estado']
    list_filter = ['categoria', 'estado', 'ruta', 'tipo_negocio']
    search_fields = ['nombre', 'apellido', 'telefono', 'tipo_comercio']
    ordering = ['apellido', 'nombre']
    list_editable = ['categoria', 'ruta']
    autocomplete_fields = ['tipo_negocio', 'ruta']
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'apellido', 'telefono', 'direccion')
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


class CuotaInline(admin.TabularInline):
    model = Cuota
    extra = 0
    readonly_fields = ['numero_cuota', 'monto_cuota', 'fecha_vencimiento', 'estado', 'monto_pagado', 'fecha_pago_real']
    can_delete = False


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = ['id', 'cliente', 'monto_solicitado', 'monto_total_a_pagar', 'cuotas_pactadas', 'frecuencia', 'estado', 'fecha_inicio']
    list_filter = ['estado', 'frecuencia', 'fecha_inicio']
    search_fields = ['cliente__nombre', 'cliente__apellido']
    raw_id_fields = ['cliente']
    readonly_fields = ['monto_total_a_pagar', 'fecha_finalizacion', 'fecha_creacion']
    inlines = [CuotaInline]


@admin.register(Cuota)
class CuotaAdmin(admin.ModelAdmin):
    list_display = ['prestamo', 'numero_cuota', 'monto_cuota', 'fecha_vencimiento', 'estado', 'fecha_pago_real']
    list_filter = ['estado', 'fecha_vencimiento']
    search_fields = ['prestamo__cliente__nombre', 'prestamo__cliente__apellido']
    raw_id_fields = ['prestamo']

