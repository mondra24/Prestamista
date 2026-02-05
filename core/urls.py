"""
URLs de la aplicación Core - Sistema de Gestión de Préstamos
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Dashboard principal
    path('', views.DashboardView.as_view(), name='dashboard'),
    
    # Cobros del día
    path('cobros/', views.CobrosView.as_view(), name='cobros'),
    
    # Autenticación
    path('logout/', views.logout_view, name='logout'),
    
    # Clientes
    path('clientes/', views.ClienteListView.as_view(), name='cliente_list'),
    path('clientes/nuevo/', views.ClienteCreateView.as_view(), name='cliente_create'),
    path('clientes/<int:pk>/', views.ClienteDetailView.as_view(), name='cliente_detail'),
    path('clientes/<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente_update'),
    
    # Préstamos
    path('prestamos/', views.PrestamoListView.as_view(), name='prestamo_list'),
    path('prestamos/nuevo/', views.PrestamoCreateView.as_view(), name='prestamo_create'),
    path('prestamos/<int:pk>/', views.PrestamoDetailView.as_view(), name='prestamo_detail'),
    path('prestamos/<int:pk>/renovar/', views.RenovarPrestamoView.as_view(), name='prestamo_renovar'),
    
    # Cobros (AJAX)
    path('api/cobrar/<int:pk>/', views.cobrar_cuota, name='cobrar_cuota'),
    path('api/cuotas-hoy/', views.obtener_cuotas_hoy, name='cuotas_hoy'),
    
    # Reportes
    path('cierre-caja/', views.CierreCajaView.as_view(), name='cierre_caja'),
    path('planilla/', views.PlanillaImpresionView.as_view(), name='planilla_impresion'),
    path('reportes/', views.ReporteGeneralView.as_view(), name='reporte_general'),
    
    # Gestión de Usuarios
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_list'),
    path('usuarios/nuevo/', views.UsuarioCreateView.as_view(), name='usuario_create'),
    path('usuarios/<int:pk>/editar/', views.UsuarioEditView.as_view(), name='usuario_edit'),
    path('usuarios/<int:pk>/toggle/', views.toggle_usuario_activo, name='usuario_toggle'),
]
