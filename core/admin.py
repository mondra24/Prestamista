"""
Configuración del Admin para el Sistema de Gestión de Préstamos
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import Cliente, Prestamo, Cuota, PerfilUsuario

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


# ==================== ADMINISTRACIÓN DE PRÉSTAMOS ====================

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'telefono', 'categoria', 'estado', 'fecha_registro']
    list_filter = ['categoria', 'estado']
    search_fields = ['nombre', 'apellido', 'telefono']
    ordering = ['apellido', 'nombre']
    
    def nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido}"
    nombre_completo.short_description = 'Nombre Completo'


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

