"""
Vistas del Sistema de Gestión de Préstamos
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from decimal import Decimal
import json

from .models import Cliente, Prestamo, Cuota
from .forms import ClienteForm, PrestamoForm, RenovacionPrestamoForm


def logout_view(request):
    """Vista para cerrar sesión"""
    logout(request)
    messages.success(request, 'Has cerrado sesión correctamente.')
    return redirect('login')


class DashboardView(LoginRequiredMixin, TemplateView):
    """Vista principal del dashboard con resumen general"""
    template_name = 'core/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = timezone.now().date()
        
        # Estadísticas del día
        cobros_realizados_hoy = Cuota.objects.filter(
            fecha_pago_real=hoy,
            estado='PA'
        ).aggregate(
            total=Sum('monto_pagado'),
            cantidad=Count('id')
        )
        
        # Cuotas pendientes hoy
        cuotas_pendientes_hoy = Cuota.objects.filter(
            fecha_vencimiento=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).count()
        
        # Cuotas vencidas total
        cuotas_vencidas = Cuota.objects.filter(
            fecha_vencimiento__lt=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).count()
        
        # Total por cobrar hoy
        total_por_cobrar = Cuota.objects.filter(
            fecha_vencimiento=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).aggregate(total=Sum('monto_cuota'))['total'] or Decimal('0.00')
        
        # Estadísticas generales
        prestamos_activos = Prestamo.objects.filter(estado='AC').count()
        clientes_activos = Cliente.objects.filter(estado='AC').count()
        
        # Monto total por cobrar (todas las cuotas pendientes)
        total_cartera = Cuota.objects.filter(
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).aggregate(total=Sum('monto_cuota'))['total'] or Decimal('0.00')
        
        context.update({
            'total_cobrado_hoy': cobros_realizados_hoy['total'] or Decimal('0.00'),
            'cantidad_cobros_hoy': cobros_realizados_hoy['cantidad'] or 0,
            'cuotas_pendientes_hoy': cuotas_pendientes_hoy,
            'cuotas_vencidas': cuotas_vencidas,
            'total_por_cobrar': total_por_cobrar,
            'prestamos_activos': prestamos_activos,
            'clientes_activos': clientes_activos,
            'total_cartera': total_cartera,
            'fecha_hoy': hoy,
        })
        return context


class CobrosView(LoginRequiredMixin, TemplateView):
    """Vista de cobros del día con cuotas pendientes y vencidas"""
    template_name = 'core/cobros.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = timezone.now().date()
        
        # Cuotas del día (pendientes y vencidas)
        cuotas_hoy = Cuota.objects.filter(
            fecha_vencimiento=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).select_related('prestamo', 'prestamo__cliente').order_by('prestamo__cliente__apellido')
        
        # Cuotas vencidas (días anteriores)
        cuotas_vencidas = Cuota.objects.filter(
            fecha_vencimiento__lt=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).select_related('prestamo', 'prestamo__cliente').order_by('fecha_vencimiento')
        
        # Estadísticas del día
        cobros_realizados_hoy = Cuota.objects.filter(
            fecha_pago_real=hoy,
            estado='PA'
        ).aggregate(
            total=Sum('monto_pagado'),
            cantidad=Count('id')
        )
        
        # Total por cobrar hoy
        total_por_cobrar = cuotas_hoy.aggregate(
            total=Sum('monto_cuota')
        )['total'] or Decimal('0.00')
        
        context.update({
            'cuotas_hoy': cuotas_hoy,
            'cuotas_vencidas': cuotas_vencidas,
            'total_cobrado_hoy': cobros_realizados_hoy['total'] or Decimal('0.00'),
            'cantidad_cobros_hoy': cobros_realizados_hoy['cantidad'] or 0,
            'total_por_cobrar': total_por_cobrar,
            'fecha_hoy': hoy,
        })
        return context


# ============== VISTAS DE CLIENTES ==============

class ClienteListView(LoginRequiredMixin, ListView):
    """Lista de clientes"""
    model = Cliente
    template_name = 'core/cliente_list.html'
    context_object_name = 'clientes'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q', '')
        categoria = self.request.GET.get('categoria', '')
        
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda) |
                Q(apellido__icontains=busqueda) |
                Q(telefono__icontains=busqueda)
            )
        
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categorias'] = Cliente.Categoria.choices
        return context


class ClienteCreateView(LoginRequiredMixin, CreateView):
    """Crear nuevo cliente"""
    model = Cliente
    form_class = ClienteForm
    template_name = 'core/cliente_form.html'
    success_url = reverse_lazy('core:cliente_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Cliente creado exitosamente.')
        return super().form_valid(form)


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    """Editar cliente"""
    model = Cliente
    form_class = ClienteForm
    template_name = 'core/cliente_form.html'
    success_url = reverse_lazy('core:cliente_list')
    
    def form_valid(self, form):
        messages.success(self.request, 'Cliente actualizado exitosamente.')
        return super().form_valid(form)


class ClienteDetailView(LoginRequiredMixin, DetailView):
    """Detalle de cliente"""
    model = Cliente
    template_name = 'core/cliente_detail.html'
    context_object_name = 'cliente'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['prestamos'] = self.object.prestamos.all()
        return context


# ============== VISTAS DE PRÉSTAMOS ==============

class PrestamoListView(LoginRequiredMixin, ListView):
    """Lista de préstamos"""
    model = Prestamo
    template_name = 'core/prestamo_list.html'
    context_object_name = 'prestamos'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        estado = self.request.GET.get('estado', '')
        
        if estado:
            queryset = queryset.filter(estado=estado)
        
        return queryset.select_related('cliente')


class PrestamoCreateView(LoginRequiredMixin, CreateView):
    """Crear nuevo préstamo"""
    model = Prestamo
    form_class = PrestamoForm
    template_name = 'core/prestamo_form.html'
    success_url = reverse_lazy('core:prestamo_list')
    
    def get_initial(self):
        initial = super().get_initial()
        cliente_id = self.request.GET.get('cliente')
        if cliente_id:
            initial['cliente'] = cliente_id
        initial['fecha_inicio'] = timezone.now().date()
        return initial
    
    def form_valid(self, form):
        messages.success(self.request, 'Préstamo creado exitosamente. Las cuotas han sido generadas.')
        return super().form_valid(form)


class PrestamoDetailView(LoginRequiredMixin, DetailView):
    """Detalle de préstamo con todas sus cuotas"""
    model = Prestamo
    template_name = 'core/prestamo_detail.html'
    context_object_name = 'prestamo'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cuotas'] = self.object.cuotas.all()
        return context


class RenovarPrestamoView(LoginRequiredMixin, TemplateView):
    """Vista para renovar un préstamo"""
    template_name = 'core/prestamo_renovar.html'
    
    def get_prestamo(self):
        return get_object_or_404(Prestamo, pk=self.kwargs['pk'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prestamo = self.get_prestamo()
        context['prestamo'] = prestamo
        context['saldo_pendiente'] = prestamo.calcular_saldo_para_renovacion()
        context['form'] = kwargs.get('form', RenovacionPrestamoForm(initial={
            'nueva_tasa': prestamo.tasa_interes_porcentaje,
            'nuevas_cuotas': prestamo.cuotas_pactadas,
            'nueva_frecuencia': prestamo.frecuencia,
        }))
        return context
    
    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())
    
    def post(self, request, *args, **kwargs):
        form = RenovacionPrestamoForm(request.POST)
        if form.is_valid():
            prestamo_anterior = self.get_prestamo()
            
            nuevo_prestamo = Prestamo.renovar_prestamo(
                prestamo_anterior=prestamo_anterior,
                nuevo_monto=form.cleaned_data['nuevo_monto'],
                nueva_tasa=form.cleaned_data['nueva_tasa'],
                nuevas_cuotas=form.cleaned_data['nuevas_cuotas'],
                nueva_frecuencia=form.cleaned_data['nueva_frecuencia']
            )
            
            messages.success(
                request, 
                f'Préstamo renovado exitosamente. Nuevo préstamo #{nuevo_prestamo.pk} creado.'
            )
            return redirect('core:prestamo_detail', pk=nuevo_prestamo.pk)
        
        return self.render_to_response(self.get_context_data(form=form))


# ============== VISTAS DE COBROS (AJAX) ==============

@login_required
def cobrar_cuota(request, pk):
    """Registrar pago de cuota via AJAX"""
    if request.method == 'POST':
        try:
            cuota = get_object_or_404(Cuota, pk=pk)
            
            # Obtener datos del body
            try:
                data = json.loads(request.body)
                monto = Decimal(str(data.get('monto', cuota.monto_restante)))
                accion_restante = data.get('accion_restante', 'ignorar')  # 'ignorar', 'proxima', 'especial'
                fecha_especial_str = data.get('fecha_especial', None)
                
                # Convertir fecha especial si existe
                fecha_especial = None
                if fecha_especial_str and accion_restante == 'especial':
                    from datetime import datetime
                    fecha_especial = datetime.strptime(fecha_especial_str, '%Y-%m-%d').date()
                    
            except (json.JSONDecodeError, ValueError):
                monto = None
                accion_restante = 'ignorar'
                fecha_especial = None
            
            # Calcular restante antes del pago
            monto_restante_antes = float(cuota.monto_restante)
            monto_que_quedara = max(0, monto_restante_antes - float(monto or cuota.monto_restante))
            
            cuota.registrar_pago(monto, accion_restante, fecha_especial)
            
            # Mensaje según la acción
            if accion_restante == 'proxima' and monto_que_quedara > 0:
                mensaje = f'Pago registrado. ${monto_que_quedara:.2f} sumado a la próxima cuota.'
            elif accion_restante == 'especial' and monto_que_quedara > 0:
                mensaje = f'Pago registrado. Cuota especial creada por ${monto_que_quedara:.2f}.'
            else:
                mensaje = 'Pago registrado exitosamente'
            
            return JsonResponse({
                'success': True,
                'message': mensaje,
                'cuota': {
                    'id': cuota.pk,
                    'estado': cuota.estado,
                    'estado_display': cuota.get_estado_display(),
                    'monto_pagado': float(cuota.monto_pagado),
                    'monto_restante': float(cuota.monto_restante),
                },
                'prestamo': {
                    'progreso': cuota.prestamo.progreso_porcentaje,
                    'estado': cuota.prestamo.estado,
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)


@login_required
def obtener_cuotas_hoy(request):
    """Obtener cuotas del día via AJAX (para actualización en tiempo real)"""
    hoy = timezone.now().date()
    
    cuotas = Cuota.objects.filter(
        fecha_vencimiento=hoy,
        estado__in=['PE', 'PC'],
        prestamo__estado='AC'
    ).select_related('prestamo', 'prestamo__cliente').values(
        'id', 'numero_cuota', 'monto_cuota', 'estado',
        'prestamo__id', 'prestamo__cuotas_pactadas',
        'prestamo__cliente__nombre', 'prestamo__cliente__apellido'
    )
    
    return JsonResponse({
        'cuotas': list(cuotas)
    })


# ============== VISTAS DE REPORTES ==============

class CierreCajaView(LoginRequiredMixin, TemplateView):
    """Vista de cierre de caja del día"""
    template_name = 'core/cierre_caja.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener fecha del filtro o usar hoy
        fecha_str = self.request.GET.get('fecha')
        if fecha_str:
            from datetime import datetime
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        else:
            fecha = timezone.now().date()
        
        # Pagos del día
        pagos_del_dia = Cuota.objects.filter(
            fecha_pago_real=fecha,
            estado='PA'
        ).select_related('prestamo', 'prestamo__cliente').order_by(
            'prestamo__cliente__apellido'
        )
        
        # Total cobrado
        total_cobrado = pagos_del_dia.aggregate(
            total=Sum('monto_pagado')
        )['total'] or Decimal('0.00')
        
        context.update({
            'fecha': fecha,
            'pagos': pagos_del_dia,
            'total_cobrado': total_cobrado,
            'cantidad_pagos': pagos_del_dia.count(),
        })
        return context


class PlanillaImpresionView(LoginRequiredMixin, TemplateView):
    """Vista optimizada para impresión"""
    template_name = 'core/planilla_impresion.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        fecha_str = self.request.GET.get('fecha')
        if fecha_str:
            from datetime import datetime
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        else:
            fecha = timezone.now().date()
        
        pagos = Cuota.objects.filter(
            fecha_pago_real=fecha,
            estado='PA'
        ).select_related('prestamo', 'prestamo__cliente').order_by(
            'prestamo__cliente__apellido'
        )
        
        total = pagos.aggregate(total=Sum('monto_pagado'))['total'] or Decimal('0.00')
        
        context.update({
            'fecha': fecha,
            'pagos': pagos,
            'total': total,
        })
        return context


class ReporteGeneralView(LoginRequiredMixin, TemplateView):
    """Vista con reportes generales"""
    template_name = 'core/reporte_general.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estadísticas generales
        context['total_clientes'] = Cliente.objects.filter(estado='AC').count()
        context['prestamos_activos'] = Prestamo.objects.filter(estado='AC').count()
        
        # Capital en la calle (monto pendiente de todos los préstamos activos)
        prestamos_activos = Prestamo.objects.filter(estado='AC')
        capital_calle = sum(p.monto_pendiente for p in prestamos_activos)
        context['capital_en_calle'] = capital_calle
        
        # Cuotas vencidas
        hoy = timezone.now().date()
        context['cuotas_vencidas'] = Cuota.objects.filter(
            fecha_vencimiento__lt=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).count()
        
        # Distribución por categoría de clientes
        context['clientes_por_categoria'] = Cliente.objects.values('categoria').annotate(
            cantidad=Count('id')
        )
        
        return context


# ============== VISTAS DE GESTIÓN DE USUARIOS ==============

from django.contrib.auth.models import User
from .models import PerfilUsuario
from .forms import UsuarioForm, UsuarioEditForm


class UsuarioListView(LoginRequiredMixin, ListView):
    """Lista de usuarios del sistema"""
    model = User
    template_name = 'core/usuario_list.html'
    context_object_name = 'usuarios'
    
    def dispatch(self, request, *args, **kwargs):
        # Solo admins pueden ver usuarios
        if not hasattr(request.user, 'perfil') or not request.user.perfil.es_admin:
            if not request.user.is_superuser:
                messages.error(request, 'No tienes permiso para acceder a esta sección.')
                return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.select_related('perfil').order_by('-date_joined')


class UsuarioCreateView(LoginRequiredMixin, TemplateView):
    """Crear nuevo usuario"""
    template_name = 'core/usuario_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Solo admins pueden crear usuarios
        if not hasattr(request.user, 'perfil') or not request.user.perfil.es_admin:
            if not request.user.is_superuser:
                messages.error(request, 'No tienes permiso para crear usuarios.')
                return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = kwargs.get('form', UsuarioForm())
        context['titulo'] = 'Nuevo Usuario'
        return context
    
    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())
    
    def post(self, request, *args, **kwargs):
        form = UsuarioForm(request.POST)
        if form.is_valid():
            # Crear usuario
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
            )
            
            # Actualizar perfil
            if hasattr(user, 'perfil'):
                user.perfil.rol = form.cleaned_data['rol']
                user.perfil.telefono = form.cleaned_data['telefono']
                user.perfil.save()
            else:
                PerfilUsuario.objects.create(
                    user=user,
                    rol=form.cleaned_data['rol'],
                    telefono=form.cleaned_data['telefono']
                )
            
            messages.success(request, f'Usuario "{user.username}" creado exitosamente.')
            return redirect('core:usuario_list')
        
        return self.render_to_response(self.get_context_data(form=form))


class UsuarioEditView(LoginRequiredMixin, TemplateView):
    """Editar usuario existente"""
    template_name = 'core/usuario_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Solo admins pueden editar usuarios
        if not hasattr(request.user, 'perfil') or not request.user.perfil.es_admin:
            if not request.user.is_superuser:
                messages.error(request, 'No tienes permiso para editar usuarios.')
                return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_user(self):
        return get_object_or_404(User, pk=self.kwargs['pk'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.get_user()
        context['usuario_edit'] = user
        context['titulo'] = f'Editar Usuario: {user.username}'
        
        if 'form' not in kwargs:
            initial = {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'rol': user.perfil.rol if hasattr(user, 'perfil') else 'CO',
                'telefono': user.perfil.telefono if hasattr(user, 'perfil') else '',
                'activo': user.perfil.activo if hasattr(user, 'perfil') else True,
            }
            context['form'] = UsuarioEditForm(initial=initial)
        else:
            context['form'] = kwargs['form']
        
        return context
    
    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())
    
    def post(self, request, *args, **kwargs):
        form = UsuarioEditForm(request.POST)
        user = self.get_user()
        
        if form.is_valid():
            # Actualizar usuario
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.email = form.cleaned_data['email']
            
            # Cambiar contraseña si se proporcionó
            if form.cleaned_data['password']:
                user.set_password(form.cleaned_data['password'])
            
            user.save()
            
            # Actualizar perfil
            if hasattr(user, 'perfil'):
                user.perfil.rol = form.cleaned_data['rol']
                user.perfil.telefono = form.cleaned_data['telefono']
                user.perfil.activo = form.cleaned_data['activo']
                user.perfil.save()
            
            messages.success(request, f'Usuario "{user.username}" actualizado exitosamente.')
            return redirect('core:usuario_list')
        
        return self.render_to_response(self.get_context_data(form=form))


@login_required
def toggle_usuario_activo(request, pk):
    """Activar/desactivar un usuario"""
    # Verificar permisos
    if not hasattr(request.user, 'perfil') or not request.user.perfil.es_admin:
        if not request.user.is_superuser:
            messages.error(request, 'No tienes permiso para realizar esta acción.')
            return redirect('core:dashboard')
    
    user = get_object_or_404(User, pk=pk)
    
    # No permitir desactivarse a sí mismo
    if user == request.user:
        messages.error(request, 'No puedes desactivarte a ti mismo.')
        return redirect('core:usuario_list')
    
    if hasattr(user, 'perfil'):
        user.perfil.activo = not user.perfil.activo
        user.perfil.save()
        user.is_active = user.perfil.activo
        user.save()
        
        estado = 'activado' if user.perfil.activo else 'desactivado'
        messages.success(request, f'Usuario "{user.username}" {estado}.')
    
    return redirect('core:usuario_list')
