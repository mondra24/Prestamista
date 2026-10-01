"""
Vistas del Sistema de Gestión de Préstamos
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Sum, Count, Q, F, Prefetch, Avg
from django.db.models.functions import TruncMonth
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from decimal import Decimal
from datetime import date, timedelta
import json

from .models import Cliente, Prestamo, Cuota, ConfiguracionMora, ConfiguracionMoraReciente, HistorialModificacionPago, NotaSeguimiento, fecha_local_hoy, ConfiguracionMensajesAutomaticos, DIAS_SEMANA_CODIGOS, TareaPendiente
from .forms import ClienteForm, PrestamoForm, RenovacionPrestamoForm
from . import whatsapp_bridge


def es_usuario_admin(user):
    """Verifica si el usuario es superusuario o tiene rol Administrador"""
    if user.is_superuser:
        return True
    return hasattr(user, 'perfil') and user.perfil.es_admin


def es_superadmin(user):
    """Verifica si el usuario es superusuario (solo desarrolladores)"""
    return user.is_superuser


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
        hoy = fecha_local_hoy()
        
        # Filtro base por usuario (admin ve todo)
        cliente_filter = {}
        if not es_usuario_admin(self.request.user):
            cliente_filter['prestamo__cobrador'] = self.request.user
        
        # Estadísticas del día (incluye pagos completos y parciales)
        cobros_realizados_hoy = Cuota.objects.filter(
            fecha_pago_real=hoy,
            estado__in=['PA', 'PC'],
            **cliente_filter
        ).aggregate(
            total_capital=Sum('monto_pagado'),
            total_mora=Sum('interes_mora_cobrado'),
            cantidad=Count('id')
        )
        total_cobrado_hoy_dash = (cobros_realizados_hoy['total_capital'] or Decimal('0.00')) + \
                                 (cobros_realizados_hoy['total_mora'] or Decimal('0.00'))

        # Cuotas pendientes hoy
        cuotas_pendientes_hoy = Cuota.objects.filter(
            fecha_vencimiento=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC',
            **cliente_filter
        ).count()
        
        # Cuotas vencidas total
        cuotas_vencidas = Cuota.objects.filter(
            fecha_vencimiento__lt=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC',
            **cliente_filter
        ).count()
        
        # Total por cobrar hoy (capital pendiente real)
        total_por_cobrar = Cuota.objects.filter(
            fecha_vencimiento=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC',
            **cliente_filter
        ).aggregate(total=Sum(F('monto_cuota') - F('monto_pagado')))['total'] or Decimal('0.00')

        # Estadísticas generales (filtradas por usuario)
        pendiente_expr = F('monto_cuota') - F('monto_pagado')
        cartera_filter = {'estado__in': ['PE', 'PC'], 'prestamo__estado': 'AC'}
        if not es_usuario_admin(self.request.user):
            prestamos_activos = Prestamo.objects.filter(estado='AC', cobrador=self.request.user).count()
            clientes_activos = Cliente.objects.filter(estado='AC', usuario=self.request.user).count()
            cartera_filter['prestamo__cobrador'] = self.request.user
        else:
            prestamos_activos = Prestamo.objects.filter(estado='AC').count()
            clientes_activos = Cliente.objects.filter(estado='AC').count()

        total_cartera = Cuota.objects.filter(
            **cartera_filter
        ).aggregate(total=Sum(pendiente_expr))['total'] or Decimal('0.00')

        context.update({
            'total_cobrado_hoy': total_cobrado_hoy_dash,
            'cantidad_cobros_hoy': cobros_realizados_hoy['cantidad'] or 0,
            'cuotas_pendientes_hoy': cuotas_pendientes_hoy,
            'cuotas_vencidas': cuotas_vencidas,
            'total_por_cobrar': total_por_cobrar,
            'prestamos_activos': prestamos_activos,
            'clientes_activos': clientes_activos,
            'total_cartera': total_cartera,
            'mora_total_pendiente': Decimal('0.00'),
            'fecha_hoy': hoy,
        })
        return context


class CobrosView(LoginRequiredMixin, TemplateView):
    """Vista de cobros del día con cuotas pendientes y vencidas"""
    template_name = 'core/cobros.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from datetime import timedelta
        from .models import RutaCobro, ConfiguracionMora
        hoy = fecha_local_hoy()
        
        # Base queryset - filtrar por usuario si no es admin
        base_filter = {}
        if not es_usuario_admin(self.request.user):
            base_filter['prestamo__cobrador'] = self.request.user
        
        # Cuotas del día (pendientes) - ordenadas por ruta
        cuotas_hoy = Cuota.objects.filter(
            fecha_vencimiento=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC',
            **base_filter
        ).select_related(
            'prestamo', 'prestamo__cliente', 'prestamo__cliente__ruta', 'prestamo__cliente__usuario', 'prestamo__cobrador'
        ).prefetch_related('prestamo__notas_seguimiento').order_by(
            'prestamo__cliente__ruta__orden',
            'prestamo__cliente__ruta__nombre',
            'prestamo__cliente__apellido'
        )

        # Mora reciente / Vencidas (días anteriores): el corte configurable
        # (ConfiguracionMoraReciente) separa la mora que todavía está dentro
        # del margen de tolerancia de pago del cliente de la deuda vieja,
        # que antes se mezclaba todo en "Vencidas".
        dias_corte_mora = ConfiguracionMoraReciente.obtener_dias_corte()
        fecha_corte_mora = hoy - timedelta(days=dias_corte_mora)

        cuotas_mora_reciente = Cuota.objects.filter(
            fecha_vencimiento__lt=hoy,
            fecha_vencimiento__gte=fecha_corte_mora,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC',
            **base_filter
        ).select_related(
            'prestamo', 'prestamo__cliente', 'prestamo__cliente__ruta', 'prestamo__cliente__usuario', 'prestamo__cobrador'
        ).prefetch_related('prestamo__notas_seguimiento').order_by(
            'prestamo__cliente__ruta__orden',
            'prestamo__cliente__ruta__nombre',
            'fecha_vencimiento'
        )

        cuotas_vencidas = Cuota.objects.filter(
            fecha_vencimiento__lt=fecha_corte_mora,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC',
            **base_filter
        ).select_related(
            'prestamo', 'prestamo__cliente', 'prestamo__cliente__ruta', 'prestamo__cliente__usuario', 'prestamo__cobrador'
        ).prefetch_related('prestamo__notas_seguimiento').order_by(
            'prestamo__cliente__ruta__orden',
            'prestamo__cliente__ruta__nombre',
            'fecha_vencimiento'
        )

        # Cuotas próximas (próximos 30 días) - ordenadas por fecha y ruta
        cuotas_proximas = Cuota.objects.filter(
            fecha_vencimiento__gt=hoy,
            fecha_vencimiento__lte=hoy + timedelta(days=30),
            estado__in=['PE', 'PC'],
            prestamo__estado='AC',
            **base_filter
        ).select_related(
            'prestamo', 'prestamo__cliente', 'prestamo__cliente__ruta', 'prestamo__cliente__usuario', 'prestamo__cobrador'
        ).prefetch_related('prestamo__notas_seguimiento').order_by(
            'fecha_vencimiento',
            'prestamo__cliente__ruta__orden',
            'prestamo__cliente__ruta__nombre'
        )
        
        # Separar próxima semana de resto del mes
        cuotas_semana = [c for c in cuotas_proximas if c.fecha_vencimiento <= hoy + timedelta(days=7)]
        cuotas_mes = [c for c in cuotas_proximas if c.fecha_vencimiento > hoy + timedelta(days=7)]

        # Próximos 7 días desglosados día por día (con subtotal), para que el
        # cobrador vea de un vistazo cuánto vence cada día sin abrir todo junto.
        # Nota: se arma el nombre del día a mano (no con |date:"D") porque el
        # catálogo de traducción es-ar de Django devuelve el abreviado sin
        # tilde ("Mie" en vez de "Mié") aunque el nombre completo sí traduce bien.
        from collections import OrderedDict
        DIAS_ABREV = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        dias_semana_map = OrderedDict()
        for i in range(1, 8):
            fecha_dia = hoy + timedelta(days=i)
            dias_semana_map[fecha_dia] = {
                'fecha': fecha_dia,
                'nombre_dia': DIAS_ABREV[fecha_dia.weekday()],
                'cuotas': [],
                'total': Decimal('0.00'),
            }
        for c in cuotas_semana:
            dia = dias_semana_map.get(c.fecha_vencimiento)
            if dia is not None:
                dia['cuotas'].append(c)
                dia['total'] += c.monto_restante
        dias_semana_list = [d for d in dias_semana_map.values() if d['cuotas']]
        
        # Estadísticas del día
        cobros_filter = {'fecha_pago_real': hoy, 'estado__in': ['PA', 'PC']}
        if not es_usuario_admin(self.request.user):
            cobros_filter['prestamo__cobrador'] = self.request.user

        cobros_realizados_hoy = Cuota.objects.filter(
            **cobros_filter
        ).aggregate(
            total_capital=Sum('monto_pagado'),
            total_mora=Sum('interes_mora_cobrado'),
            cantidad=Count('id')
        )
        total_cobrado_hoy = (cobros_realizados_hoy['total_capital'] or Decimal('0.00')) + \
                            (cobros_realizados_hoy['total_mora'] or Decimal('0.00'))

        pendiente_expr = F('monto_cuota') - F('monto_pagado')

        # Total por cobrar hoy (capital pendiente real)
        total_por_cobrar = cuotas_hoy.aggregate(
            total=Sum(pendiente_expr)
        )['total'] or Decimal('0.00')

        # Total próximos (capital pendiente real)
        total_proximas = cuotas_proximas.aggregate(
            total=Sum(pendiente_expr)
        )['total'] or Decimal('0.00')

        # Total vencidas / mora reciente: solo capital pendiente. La mora la
        # registra el cobrador a mano desde el modal del lápiz; no se suma
        # automática.
        total_vencidas = cuotas_vencidas.aggregate(
            total=Sum(pendiente_expr)
        )['total'] or Decimal('0.00')

        total_mora_reciente = cuotas_mora_reciente.aggregate(
            total=Sum(pendiente_expr)
        )['total'] or Decimal('0.00')
        
        # Obtener rutas activas para filtrado
        rutas = RutaCobro.objects.filter(activa=True).order_by('orden', 'nombre')

        # Obtener configuración de mora
        config_mora = ConfiguracionMora.obtener_config_activa()

        # Repaso de la semana (A5): cuotas que vencieron en los últimos 7 días,
        # separadas en cobradas vs. pendientes. Se excluyen préstamos renovados
        # (sus cuotas quedan marcadas PA al renovar, pero no fueron cobradas de verdad).
        inicio_semana_pasada = hoy - timedelta(days=6)
        cuotas_repaso_semana = list(Cuota.objects.filter(
            fecha_vencimiento__gte=inicio_semana_pasada,
            fecha_vencimiento__lte=hoy,
            prestamo__estado='AC',
            **base_filter
        ).select_related('prestamo', 'prestamo__cliente', 'prestamo__cliente__ruta').order_by('-fecha_vencimiento'))

        repaso_semana_cobradas = [c for c in cuotas_repaso_semana if c.estado == 'PA']
        repaso_semana_pendientes = [c for c in cuotas_repaso_semana if c.estado in ('PE', 'PC')]
        repaso_semana_total_cobrado = sum((c.monto_pagado for c in repaso_semana_cobradas), Decimal('0.00'))
        repaso_semana_total_pendiente = sum((c.monto_restante for c in repaso_semana_pendientes), Decimal('0.00'))

        context.update({
            'cuotas_hoy': cuotas_hoy,
            'cuotas_vencidas': cuotas_vencidas,
            'cuotas_mora_reciente': cuotas_mora_reciente,
            'cuotas_proximas': cuotas_proximas,
            'cuotas_semana': cuotas_semana,
            'cuotas_mes': cuotas_mes,
            'dias_semana_list': dias_semana_list,
            'total_cobrado_hoy': total_cobrado_hoy,
            'cantidad_cobros_hoy': cobros_realizados_hoy['cantidad'] or 0,
            'total_por_cobrar': total_por_cobrar,
            'total_dia_completo': total_cobrado_hoy + total_por_cobrar,
            'total_proximas': total_proximas,
            'total_vencidas': total_vencidas,
            'total_mora_reciente': total_mora_reciente,
            'dias_corte_mora': dias_corte_mora,
            'fecha_hoy': hoy,
            'rutas': rutas,
            'config_mora': config_mora,
            'repaso_semana_cobradas': repaso_semana_cobradas,
            'repaso_semana_pendientes': repaso_semana_pendientes,
            'repaso_semana_total_cobrado': repaso_semana_total_cobrado,
            'repaso_semana_total_pendiente': repaso_semana_total_pendiente,
            'repaso_semana_inicio': inicio_semana_pasada,
        })
        
        # Anotar historial de modificaciones en todas las cuotas
        from itertools import chain
        todas_cuotas = list(chain(cuotas_vencidas, cuotas_mora_reciente, cuotas_hoy, cuotas_semana, cuotas_mes))
        cuota_ids = [c.id for c in todas_cuotas]
        if cuota_ids:
            historiales = HistorialModificacionPago.objects.filter(
                cuota_id__in=cuota_ids
            ).select_related('cuota_relacionada', 'usuario').order_by('-fecha_modificacion')
            historial_map = {}
            for h in historiales:
                if h.cuota_id not in historial_map:
                    historial_map[h.cuota_id] = []
                historial_map[h.cuota_id].append(h)
            for cuota in todas_cuotas:
                cuota.historial_list = historial_map.get(cuota.id, [])

        context['alias_pago'] = ConfiguracionMensajesAutomaticos.obtener().alias_pago

        return context


class CalendarioCobrosView(LoginRequiredMixin, TemplateView):
    """Calendario visual de cobros (A6): un vistazo del mes completo, día por día.
    También soporta una vista semanal (?vista=semana), pedida por el cliente:
    los días de la semana uno abajo del otro, con cliente/monto/cuota de un vistazo."""
    template_name = 'core/calendario_cobros.html'

    def get_context_data(self, **kwargs):
        import calendar as calendar_module
        from datetime import date

        context = super().get_context_data(**kwargs)
        hoy = fecha_local_hoy()

        vista = self.request.GET.get('vista', 'mes')
        if vista not in ('mes', 'semana'):
            vista = 'mes'
        context['vista'] = vista

        base_filter = {}
        if not es_usuario_admin(self.request.user):
            base_filter['prestamo__cobrador'] = self.request.user

        if vista == 'semana':
            self._agregar_contexto_semana(context, hoy, base_filter)
            return context

        try:
            year = int(self.request.GET.get('year', hoy.year))
            month = int(self.request.GET.get('month', hoy.month))
            date(year, month, 1)  # valida que el año/mes sean válidos
        except (ValueError, TypeError):
            year, month = hoy.year, hoy.month

        _, ultimo_dia_num = calendar_module.monthrange(year, month)
        primer_dia = date(year, month, 1)
        ultimo_dia = date(year, month, ultimo_dia_num)

        cuotas_mes = list(Cuota.objects.filter(
            fecha_vencimiento__gte=primer_dia,
            fecha_vencimiento__lte=ultimo_dia,
            prestamo__estado='AC',
            **base_filter
        ).select_related('prestamo', 'prestamo__cliente').order_by('prestamo__cliente__apellido'))

        cuotas_por_dia = {}
        for cuota in cuotas_mes:
            cuotas_por_dia.setdefault(cuota.fecha_vencimiento.day, []).append(cuota)

        dias = []
        detalle_dias = {}
        for dia_num in range(1, ultimo_dia_num + 1):
            fecha_dia = date(year, month, dia_num)
            cuotas_dia = cuotas_por_dia.get(dia_num, [])

            if not cuotas_dia:
                color = ''
            elif fecha_dia > hoy:
                color = 'proxima'
            elif all(c.estado == 'PA' for c in cuotas_dia):
                color = 'cobrado'
            else:
                color = 'pendiente'

            total_dia = sum((c.monto_cuota for c in cuotas_dia), Decimal('0.00'))

            dias.append({
                'numero': dia_num,
                'color': color,
                'cantidad': len(cuotas_dia),
                'es_hoy': fecha_dia == hoy,
            })

            detalle_dias[str(dia_num)] = {
                'fecha': fecha_dia.strftime('%d/%m/%Y'),
                'total': float(total_dia),
                'cuotas': [
                    {
                        'cliente': c.prestamo.cliente.nombre_completo,
                        'monto': float(c.monto_restante if c.estado != 'PA' else c.monto_cuota),
                        'estado': c.get_estado_display(),
                        'cobrado': c.estado == 'PA',
                        'cliente_url': reverse('core:cliente_detail', args=[c.prestamo.cliente.pk]),
                    }
                    for c in cuotas_dia
                ],
            }

        # Grilla del mes (semanas de lunes a domingo, con relleno de días de otros meses)
        cal = calendar_module.Calendar(firstweekday=0)
        semanas = cal.monthdayscalendar(year, month)
        dias_por_numero = {d['numero']: d for d in dias}
        grilla = [
            [dias_por_numero.get(num) if num != 0 else None for num in semana]
            for semana in semanas
        ]

        mes_anterior = (year, month - 1) if month > 1 else (year - 1, 12)
        mes_siguiente = (year, month + 1) if month < 12 else (year + 1, 1)

        total_mes_cobrado = sum((c.monto_cuota for c in cuotas_mes if c.estado == 'PA'), Decimal('0.00'))
        total_mes_pendiente = sum((c.monto_restante for c in cuotas_mes if c.estado != 'PA'), Decimal('0.00'))

        context.update({
            'primer_dia_mes': primer_dia,
            'grilla': grilla,
            'anio': year,
            'mes': month,
            # Armadas ya en Python (no en el template) para que USE_THOUSAND_SEPARATOR
            # no le meta un punto de miles al año dentro del querystring (?year=2.026)
            'url_mes_anterior': f'?year={mes_anterior[0]}&month={mes_anterior[1]}',
            'url_mes_siguiente': f'?year={mes_siguiente[0]}&month={mes_siguiente[1]}',
            'detalle_dias': detalle_dias,
            'total_mes_cobrado': total_mes_cobrado,
            'total_mes_pendiente': total_mes_pendiente,
            'es_mes_actual': (year == hoy.year and month == hoy.month),
            'url_vista_semana': '?vista=semana',
        })
        return context

    def _agregar_contexto_semana(self, context, hoy, base_filter):
        """
        Vista semanal pedida por el cliente: los días de la semana uno abajo
        del otro (como Google Calendar), con cliente + monto + número de
        cuota a la vista sin tener que abrir un modal por día.
        """
        from datetime import date, timedelta

        fecha_param = self.request.GET.get('fecha', '')
        try:
            fecha_ref = date.fromisoformat(fecha_param) if fecha_param else hoy
        except ValueError:
            fecha_ref = hoy

        lunes = fecha_ref - timedelta(days=fecha_ref.weekday())
        domingo = lunes + timedelta(days=6)

        cuotas_semana = list(Cuota.objects.filter(
            fecha_vencimiento__gte=lunes,
            fecha_vencimiento__lte=domingo,
            prestamo__estado='AC',
            **base_filter
        ).select_related('prestamo', 'prestamo__cliente').order_by(
            'fecha_vencimiento', 'prestamo__cliente__apellido'
        ))

        cuotas_por_dia = {}
        for cuota in cuotas_semana:
            cuotas_por_dia.setdefault(cuota.fecha_vencimiento, []).append(cuota)

        # Nombres cortos en es-ar (ver mismo comentario/solución en CobrosView:
        # el catálogo de traducción de Django da "Mie" sin tilde con |date:"D")
        DIAS_ABREV = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

        dias_semana = []
        total_semana_cobrado = Decimal('0.00')
        total_semana_pendiente = Decimal('0.00')
        for i in range(7):
            fecha_dia = lunes + timedelta(days=i)
            cuotas_dia = cuotas_por_dia.get(fecha_dia, [])
            total_dia = Decimal('0.00')
            entradas = []
            for c in cuotas_dia:
                monto = c.monto_cuota if c.estado == 'PA' else c.monto_restante
                total_dia += monto
                if c.estado == 'PA':
                    total_semana_cobrado += monto
                else:
                    total_semana_pendiente += monto
                entradas.append({
                    'cliente': c.prestamo.cliente.nombre_completo,
                    'cliente_url': reverse('core:cliente_detail', args=[c.prestamo.cliente.pk]),
                    'monto': monto,
                    'cuota_texto': f'Cuota {c.numero_cuota} de {c.prestamo.cuotas_pactadas}',
                    'cobrado': c.estado == 'PA',
                })
            dias_semana.append({
                'fecha': fecha_dia,
                'nombre_dia': DIAS_ABREV[i],
                'es_hoy': fecha_dia == hoy,
                'entradas': entradas,
                'total': total_dia,
            })

        semana_anterior = lunes - timedelta(days=7)
        semana_siguiente = lunes + timedelta(days=7)

        context.update({
            'dias_semana': dias_semana,
            'lunes_semana': lunes,
            'domingo_semana': domingo,
            'total_semana_cobrado': total_semana_cobrado,
            'total_semana_pendiente': total_semana_pendiente,
            'es_semana_actual': (lunes <= hoy <= domingo),
            'url_semana_anterior': f'?vista=semana&fecha={semana_anterior.isoformat()}',
            'url_semana_siguiente': f'?vista=semana&fecha={semana_siguiente.isoformat()}',
            'url_vista_mes': '?vista=mes',
        })


# ============== VISTAS DE CLIENTES ==============

class ClienteListView(LoginRequiredMixin, ListView):
    """Lista de clientes"""
    model = Cliente
    template_name = 'core/cliente_list.html'
    context_object_name = 'clientes'
    paginate_by = 50
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('usuario')
        
        # Filtrar por usuario (admin ve todos, otros solo los suyos)
        if not es_usuario_admin(self.request.user):
            queryset = queryset.filter(usuario=self.request.user)
        
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
        # Asignar el usuario actual al cliente
        form.instance.usuario = self.request.user
        messages.success(self.request, 'Cliente creado exitosamente.')
        return super().form_valid(form)


class ClienteUpdateView(LoginRequiredMixin, UpdateView):
    """Editar cliente"""
    model = Cliente
    form_class = ClienteForm
    template_name = 'core/cliente_form.html'
    success_url = reverse_lazy('core:cliente_list')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Admin puede editar todos, otros solo los suyos
        if not es_usuario_admin(self.request.user):
            queryset = queryset.filter(usuario=self.request.user)
        return queryset
    
    def form_valid(self, form):
        messages.success(self.request, 'Cliente actualizado exitosamente.')
        return super().form_valid(form)


class ClienteDeleteView(LoginRequiredMixin, DeleteView):
    """Eliminar cliente"""
    model = Cliente
    success_url = reverse_lazy('core:cliente_list')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if not es_usuario_admin(self.request.user):
            queryset = queryset.filter(usuario=self.request.user)
        return queryset
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Verificar si tiene préstamos asociados
        if self.object.prestamos.exists():
            messages.error(request, 
                f'No se puede eliminar a {self.object.nombre_completo} porque tiene '
                f'{self.object.prestamos.count()} préstamo(s) asociado(s). '
                f'Primero debe eliminar o reasignar los préstamos.'
            )
            return redirect('core:cliente_detail', pk=self.object.pk)
        
        nombre = self.object.nombre_completo
        self.object.delete()
        messages.success(request, f'Cliente {nombre} eliminado exitosamente.')
        return redirect('core:cliente_list')


class ClienteDetailView(LoginRequiredMixin, DetailView):
    """Detalle de cliente"""
    model = Cliente
    template_name = 'core/cliente_detail.html'
    context_object_name = 'cliente'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Admin puede ver todos, otros solo los suyos
        if not es_usuario_admin(self.request.user):
            queryset = queryset.filter(usuario=self.request.user)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prestamos_activos = list(self.object.prestamos.filter(estado='AC').select_related('cobrador'))
        context['prestamos_activos'] = prestamos_activos
        context['prestamos_activos_count'] = len(prestamos_activos)
        # Historial = todo lo que no está activo (lo activo ya se ve arriba, en grande;
        # repetirlo acá sería ruido, no información nueva).
        context['prestamos_historial'] = self.object.prestamos.exclude(
            estado='AC'
        ).select_related('cobrador').order_by('-fecha_inicio')
        # Últimos movimientos (A3): repasar la actividad reciente sin entrar a cada préstamo
        context['movimientos_recientes'] = HistorialModificacionPago.objects.filter(
            cuota__prestamo__cliente=self.object
        ).select_related('cuota', 'cuota_relacionada', 'usuario').order_by('-fecha_modificacion')[:6]
        context['historial_pagos'] = self.object.historial_pagos
        return context


# ============== VISTAS DE PRÉSTAMOS ==============

class PrestamoListView(LoginRequiredMixin, ListView):
    """Lista de préstamos"""
    model = Prestamo
    template_name = 'core/prestamo_list.html'
    context_object_name = 'prestamos'
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtrar por clientes del usuario (admin ve todos)
        if not es_usuario_admin(self.request.user):
            queryset = queryset.filter(cobrador=self.request.user)

        estado = self.request.GET.get('estado', '')
        busqueda = self.request.GET.get('q', '')

        if estado:
            queryset = queryset.filter(estado=estado)

        if busqueda:
            queryset = queryset.filter(
                Q(cliente__nombre__icontains=busqueda) |
                Q(cliente__apellido__icontains=busqueda) |
                Q(cliente__telefono__icontains=busqueda)
            )

        return queryset.select_related('cliente', 'cliente__usuario', 'cobrador')


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
            try:
                initial['cliente'] = int(cliente_id)
            except (ValueError, TypeError):
                pass
        initial['fecha_inicio'] = fecha_local_hoy()
        return initial
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filtrar clientes por usuario (admin ve todos)
        if not es_usuario_admin(self.request.user):
            form.fields['cliente'].queryset = Cliente.objects.filter(
                estado='AC', usuario=self.request.user
            ).order_by('apellido', 'nombre')
        else:
            form.fields['cliente'].queryset = Cliente.objects.filter(
                estado='AC'
            ).order_by('apellido', 'nombre')
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pasar datos de clientes para mostrar límite de crédito. El template
        # calcula credito_usado/prestamo_activo/etc. para CADA cliente activo
        # (para el JS de "Nuevo Préstamo"); sin este prefetch eso dispara
        # varias queries por cliente y con muchos clientes activos termina en
        # timeout (Internal Server Error) en producción.
        prestamos_prefetch = Prefetch(
            'prestamos', queryset=Prestamo.objects.all().prefetch_related('cuotas')
        )
        if not es_usuario_admin(self.request.user):
            context['clientes'] = Cliente.objects.filter(
                estado='AC', usuario=self.request.user
            ).order_by('apellido', 'nombre').select_related('tipo_negocio').prefetch_related(prestamos_prefetch)
        else:
            context['clientes'] = Cliente.objects.filter(
                estado='AC'
            ).order_by('apellido', 'nombre').select_related('tipo_negocio').prefetch_related(prestamos_prefetch)
        return context
    
    def form_valid(self, form):
        # Asignar el cobrador actual al préstamo
        form.instance.cobrador = self.request.user
        messages.success(self.request, 'Préstamo creado exitosamente. Las cuotas han sido generadas.')
        return super().form_valid(form)


class PrestamoDetailView(LoginRequiredMixin, DetailView):
    """Detalle de préstamo con todas sus cuotas"""
    model = Prestamo
    template_name = 'core/prestamo_detail.html'
    context_object_name = 'prestamo'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Admin puede ver todos, otros solo los de sus préstamos
        if not es_usuario_admin(self.request.user):
            queryset = queryset.filter(cobrador=self.request.user)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cuotas = list(self.object.cuotas.all())
        context['config_mora'] = ConfiguracionMora.obtener_config_activa()
        
        # Cargar historial de modificaciones para todas las cuotas
        cuota_ids = [c.id for c in cuotas]
        historial = HistorialModificacionPago.objects.filter(
            cuota_id__in=cuota_ids
        ).select_related('cuota_relacionada', 'usuario').order_by('-fecha_modificacion')
        
        historial_por_cuota = {}
        for h in historial:
            if h.cuota_id not in historial_por_cuota:
                historial_por_cuota[h.cuota_id] = []
            historial_por_cuota[h.cuota_id].append(h)
        
        # Anotar cada cuota con su historial
        for cuota in cuotas:
            cuota.historial_list = historial_por_cuota.get(cuota.id, [])
        
        context['cuotas'] = cuotas
        context['notas_seguimiento'] = self.object.notas_seguimiento.select_related('creado_por').all()
        return context


class PrestamoUpdateView(LoginRequiredMixin, UpdateView):
    """Editar un préstamo existente"""
    model = Prestamo
    form_class = PrestamoForm
    template_name = 'core/prestamo_form.html'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        if not es_usuario_admin(self.request.user):
            queryset = queryset.filter(cobrador=self.request.user)
        return queryset
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filtrar clientes por usuario (admin ve todos)
        if not es_usuario_admin(self.request.user):
            form.fields['cliente'].queryset = Cliente.objects.filter(
                estado='AC', usuario=self.request.user
            ).order_by('apellido', 'nombre')
        else:
            form.fields['cliente'].queryset = Cliente.objects.filter(
                estado='AC'
            ).order_by('apellido', 'nombre')
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['editando'] = True
        if not es_usuario_admin(self.request.user):
            context['clientes'] = Cliente.objects.filter(
                estado='AC', usuario=self.request.user
            ).order_by('apellido', 'nombre')
        else:
            context['clientes'] = Cliente.objects.filter(
                estado='AC'
            ).order_by('apellido', 'nombre')
        return context
    
    def form_valid(self, form):
        prestamo = form.save(commit=False)
        # Recalcular monto total
        interes = prestamo.monto_solicitado * (prestamo.tasa_interes_porcentaje / 100)
        prestamo.monto_total_a_pagar = prestamo.monto_solicitado + interes

        # Recalcular fecha de finalización si no es manual
        if not prestamo.fecha_finalizacion_manual or not prestamo.fecha_finalizacion:
            prestamo.fecha_finalizacion = prestamo.calcular_fecha_finalizacion()

        with transaction.atomic():
            prestamo.save()

            # Sincronizar la cantidad de cuotas pendientes con cuotas_pactadas.
            # Antes esto solo redistribuía el monto entre las cuotas PE que ya
            # existían: si cuotas_pactadas cambiaba (ej. de 2 a 3), la cuota
            # nueva nunca se creaba y todo lo que lee las cuotas (el detalle,
            # los mensajes automáticos) seguía viendo el cronograma viejo.
            cuotas_resueltas = prestamo.cuotas.filter(estado__in=['PA', 'PC']).count()
            cuotas_pendientes = list(prestamo.cuotas.filter(estado='PE').order_by('numero_cuota'))
            necesarias = max(prestamo.cuotas_pactadas - cuotas_resueltas, 0)

            if len(cuotas_pendientes) > necesarias:
                # Sobran cuotas pendientes: se borran las últimas (nunca las
                # que ya tienen pago, esas no están en este queryset)
                for cuota in cuotas_pendientes[necesarias:]:
                    cuota.delete()
                cuotas_pendientes = cuotas_pendientes[:necesarias]
            elif len(cuotas_pendientes) < necesarias:
                # Faltan cuotas pendientes: se generan continuando el
                # cronograma desde la última cuota existente
                ultima_cuota = prestamo.cuotas.order_by('-numero_cuota').first()
                ultimo_numero = ultima_cuota.numero_cuota if ultima_cuota else 0
                fecha_vencimiento = ultima_cuota.fecha_vencimiento if ultima_cuota else prestamo.fecha_inicio
                faltan = necesarias - len(cuotas_pendientes)
                for _ in range(faltan):
                    ultimo_numero += 1
                    fecha_vencimiento = prestamo.siguiente_fecha_cuota(fecha_vencimiento)
                    cuotas_pendientes.append(Cuota.objects.create(
                        prestamo=prestamo,
                        numero_cuota=ultimo_numero,
                        monto_cuota=Decimal('0.00'),
                        fecha_vencimiento=fecha_vencimiento
                    ))

            # Redistribuir el monto restante entre las cuotas pendientes ya sincronizadas
            if cuotas_pendientes:
                monto_pagado = prestamo.monto_pagado
                monto_restante = prestamo.monto_total_a_pagar - monto_pagado
                nueva_cuota_monto = round(monto_restante / len(cuotas_pendientes), 2)
                for cuota in cuotas_pendientes:
                    cuota.monto_cuota = nueva_cuota_monto
                Cuota.objects.bulk_update(cuotas_pendientes, ['monto_cuota'])

        messages.success(self.request, 'Préstamo actualizado exitosamente.')
        return redirect('core:prestamo_detail', pk=prestamo.pk)
    
    def get_success_url(self):
        return reverse_lazy('core:prestamo_detail', kwargs={'pk': self.object.pk})


class PrestamoDeleteView(LoginRequiredMixin, DeleteView):
    """Eliminar un préstamo y todas sus cuotas"""
    model = Prestamo
    success_url = reverse_lazy('core:prestamo_list')

    def get_queryset(self):
        queryset = super().get_queryset()
        if not es_usuario_admin(self.request.user):
            queryset = queryset.filter(cobrador=self.request.user)
        return queryset

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        prestamo_pk = self.object.pk
        cliente_nombre = self.object.cliente.nombre_completo
        # No permitir eliminar préstamos que ya tienen pagos realizados
        if self.object.cuotas.filter(estado__in=['PA', 'PC']).exists():
            messages.error(
                request,
                f'No se puede eliminar el préstamo #{prestamo_pk} porque ya tiene pagos registrados. '
                f'Puede cancelarlo en vez de eliminarlo.'
            )
            return redirect('core:prestamo_detail', pk=prestamo_pk)
        # Eliminar cuotas asociadas y el préstamo
        self.object.cuotas.all().delete()
        self.object.delete()
        messages.success(request, f'Préstamo #{prestamo_pk} de {cliente_nombre} eliminado exitosamente.')
        return redirect('core:prestamo_list')


class RenovarPrestamoView(LoginRequiredMixin, TemplateView):
    """Vista para renovar un préstamo"""
    template_name = 'core/prestamo_renovar.html'
    
    def get_prestamo(self):
        # Verificar propiedad del préstamo
        if not es_usuario_admin(self.request.user):
            return get_object_or_404(Prestamo, pk=self.kwargs['pk'], cobrador=self.request.user)
        return get_object_or_404(Prestamo, pk=self.kwargs['pk'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prestamo = self.get_prestamo()
        saldo_pendiente = prestamo.calcular_saldo_para_renovacion()
        context['prestamo'] = prestamo
        context['saldo_pendiente'] = saldo_pendiente
        context['form'] = kwargs.get('form', RenovacionPrestamoForm(
            cliente=prestamo.cliente,
            saldo_pendiente=saldo_pendiente,
            initial={
                'nueva_tasa': prestamo.tasa_interes_porcentaje,
                'nuevas_cuotas': prestamo.cuotas_pactadas,
                'nueva_frecuencia': prestamo.frecuencia,
            }
        ))
        # Agregar información del límite de crédito
        context['maximo_capital_adicional'] = prestamo.cliente.maximo_prestable
        if context['maximo_capital_adicional'] is not None:
            context['maximo_capital_adicional'] += saldo_pendiente
        return context
    
    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())
    
    def post(self, request, *args, **kwargs):
        prestamo_anterior = self.get_prestamo()
        saldo_pendiente = prestamo_anterior.calcular_saldo_para_renovacion()
        form = RenovacionPrestamoForm(
            request.POST,
            cliente=prestamo_anterior.cliente,
            saldo_pendiente=saldo_pendiente
        )
        if form.is_valid():
            nuevo_prestamo = Prestamo.renovar_prestamo(
                prestamo_anterior=prestamo_anterior,
                nuevo_monto=form.cleaned_data['nuevo_monto'],
                nueva_tasa=form.cleaned_data['nueva_tasa'],
                nuevas_cuotas=form.cleaned_data['nuevas_cuotas'],
                nueva_frecuencia=form.cleaned_data['nueva_frecuencia'],
                cobrador=request.user,
                fecha_finalizacion=form.cleaned_data.get('fecha_finalizacion')
            )
            
            messages.success(
                request, 
                f'Préstamo renovado exitosamente. Nuevo préstamo #{nuevo_prestamo.pk} creado.'
            )
            return redirect('core:prestamo_detail', pk=nuevo_prestamo.pk)
        
        return self.render_to_response(self.get_context_data(form=form))


# ============== VISTAS DE COBROS (AJAX) ==============

@login_required
def anular_pago_cuota(request, pk):
    """Anular/revertir un pago de cuota via AJAX"""
    if request.method == 'POST':
        try:
            # Solo el cobrador asignado o admin puede anular
            if es_usuario_admin(request.user):
                cuota = get_object_or_404(Cuota, pk=pk)
            else:
                cuota = get_object_or_404(Cuota, pk=pk, prestamo__cobrador=request.user)
            
            if cuota.estado not in ['PA', 'PC']:
                return JsonResponse({
                    'success': False,
                    'message': 'Solo se pueden anular pagos de cuotas cobradas.'
                }, status=400)
            
            cuota.cancelar_pago(usuario=request.user)

            # Recalcular estadísticas (capital + mora)
            hoy = fecha_local_hoy()
            stats_filter = {
                'fecha_pago_real': hoy,
                'estado__in': ['PA', 'PC'],
            }
            if not es_usuario_admin(request.user):
                stats_filter['prestamo__cobrador'] = request.user

            agg = Cuota.objects.filter(**stats_filter).aggregate(
                cap=Sum('monto_pagado'), mora=Sum('interes_mora_cobrado')
            )
            total_cobrado_hoy = (agg['cap'] or Decimal('0.00')) + (agg['mora'] or Decimal('0.00'))

            cantidad_cobros_hoy = Cuota.objects.filter(
                **stats_filter
            ).count()
            
            return JsonResponse({
                'success': True,
                'message': 'Pago anulado exitosamente. La cuota volvió a estado pendiente.',
                'cuota': {
                    'id': cuota.pk,
                    'estado': cuota.estado,
                    'estado_display': cuota.get_estado_display(),
                    'monto_cuota': float(cuota.monto_cuota),
                    'monto_pagado': float(cuota.monto_pagado),
                    'monto_restante': float(cuota.monto_restante),
                },
                'prestamo': {
                    'progreso': cuota.prestamo.progreso_porcentaje,
                    'estado': cuota.prestamo.estado,
                },
                'estadisticas': {
                    'total_cobrado_hoy': int(total_cobrado_hoy),
                    'cantidad_cobros_hoy': cantidad_cobros_hoy,
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)


@login_required
def cobrar_cuota(request, pk):
    """Registrar pago de cuota via AJAX"""
    if request.method == 'POST':
        try:
            # Admin puede cobrar cualquier cuota, cobrador solo las suyas
            if es_usuario_admin(request.user):
                cuota = get_object_or_404(Cuota, pk=pk)
            else:
                cuota = get_object_or_404(Cuota, pk=pk, prestamo__cobrador=request.user)
            
            # Obtener datos del body
            try:
                data = json.loads(request.body)
                monto = Decimal(str(data.get('monto', cuota.monto_restante)))
                accion_restante = data.get('accion_restante', 'ignorar')  # 'ignorar', 'proxima', 'especial'
                fecha_especial_str = data.get('fecha_especial', None)
                
                # Nuevos campos de método de pago
                metodo_pago = data.get('metodo_pago', 'EF')  # 'EF', 'TR', 'MX'
                monto_efectivo = data.get('monto_efectivo')
                monto_transferencia = data.get('monto_transferencia')
                referencia_transferencia = data.get('referencia_transferencia')
                
                # Interés por mora
                interes_mora = data.get('interes_mora', 0)
                
                # Convertir fecha especial si existe
                fecha_especial = None
                if fecha_especial_str and accion_restante == 'especial':
                    from datetime import datetime
                    fecha_especial = datetime.strptime(fecha_especial_str, '%Y-%m-%d').date()
                    
            except (json.JSONDecodeError, ValueError):
                monto = None
                accion_restante = 'ignorar'
                fecha_especial = None
                metodo_pago = 'EF'
                monto_efectivo = None
                monto_transferencia = None
                referencia_transferencia = None
                interes_mora = 0
            
            # Calcular restante antes del pago
            monto_restante_antes = float(cuota.monto_restante)
            monto_que_quedara = max(0, monto_restante_antes - float(monto or cuota.monto_restante))
            
            cuota.registrar_pago(
                monto=monto, 
                accion_restante=accion_restante, 
                fecha_especial=fecha_especial,
                metodo_pago=metodo_pago,
                monto_efectivo=monto_efectivo,
                monto_transferencia=monto_transferencia,
                referencia_transferencia=referencia_transferencia,
                interes_mora=interes_mora,
                cobrador=request.user
            )
            
            # Mensaje según la acción
            if accion_restante == 'proxima' and monto_que_quedara > 0:
                mensaje = f'Pago registrado. ${monto_que_quedara:.2f} sumado a la próxima cuota.'
            elif accion_restante == 'especial' and monto_que_quedara > 0:
                mensaje = f'Pago registrado. Cuota especial creada por ${monto_que_quedara:.2f}.'
            else:
                mensaje = 'Pago registrado exitosamente'
            
            # Agregar info de método de pago al mensaje
            if metodo_pago == 'TR':
                mensaje += ' (Transferencia)'
            elif metodo_pago == 'MX':
                mensaje += ' (Mixto)'
            
            # Calcular total cobrado hoy (capital + mora)
            hoy = fecha_local_hoy()
            stats_filter = {
                'fecha_pago_real': hoy,
                'estado__in': ['PA', 'PC'],
            }
            if not es_usuario_admin(request.user):
                stats_filter['prestamo__cobrador'] = request.user

            agg = Cuota.objects.filter(**stats_filter).aggregate(
                cap=Sum('monto_pagado'), mora=Sum('interes_mora_cobrado')
            )
            total_cobrado_hoy = (agg['cap'] or Decimal('0.00')) + (agg['mora'] or Decimal('0.00'))

            cantidad_cobros_hoy = Cuota.objects.filter(
                **stats_filter
            ).count()

            # Cuánto bajó el capital pendiente de ESTA cuota con este pago (permite
            # actualizar los totales "Por Cobrar"/"Vencidas" en la pantalla sin recargar).
            capital_cobrado_ahora = monto_restante_antes - float(cuota.monto_restante)
            era_vencida = cuota.fecha_vencimiento < hoy

            return JsonResponse({
                'success': True,
                'message': mensaje,
                'cuota': {
                    'id': cuota.pk,
                    'estado': cuota.estado,
                    'estado_display': cuota.get_estado_display(),
                    'monto_pagado': float(cuota.monto_pagado),
                    'monto_restante': float(cuota.monto_restante),
                    'metodo_pago': cuota.metodo_pago,
                    'interes_mora_cobrado': float(cuota.interes_mora_cobrado),
                },
                'prestamo': {
                    'progreso': cuota.prestamo.progreso_porcentaje,
                    'estado': cuota.prestamo.estado,
                },
                'estadisticas': {
                    'total_cobrado_hoy': int(total_cobrado_hoy),  # Sin decimales
                    'cantidad_cobros_hoy': cantidad_cobros_hoy,
                    'capital_cobrado_ahora': int(round(capital_cobrado_ahora)),
                    'era_vencida': era_vencida,
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)


@login_required
def editar_cobro(request, pk):
    """Editar un cobro existente via AJAX"""
    if request.method == 'POST':
        try:
            if es_usuario_admin(request.user):
                cuota = get_object_or_404(Cuota, pk=pk)
            else:
                cuota = get_object_or_404(Cuota, pk=pk, prestamo__cobrador=request.user)
            
            if cuota.estado not in ['PA', 'PC']:
                return JsonResponse({
                    'success': False,
                    'message': 'Solo se pueden editar cobros de cuotas pagadas o parciales.'
                }, status=400)
            
            data = json.loads(request.body)
            nuevo_monto = Decimal(str(data.get('monto', float(cuota.monto_pagado))))
            metodo_pago = data.get('metodo_pago', cuota.metodo_pago or 'EF')
            monto_efectivo = data.get('monto_efectivo')
            monto_transferencia = data.get('monto_transferencia')
            referencia = data.get('referencia_transferencia')
            interes_mora = Decimal(str(data.get('interes_mora', float(cuota.interes_mora_cobrado))))
            marcar_completo = data.get('marcar_completo', False)
            
            monto_anterior = cuota.monto_pagado
            monto_cuota_anterior = cuota.monto_cuota
            
            # Actualizar datos del pago
            cuota.monto_pagado = nuevo_monto
            cuota.metodo_pago = metodo_pago
            cuota.interes_mora_cobrado = interes_mora
            
            if metodo_pago == 'EF':
                cuota.monto_efectivo = nuevo_monto
                cuota.monto_transferencia = Decimal('0.00')
            elif metodo_pago == 'TR':
                cuota.monto_efectivo = Decimal('0.00')
                cuota.monto_transferencia = nuevo_monto
                cuota.referencia_transferencia = referencia
            elif metodo_pago == 'MX':
                cuota.monto_efectivo = Decimal(str(monto_efectivo or 0))
                cuota.monto_transferencia = Decimal(str(monto_transferencia or 0))
                cuota.referencia_transferencia = referencia
            
            if marcar_completo:
                # Ajustar monto de cuota para que coincida con lo pagado
                cuota.monto_cuota = nuevo_monto
                cuota.estado = Cuota.Estado.PAGADO
            elif nuevo_monto >= cuota.monto_cuota:
                cuota.estado = Cuota.Estado.PAGADO
                cuota.monto_pagado = cuota.monto_cuota
            else:
                cuota.estado = Cuota.Estado.PARCIAL
            
            cuota.save()
            
            # Registrar en historial
            HistorialModificacionPago.objects.create(
                cuota=cuota,
                usuario=request.user,
                tipo_modificacion='ED',
                monto_cuota_anterior=monto_cuota_anterior,
                monto_cuota_nuevo=cuota.monto_cuota,
                monto_pagado=nuevo_monto,
                monto_restante_transferido=Decimal('0.00'),
                interes_mora=interes_mora,
                metodo_pago=metodo_pago,
                notas=f'Cobro editado. Monto anterior: ${monto_anterior:,.0f} → Nuevo: ${nuevo_monto:,.0f}. Completo: {"Sí" if marcar_completo else "No"}'
            )
            
            # Verificar si el préstamo está completamente pagado
            prestamo = cuota.prestamo
            if not prestamo.cuotas.filter(estado__in=['PE', 'PC']).exists():
                prestamo.estado = Prestamo.Estado.FINALIZADO
                prestamo.save(update_fields=['estado'])
            elif prestamo.estado == Prestamo.Estado.FINALIZADO:
                prestamo.estado = Prestamo.Estado.ACTIVO
                prestamo.save(update_fields=['estado'])
            
            return JsonResponse({
                'success': True,
                'message': 'Cobro editado exitosamente',
                'cuota': {
                    'id': cuota.pk,
                    'estado': cuota.estado,
                    'monto_cuota': float(cuota.monto_cuota),
                    'monto_pagado': float(cuota.monto_pagado),
                    'monto_restante': float(cuota.monto_restante),
                    'metodo_pago': cuota.metodo_pago,
                    'interes_mora_cobrado': float(cuota.interes_mora_cobrado),
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
    hoy = fecha_local_hoy()
    
    cuotas_qs = Cuota.objects.filter(
        fecha_vencimiento=hoy,
        estado__in=['PE', 'PC'],
        prestamo__estado='AC'
    )
    # Filtrar por usuario (admin ve todo)
    if not es_usuario_admin(request.user):
        cuotas_qs = cuotas_qs.filter(prestamo__cobrador=request.user)
    
    cuotas = cuotas_qs.select_related('prestamo', 'prestamo__cliente', 'prestamo__cliente__usuario', 'prestamo__cobrador').values(
        'id', 'numero_cuota', 'monto_cuota', 'estado',
        'prestamo__id', 'prestamo__cuotas_pactadas',
        'prestamo__cliente__nombre', 'prestamo__cliente__apellido',
        'prestamo__cobrador__username', 'prestamo__cobrador__first_name',
        'prestamo__cobrador__last_name'
    )
    
    return JsonResponse({
        'cuotas': list(cuotas)
    })


@login_required
def cambiar_categoria_cliente(request, pk):
    """Cambiar categoría del cliente via AJAX"""
    if request.method == 'POST':
        try:
            # Verificar propiedad del cliente
            if not es_usuario_admin(request.user):
                cliente = get_object_or_404(Cliente, pk=pk, usuario=request.user)
            else:
                cliente = get_object_or_404(Cliente, pk=pk)
            
            data = json.loads(request.body)
            nueva_categoria = data.get('categoria')
            
            if nueva_categoria not in ['EX', 'RE', 'MO', 'NU']:
                return JsonResponse({
                    'success': False,
                    'message': 'Categoría no válida'
                }, status=400)
            
            categoria_anterior = cliente.get_categoria_display()
            cliente.categoria = nueva_categoria
            cliente.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Categoría cambiada de {categoria_anterior} a {cliente.get_categoria_display()}',
                'cliente': {
                    'id': cliente.pk,
                    'categoria': cliente.categoria,
                    'categoria_display': cliente.get_categoria_display(),
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)


@login_required
def cambiar_estado_irrecuperable_prestamo(request, pk):
    """
    Marcar un préstamo activo como irrecuperable (o revertirlo a activo).
    Solo admin: es una decisión de negocio, no una tarea de cobranza diaria.
    Al pasar a 'IR' el préstamo desaparece de Cobros/dashboard/reportes sin
    tocar ninguna de esas vistas, porque todas filtran explícitamente
    estado='AC'.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    if not es_usuario_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Solo un administrador puede hacer este cambio'}, status=403)

    try:
        prestamo = Prestamo.objects.get(pk=pk)
    except Prestamo.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Préstamo no encontrado'}, status=404)

    if prestamo.estado == Prestamo.Estado.ACTIVO:
        prestamo.estado = Prestamo.Estado.IRRECUPERABLE
        mensaje = f'Préstamo #{prestamo.pk} marcado como irrecuperable.'
    elif prestamo.estado == Prestamo.Estado.IRRECUPERABLE:
        prestamo.estado = Prestamo.Estado.ACTIVO
        mensaje = f'Préstamo #{prestamo.pk} reactivado.'
    else:
        return JsonResponse({
            'success': False,
            'message': f'No se puede cambiar un préstamo en estado "{prestamo.get_estado_display()}".'
        }, status=400)

    prestamo.save(update_fields=['estado'])

    return JsonResponse({
        'success': True,
        'message': mensaje,
        'data': {'estado': prestamo.estado, 'estado_display': prestamo.get_estado_display()}
    })


@login_required
def actualizar_corte_mora_reciente(request):
    """
    Actualiza cuántos días de atraso separan "Mora Reciente" de "Vencidas"
    en Cobros. Solo admin: es una decisión de política de cobranza, no algo
    que cada cobrador deba poder tocar.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    if not es_usuario_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Solo un administrador puede cambiar esto'}, status=403)

    try:
        data = json.loads(request.body)
        dias = int(data.get('dias_corte'))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'message': 'Valor no válido'}, status=400)

    if dias < 1 or dias > 90:
        return JsonResponse({'success': False, 'message': 'El corte debe ser entre 1 y 90 días'}, status=400)

    config, _ = ConfiguracionMoraReciente.objects.get_or_create(pk=1)
    config.dias_corte = dias
    config.save(update_fields=['dias_corte'])

    return JsonResponse({
        'success': True,
        'message': f'Corte actualizado a {dias} días.',
        'data': {'dias_corte': dias}
    })


@login_required
def buscar_clientes(request):
    """Búsqueda de clientes via AJAX para autocompletado"""
    q = request.GET.get('q', '').strip()
    if len(q) < 1:
        return JsonResponse({'results': []})
    
    queryset = Cliente.objects.filter(estado='AC')
    if not es_usuario_admin(request.user):
        queryset = queryset.filter(usuario=request.user)
    
    queryset = queryset.filter(
        Q(nombre__icontains=q) |
        Q(apellido__icontains=q) |
        Q(telefono__icontains=q)
    ).select_related('ruta')[:15]
    
    results = []
    for c in queryset:
        results.append({
            'id': c.pk,
            'nombre': c.nombre_completo,
            'telefono': c.telefono or '',
            'ruta': c.ruta.nombre if c.ruta else '',
            'categoria': c.categoria,
            'categoria_display': c.get_categoria_display(),
        })
    
    return JsonResponse({'results': results})


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
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                fecha = fecha_local_hoy()
        else:
            fecha = fecha_local_hoy()

        # Pagos del día (incluye pagos completos y parciales)
        pagos_del_dia = Cuota.objects.filter(
            fecha_pago_real=fecha,
            estado__in=['PA', 'PC']
        )
        # Filtrar por usuario (admin ve todo)
        if not es_usuario_admin(self.request.user):
            pagos_del_dia = pagos_del_dia.filter(prestamo__cobrador=self.request.user)
        pagos_del_dia = pagos_del_dia.select_related('prestamo', 'prestamo__cliente', 'cobrado_por').order_by(
            'prestamo__cliente__apellido'
        )
        
        # Total cobrado
        total_cobrado = pagos_del_dia.aggregate(
            total=Sum('monto_pagado')
        )['total'] or Decimal('0.00')

        # Totales desglosados por efectivo y transferencia
        totales_metodo = pagos_del_dia.aggregate(
            total_efectivo=Sum('monto_efectivo'),
            total_transferencia=Sum('monto_transferencia'),
        )

        # Totales por cobrador (visible para admins)
        totales_por_cobrador = []
        if es_usuario_admin(self.request.user):
            from django.contrib.auth.models import User
            cobradores_ids = pagos_del_dia.order_by().values_list('cobrado_por', flat=True).distinct()
            for cobrador_id in cobradores_ids:
                if cobrador_id is None:
                    continue
                cobrador = User.objects.filter(pk=cobrador_id).first()
                if not cobrador:
                    continue
                pagos_cobrador = pagos_del_dia.filter(cobrado_por=cobrador)
                agg = pagos_cobrador.aggregate(
                    total=Sum('monto_pagado'),
                    cantidad=Count('id'),
                    efectivo=Sum('monto_efectivo'),
                    transferencia=Sum('monto_transferencia'),
                )
                totales_por_cobrador.append({
                    'cobrador': cobrador.get_full_name() or cobrador.username,
                    'total': agg['total'] or Decimal('0.00'),
                    'cantidad': agg['cantidad'] or 0,
                    'efectivo': agg['efectivo'] or Decimal('0.00'),
                    'transferencia': agg['transferencia'] or Decimal('0.00'),
                })

        context.update({
            'fecha': fecha,
            'pagos': pagos_del_dia,
            'total_cobrado': total_cobrado,
            'cantidad_pagos': pagos_del_dia.count(),
            'total_efectivo': totales_metodo['total_efectivo'] or Decimal('0.00'),
            'total_transferencia': totales_metodo['total_transferencia'] or Decimal('0.00'),
            'totales_por_cobrador': totales_por_cobrador,
        })
        
        # Anotar historial de modificaciones en cada pago
        pagos_list = list(pagos_del_dia)
        pago_ids = [p.id for p in pagos_list]
        if pago_ids:
            historiales = HistorialModificacionPago.objects.filter(
                cuota_id__in=pago_ids
            ).select_related('cuota_relacionada', 'usuario').order_by('-fecha_modificacion')
            historial_map = {}
            for h in historiales:
                if h.cuota_id not in historial_map:
                    historial_map[h.cuota_id] = []
                historial_map[h.cuota_id].append(h)
            for pago in pagos_list:
                pago.historial_list = historial_map.get(pago.id, [])
        context['pagos'] = pagos_list
        
        return context


class PlanillaImpresionView(LoginRequiredMixin, TemplateView):
    """Vista optimizada para impresión con cuotas pendientes del día"""
    template_name = 'core/planilla_impresion.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from collections import OrderedDict
        from .models import RutaCobro, ConfiguracionPlanilla, ColumnaPlanilla
        
        # Obtener configuración de planilla
        config_id = self.request.GET.get('config')
        if config_id:
            try:
                config = ConfiguracionPlanilla.objects.get(pk=config_id)
            except ConfiguracionPlanilla.DoesNotExist:
                config = ConfiguracionPlanilla.objects.filter(es_default=True).first()
        else:
            config = ConfiguracionPlanilla.objects.filter(es_default=True).first()
        
        # Si no hay configuración, usar valores por defecto
        if not config:
            config = type('ConfigDefault', (), {
                'titulo_reporte': 'PLANILLA DE COBROS',
                'subtitulo': 'Préstamos - Sistema de Gestión',
                'mostrar_logo': False,
                'mostrar_fecha': True,
                'mostrar_totales': True,
                'mostrar_firmas': True,
                'agrupar_por_ruta': True,
                'agrupar_por_categoria': False,
                'incluir_vencidas': True,  # Incluir vencidas por defecto
                'filtrar_por_ruta': None,
                'pk': None,
            })()
        
        # Obtener columnas activas
        columnas = ColumnaPlanilla.objects.filter(activa=True).order_by('orden')
        if not columnas.exists():
            # Crear columnas por defecto si no existen
            columnas_default = [
                {'nombre_columna': 'numero', 'titulo_personalizado': '#', 'orden': 1, 'ancho': '4%'},
                {'nombre_columna': 'nombre_cliente', 'titulo_personalizado': 'Cliente', 'orden': 2, 'ancho': '22%'},
                {'nombre_columna': 'telefono', 'titulo_personalizado': 'Teléfono', 'orden': 3, 'ancho': '12%'},
                {'nombre_columna': 'categoria', 'titulo_personalizado': 'Cat.', 'orden': 4, 'ancho': '8%'},
                {'nombre_columna': 'cuota_actual', 'titulo_personalizado': 'Cuota', 'orden': 5, 'ancho': '10%'},
                {'nombre_columna': 'monto_cuota', 'titulo_personalizado': 'Monto', 'orden': 6, 'ancho': '12%'},
                {'nombre_columna': 'es_renovacion', 'titulo_personalizado': 'Renov.', 'orden': 7, 'ancho': '10%'},
                {'nombre_columna': 'dia_pago', 'titulo_personalizado': 'Día Pago', 'orden': 8, 'ancho': '10%'},
                {'nombre_columna': 'espacio_cobrado', 'titulo_personalizado': 'Cobrado', 'orden': 9, 'ancho': '12%'},
            ]
            for col_data in columnas_default:
                ColumnaPlanilla.objects.create(**col_data)
            columnas = ColumnaPlanilla.objects.filter(activa=True).order_by('orden')
        
        fecha_str = self.request.GET.get('fecha')
        if fecha_str:
            from datetime import datetime
            try:
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                fecha = fecha_local_hoy()
        else:
            fecha = fecha_local_hoy()

        ruta_id = self.request.GET.get('ruta')
        if not ruta_id and config and hasattr(config, 'filtrar_por_ruta') and config.filtrar_por_ruta:
            ruta_id = config.filtrar_por_ruta_id
        
        # Verificar si incluir vencidas (por defecto True para mostrar todos los pendientes)
        incluir_vencidas_param = self.request.GET.get('incluir_vencidas')
        if incluir_vencidas_param is not None:
            incluir_vencidas = incluir_vencidas_param.lower() in ('true', '1', 'si', 'yes')
        else:
            incluir_vencidas = getattr(config, 'incluir_vencidas', True)
        
        # Verificar si mostrar próximas cuotas
        mostrar_proximas = self.request.GET.get('proximas', 'true').lower() in ('true', '1', 'si', 'yes')
        
        # Verificar si es modo cierre de caja (mostrar cobros realizados)
        tipo_planilla = self.request.GET.get('tipo', '')
        es_cierre = tipo_planilla == 'cierre'
        
        if es_cierre:
            # MODO CIERRE: Mostrar cuotas COBRADAS en la fecha (completas y parciales)
            cuotas_pendientes = Cuota.objects.filter(
                fecha_pago_real=fecha,
                estado__in=['PA', 'PC']
            )
            if not es_usuario_admin(self.request.user):
                cuotas_pendientes = cuotas_pendientes.filter(prestamo__cobrador=self.request.user)
            cuotas_pendientes = cuotas_pendientes.select_related(
                'prestamo',
                'prestamo__cliente',
                'prestamo__cliente__ruta',
                'prestamo__cliente__tipo_negocio'
            ).order_by('prestamo__cliente__apellido')
            
            # Cambiar título para cierre
            config.titulo_reporte = 'CIERRE DE CAJA'
            config.subtitulo = f'Cobros realizados el {fecha.strftime("%d/%m/%Y")}'
        else:
            # MODO NORMAL: Obtener cuotas PENDIENTES (no cobradas)
            estados_cuota = ['PE', 'PC']
        
            # Base query: cuotas pendientes de préstamos activos
            base_query = Cuota.objects.filter(
                estado__in=estados_cuota,
                prestamo__estado='AC'
            )
            if not es_usuario_admin(self.request.user):
                base_query = base_query.filter(prestamo__cobrador=self.request.user)
            base_query = base_query.select_related(
                'prestamo', 
                'prestamo__cliente', 
                'prestamo__cliente__ruta',
                'prestamo__cliente__tipo_negocio'
            )
            
            if incluir_vencidas and mostrar_proximas:
                # Mostrar: cuotas vencidas + cuotas del día seleccionado + próximas 7 días
                from datetime import timedelta
                fecha_limite = fecha + timedelta(days=7)
                cuotas_pendientes = base_query.filter(
                    fecha_vencimiento__lte=fecha_limite
                )
            elif incluir_vencidas:
                # Mostrar: cuotas vencidas + cuotas del día seleccionado
                cuotas_pendientes = base_query.filter(
                    fecha_vencimiento__lte=fecha
                )
            elif mostrar_proximas:
                # Mostrar: solo cuotas de la fecha seleccionada + próximos 7 días
                from datetime import timedelta
                fecha_limite = fecha + timedelta(days=7)
                cuotas_pendientes = base_query.filter(
                    fecha_vencimiento__gte=fecha,
                    fecha_vencimiento__lte=fecha_limite
                )
            else:
                # Solo cuotas del día exacto
                cuotas_pendientes = base_query.filter(
                    fecha_vencimiento=fecha
                )
        
        # Ordenar
        if hasattr(config, 'agrupar_por_ruta') and config.agrupar_por_ruta:
            cuotas_pendientes = cuotas_pendientes.order_by(
                'prestamo__cliente__ruta__orden',
                'prestamo__cliente__apellido'
            )
        elif hasattr(config, 'agrupar_por_categoria') and config.agrupar_por_categoria:
            cuotas_pendientes = cuotas_pendientes.order_by(
                'prestamo__cliente__categoria',
                'prestamo__cliente__apellido'
            )
        else:
            cuotas_pendientes = cuotas_pendientes.order_by('prestamo__cliente__apellido')
        
        # Filtrar por ruta si se especifica
        ruta_filter = None
        if ruta_id:
            try:
                ruta_filter = RutaCobro.objects.get(pk=ruta_id)
                cuotas_pendientes = cuotas_pendientes.filter(
                    prestamo__cliente__ruta_id=ruta_id
                )
            except RutaCobro.DoesNotExist:
                pass
        
        # Organizar datos
        cuotas_agrupadas = OrderedDict()
        if hasattr(config, 'agrupar_por_ruta') and config.agrupar_por_ruta:
            for cuota in cuotas_pendientes:
                grupo = cuota.prestamo.cliente.ruta.nombre if cuota.prestamo.cliente.ruta else "Sin Ruta"
                if grupo not in cuotas_agrupadas:
                    cuotas_agrupadas[grupo] = []
                cuotas_agrupadas[grupo].append(cuota)
        elif hasattr(config, 'agrupar_por_categoria') and config.agrupar_por_categoria:
            for cuota in cuotas_pendientes:
                grupo = cuota.prestamo.cliente.get_categoria_display()
                if grupo not in cuotas_agrupadas:
                    cuotas_agrupadas[grupo] = []
                cuotas_agrupadas[grupo].append(cuota)
        else:
            cuotas_agrupadas['Todos'] = list(cuotas_pendientes)
        
        total_esperado = cuotas_pendientes.aggregate(
            total=Sum('monto_pagado' if es_cierre else 'monto_cuota')
        )['total'] or Decimal('0.00')
        
        # Lista de rutas para filtro
        rutas = RutaCobro.objects.filter(activa=True).order_by('orden')
        
        # Lista de configuraciones disponibles
        configuraciones = ConfiguracionPlanilla.objects.all()
        
        context.update({
            'fecha': fecha,
            'cuotas_pendientes': cuotas_pendientes,
            'cuotas_por_ruta': cuotas_agrupadas,  # Compatibilidad
            'cuotas_agrupadas': cuotas_agrupadas,
            'total_esperado': total_esperado,
            'rutas': rutas,
            'ruta_filter': ruta_filter,
            'now': timezone.now(),
            'config': config,
            'columnas': columnas,
            'configuraciones': configuraciones,
            'incluir_vencidas': incluir_vencidas,
            'mostrar_proximas': mostrar_proximas,
            'es_cierre': es_cierre,
        })
        return context


MESES_ABREV = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']


def _primer_dia_mes_hace(fecha, meses_atras):
    """Primer día del mes que está `meses_atras` meses antes del mes de `fecha`."""
    total = fecha.year * 12 + (fecha.month - 1) - meses_atras
    return date(total // 12, total % 12 + 1, 1)


def _mes_siguiente(fecha):
    total = fecha.year * 12 + (fecha.month - 1) + 1
    return date(total // 12, total % 12 + 1, 1)


class ReporteGeneralView(LoginRequiredMixin, TemplateView):
    """Vista con reportes generales"""
    template_name = 'core/reporte_general.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hoy = fecha_local_hoy()
        es_admin = es_usuario_admin(self.request.user)

        # Estadísticas generales - filtradas por usuario
        if not es_admin:
            clientes_qs = Cliente.objects.filter(estado='AC', usuario=self.request.user)
            prestamos_qs = Prestamo.objects.filter(estado='AC', cobrador=self.request.user)
            cuotas_qs = Cuota.objects.filter(prestamo__estado='AC', prestamo__cobrador=self.request.user)
            prestamos_historicos_qs = Prestamo.objects.filter(cobrador=self.request.user)
            cuotas_historicas_qs = Cuota.objects.filter(prestamo__cobrador=self.request.user)
        else:
            clientes_qs = Cliente.objects.filter(estado='AC')
            prestamos_qs = Prestamo.objects.filter(estado='AC')
            cuotas_qs = Cuota.objects.filter(prestamo__estado='AC')
            prestamos_historicos_qs = Prestamo.objects.all()
            cuotas_historicas_qs = Cuota.objects.all()

        context['total_clientes'] = clientes_qs.count()
        context['prestamos_activos'] = prestamos_qs.count()

        # Capital en la calle - calculado a nivel DB para evitar N+1 queries
        capital_pendiente = cuotas_qs.filter(
            estado__in=['PE', 'PC']
        ).aggregate(total=Sum('monto_cuota'))['total'] or Decimal('0.00')
        capital_pagado_parcial = cuotas_qs.filter(
            estado='PC'
        ).aggregate(total=Sum('monto_pagado'))['total'] or Decimal('0.00')
        context['capital_en_calle'] = capital_pendiente - capital_pagado_parcial

        # Cuotas vencidas y cartera en riesgo (capital vencido todavía no cobrado)
        vencidas_qs = cuotas_qs.filter(fecha_vencimiento__lt=hoy, estado__in=['PE', 'PC'])
        context['cuotas_vencidas'] = vencidas_qs.count()
        context['cartera_en_riesgo'] = vencidas_qs.aggregate(
            total=Sum(F('monto_cuota') - F('monto_pagado'))
        )['total'] or Decimal('0.00')

        # Ticket e interés promedio de la cartera activa
        promedios = prestamos_qs.aggregate(
            ticket_promedio=Avg('monto_solicitado'),
            interes_promedio=Avg('tasa_interes_porcentaje'),
        )
        context['ticket_promedio'] = promedios['ticket_promedio'] or Decimal('0.00')
        context['interes_promedio'] = promedios['interes_promedio'] or Decimal('0.00')

        # Distribución por categoría de clientes
        context['clientes_por_categoria'] = clientes_qs.values('categoria').annotate(
            cantidad=Count('id')
        )

        # --- Proyectado vs Cobrado, últimos 6 meses (por mes de vencimiento) ---
        inicio_rango = _primer_dia_mes_hace(hoy, 5)
        datos_mes = {
            d['mes']: d for d in cuotas_historicas_qs.filter(
                fecha_vencimiento__gte=inicio_rango
            ).annotate(mes=TruncMonth('fecha_vencimiento')).values('mes').annotate(
                proyectado=Sum('monto_cuota'),
                cobrado=Sum('monto_pagado'),
            )
        }
        meses_labels, proyectado_serie, cobrado_serie = [], [], []
        cursor = inicio_rango
        for _ in range(6):
            dato = datos_mes.get(cursor)
            meses_labels.append(MESES_ABREV[cursor.month - 1])
            proyectado_serie.append(float(dato['proyectado']) if dato and dato['proyectado'] else 0)
            cobrado_serie.append(float(dato['cobrado']) if dato and dato['cobrado'] else 0)
            cursor = _mes_siguiente(cursor)
        context['meses_labels'] = json.dumps(meses_labels)
        context['proyectado_serie'] = json.dumps(proyectado_serie)
        context['cobrado_serie'] = json.dumps(cobrado_serie)
        total_proyectado = sum(proyectado_serie)
        total_cobrado = sum(cobrado_serie)
        context['tasa_recuperacion'] = (
            round(total_cobrado / total_proyectado * 100, 1) if total_proyectado else 0
        )

        # --- Cartera por estado de préstamo ---
        cartera_por_estado = list(prestamos_historicos_qs.values('estado').annotate(
            cantidad=Count('id'),
            monto=Sum('monto_total_a_pagar'),
        ))
        nombres_estado = dict(Prestamo.Estado.choices)
        for item in cartera_por_estado:
            item['nombre'] = nombres_estado.get(item['estado'], item['estado'])
        context['cartera_por_estado'] = cartera_por_estado
        context['cartera_por_estado_labels'] = json.dumps([i['nombre'] for i in cartera_por_estado])
        context['cartera_por_estado_data'] = json.dumps([i['cantidad'] for i in cartera_por_estado])

        # --- Antigüedad de mora (aging), sobre cartera activa vencida ---
        buckets = [
            {'label': '1-7 días', 'min': 1, 'max': 7, 'cantidad': 0, 'monto': Decimal('0.00')},
            {'label': '8-15 días', 'min': 8, 'max': 15, 'cantidad': 0, 'monto': Decimal('0.00')},
            {'label': '16-30 días', 'min': 16, 'max': 30, 'cantidad': 0, 'monto': Decimal('0.00')},
            {'label': '31-60 días', 'min': 31, 'max': 60, 'cantidad': 0, 'monto': Decimal('0.00')},
            {'label': '+60 días', 'min': 61, 'max': None, 'cantidad': 0, 'monto': Decimal('0.00')},
        ]
        for cuota in vencidas_qs.only('fecha_vencimiento', 'monto_cuota', 'monto_pagado'):
            dias = (hoy - cuota.fecha_vencimiento).days
            restante = cuota.monto_cuota - cuota.monto_pagado
            for bucket in buckets:
                if dias >= bucket['min'] and (bucket['max'] is None or dias <= bucket['max']):
                    bucket['cantidad'] += 1
                    bucket['monto'] += restante
                    break
        context['aging_buckets'] = buckets
        context['aging_labels'] = json.dumps([b['label'] for b in buckets])
        context['aging_data'] = json.dumps([float(b['monto']) for b in buckets])

        # --- Métodos de pago, últimos 30 días ---
        desde_30 = hoy - timedelta(days=30)
        metodos = cuotas_historicas_qs.filter(fecha_pago_real__gte=desde_30).aggregate(
            efectivo=Sum('monto_efectivo'),
            transferencia=Sum('monto_transferencia'),
        )
        context['metodo_efectivo'] = metodos['efectivo'] or Decimal('0.00')
        context['metodo_transferencia'] = metodos['transferencia'] or Decimal('0.00')
        context['metodos_labels'] = json.dumps(['Efectivo', 'Transferencia'])
        context['metodos_data'] = json.dumps([
            float(metodos['efectivo'] or 0), float(metodos['transferencia'] or 0)
        ])

        # --- Préstamos otorgados por mes, últimos 6 meses ---
        datos_otorgados = {
            d['mes'].date(): d for d in prestamos_historicos_qs.filter(
                fecha_creacion__date__gte=inicio_rango
            ).annotate(mes=TruncMonth('fecha_creacion')).values('mes').annotate(
                cantidad=Count('id'),
                monto=Sum('monto_solicitado'),
            )
        }
        otorgados_labels, otorgados_cantidad = [], []
        cursor = inicio_rango
        for _ in range(6):
            dato = datos_otorgados.get(cursor)
            otorgados_labels.append(MESES_ABREV[cursor.month - 1])
            otorgados_cantidad.append(dato['cantidad'] if dato else 0)
            cursor = _mes_siguiente(cursor)
        context['otorgados_labels'] = json.dumps(otorgados_labels)
        context['otorgados_data'] = json.dumps(otorgados_cantidad)

        # --- Ranking de cobradores del mes (solo admin) ---
        if es_admin:
            inicio_mes = hoy.replace(day=1)
            ranking = list(Cuota.objects.filter(
                fecha_pago_real__gte=inicio_mes,
                estado__in=['PA', 'PC'],
                cobrado_por__isnull=False,
            ).values(
                'cobrado_por__username', 'cobrado_por__first_name', 'cobrado_por__last_name'
            ).annotate(monto=Sum('monto_pagado')).order_by('-monto')[:10])
            maximo = max((r['monto'] for r in ranking), default=Decimal('0.00')) or Decimal('1.00')
            for r in ranking:
                nombre_completo = f"{r['cobrado_por__first_name']} {r['cobrado_por__last_name']}".strip()
                r['nombre'] = nombre_completo or r['cobrado_por__username']
                r['porcentaje'] = int(r['monto'] / maximo * 100)
            context['ranking_cobradores'] = ranking

        # --- Top 5 clientes con mayor monto adeudado en mora ---
        top_morosos = list(vencidas_qs.values(
            'prestamo__cliente__id', 'prestamo__cliente__nombre', 'prestamo__cliente__apellido'
        ).annotate(
            monto_adeudado=Sum(F('monto_cuota') - F('monto_pagado')),
            cuotas_atrasadas=Count('id'),
        ).order_by('-monto_adeudado')[:5])
        context['top_morosos'] = top_morosos

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
        if not es_usuario_admin(request.user):
            messages.error(request, 'No tienes permiso para acceder a esta sección.')
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Excluir superusuarios (cuentas de desarrolladores) del listado
        return User.objects.select_related('perfil').exclude(is_superuser=True).order_by('-date_joined')


class UsuarioCreateView(LoginRequiredMixin, TemplateView):
    """Crear nuevo usuario"""
    template_name = 'core/usuario_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Solo admins pueden crear usuarios
        if not es_usuario_admin(request.user):
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
    
    def get_user(self):
        user = get_object_or_404(User, pk=self.kwargs['pk'])
        # No permitir editar superusuarios (cuentas de desarrolladores)
        if user.is_superuser:
            return None
        return user

    def dispatch(self, request, *args, **kwargs):
        # Solo admins pueden editar usuarios
        if not es_usuario_admin(request.user):
            messages.error(request, 'No tienes permiso para editar usuarios.')
            return redirect('core:dashboard')
        # Verificar que no se intente editar un superusuario
        user = get_object_or_404(User, pk=self.kwargs['pk'])
        if user.is_superuser:
            messages.error(request, 'No tienes permiso para editar este usuario.')
            return redirect('core:usuario_list')
        return super().dispatch(request, *args, **kwargs)
    
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
    if not es_usuario_admin(request.user):
        messages.error(request, 'No tienes permiso para realizar esta acción.')
        return redirect('core:dashboard')
    
    user = get_object_or_404(User, pk=pk)
    
    # No permitir modificar superusuarios (cuentas de desarrolladores)
    if user.is_superuser:
        messages.error(request, 'No tienes permiso para modificar este usuario.')
        return redirect('core:usuario_list')
    
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


# ==================== EXPORTACIÓN EXCEL ====================

from django.http import HttpResponse
from .models import RegistroAuditoria, Notificacion, ConfiguracionRespaldo
import io
import os
from datetime import datetime


@login_required
def exportar_planilla_excel(request):
    """Exportar planilla de cobros a Excel"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        messages.error(request, 'La exportación a Excel no está disponible. Instale openpyxl.')
        return redirect('core:planilla_impresion')
    
    # Obtener fecha del filtro
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            fecha = fecha_local_hoy()
    else:
        fecha = fecha_local_hoy()

    # Obtener ruta de filtro
    ruta_id = request.GET.get('ruta')
    incluir_vencidas = request.GET.get('incluir_vencidas', '1').lower() in ('true', '1', 'si')
    
    # Obtener cuotas pendientes
    cuotas = Cuota.objects.filter(
        prestamo__estado='AC',
        estado__in=['PE', 'PC']
    )
    if not es_usuario_admin(request.user):
        cuotas = cuotas.filter(prestamo__cobrador=request.user)
    cuotas = cuotas.select_related('prestamo', 'prestamo__cliente', 'prestamo__cliente__ruta')
    
    if incluir_vencidas:
        cuotas = cuotas.filter(fecha_vencimiento__lte=fecha)
    else:
        cuotas = cuotas.filter(fecha_vencimiento=fecha)
    
    if ruta_id:
        cuotas = cuotas.filter(prestamo__cliente__ruta_id=ruta_id)
    
    cuotas = cuotas.order_by('prestamo__cliente__ruta__orden', 'prestamo__cliente__apellido')
    
    # Crear workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Planilla {fecha.strftime('%d-%m-%Y')}"
    
    # Pre-cargar historial de modificaciones (cuotas que recibieron monto)
    cuota_ids = list(cuotas.values_list('id', flat=True))
    cuotas_con_monto_recibido = {}
    if cuota_ids:
        historiales_recibidos = HistorialModificacionPago.objects.filter(
            cuota_id__in=cuota_ids,
            tipo_modificacion='MR'
        ).select_related('cuota_relacionada')
        for h in historiales_recibidos:
            cuotas_con_monto_recibido[h.cuota_id] = h
    
    # Estilos
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='333333', end_color='333333', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    recibida_fill = PatternFill(start_color='D1ECF1', end_color='D1ECF1', fill_type='solid')  # Celeste claro
    
    # Título
    ws.merge_cells('A1:M1')
    ws['A1'] = f'PLANILLA DE COBROS - {fecha.strftime("%d/%m/%Y")}'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    # Info
    ws.merge_cells('A2:M2')
    ws['A2'] = f'Total cobros: {cuotas.count()} | Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}'
    ws['A2'].alignment = Alignment(horizontal='center')
    
    # Leyenda
    ws.merge_cells('A3:M3')
    ws['A3'] = '■ Celeste = Cuota modificada (recibió monto de otra cuota por pago parcial)'
    ws['A3'].font = Font(italic=True, size=9)
    ws['A3'].alignment = Alignment(horizontal='center')
    
    # Headers
    headers = ['#', 'Préstamo', 'Cliente', 'Teléfono', 'Ruta', 'Cuota', 'Monto', 'Monto Original', 'Venc.', 'Fecha Fin', 'Cobrado', 'Modificada', 'Observaciones']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
    
    # Anchos de columna
    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 10
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 16
    ws.column_dimensions['I'].width = 12
    ws.column_dimensions['J'].width = 14
    ws.column_dimensions['K'].width = 15
    ws.column_dimensions['L'].width = 14
    ws.column_dimensions['M'].width = 40
    
    # Datos
    total = Decimal('0.00')
    for i, cuota in enumerate(cuotas, 1):
        row = i + 5
        ws.cell(row=row, column=1, value=i).border = border
        ws.cell(row=row, column=2, value=f'#{cuota.prestamo.pk}').border = border
        ws.cell(row=row, column=3, value=cuota.prestamo.cliente.nombre_completo).border = border
        ws.cell(row=row, column=4, value=cuota.prestamo.cliente.telefono).border = border
        ws.cell(row=row, column=5, value=cuota.prestamo.cliente.ruta.nombre if cuota.prestamo.cliente.ruta else 'Sin Ruta').border = border
        ws.cell(row=row, column=6, value=f'{cuota.numero_cuota}/{cuota.prestamo.cuotas_pactadas}').border = border
        
        monto_cell = ws.cell(row=row, column=7, value=float(cuota.monto_cuota))
        monto_cell.number_format = '#,##0'
        monto_cell.border = border
        
        # Columna Monto Original y Observaciones
        recibido = cuotas_con_monto_recibido.get(cuota.id)
        fue_modificada = recibido is not None
        
        if recibido:
            orig_cell = ws.cell(row=row, column=8, value=float(recibido.monto_cuota_anterior))
            orig_cell.number_format = '#,##0'
        else:
            orig_cell = ws.cell(row=row, column=8, value='-')
        orig_cell.border = border
        
        ws.cell(row=row, column=9, value=cuota.fecha_vencimiento.strftime('%d/%m')).border = border
        ws.cell(row=row, column=10, value=cuota.prestamo.fecha_finalizacion.strftime('%d/%m/%Y') if cuota.prestamo.fecha_finalizacion else '-').border = border
        ws.cell(row=row, column=11, value='').border = border
        
        mod_cell = ws.cell(row=row, column=12, value='SÍ' if fue_modificada else '-')
        mod_cell.border = border
        mod_cell.alignment = Alignment(horizontal='center')
        if fue_modificada:
            mod_cell.font = Font(bold=True, color='856404')
        
        obs_text = ''
        if recibido:
            origen = f' de cuota #{recibido.cuota_relacionada.numero_cuota}' if recibido.cuota_relacionada else ''
            obs_text = f'Recibió ${recibido.monto_restante_transferido:,.0f}{origen}'
            if recibido.interes_mora > 0:
                obs_text += f' (mora: ${recibido.interes_mora:,.0f})'
        
        obs_cell = ws.cell(row=row, column=13, value=obs_text if obs_text else '-')
        obs_cell.border = border
        obs_cell.alignment = Alignment(wrap_text=True)
        
        # Aplicar color de fondo si fue modificada
        if fue_modificada:
            for col_idx in range(1, 14):
                ws.cell(row=row, column=col_idx).fill = recibida_fill
        
        total += cuota.monto_cuota
    
    # Fila de total
    total_row = cuotas.count() + 6
    ws.merge_cells(f'A{total_row}:G{total_row}')
    ws.cell(row=total_row, column=1, value='TOTAL ESPERADO:').font = Font(bold=True)
    total_cell = ws.cell(row=total_row, column=8, value=float(total))
    total_cell.font = Font(bold=True)
    total_cell.number_format = '#,##0'
    
    # Registrar auditoría
    RegistroAuditoria.registrar(
        usuario=request.user,
        tipo_accion='OT',
        tipo_modelo='SI',
        descripcion=f'Exportación de planilla a Excel - Fecha: {fecha}',
        ip_address=get_client_ip(request)
    )
    
    # Crear respuesta
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=planilla_cobros_{fecha.strftime("%Y%m%d")}.xlsx'
    
    wb.save(response)
    return response


@login_required
def exportar_cierre_excel(request):
    """Exportar cierre de caja a Excel con cobros realizados"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        messages.error(request, 'La exportación a Excel no está disponible. Instale openpyxl.')
        return redirect('core:cierre_caja')
    
    # Obtener fecha
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            fecha = fecha_local_hoy()
    else:
        fecha = fecha_local_hoy()
    
    # Obtener cobros del día (completos y parciales)
    pagos = Cuota.objects.filter(
        fecha_pago_real=fecha,
        estado__in=['PA', 'PC']
    )
    if not es_usuario_admin(request.user):
        pagos = pagos.filter(prestamo__cobrador=request.user)
    pagos = pagos.select_related('prestamo', 'prestamo__cliente', 'prestamo__cliente__ruta', 'cobrado_por').order_by(
        'prestamo__cliente__apellido'
    )
    
    # Pre-cargar historial de modificaciones para las cuotas del día
    cuota_ids = list(pagos.values_list('id', flat=True))
    historial_por_cuota = {}
    if cuota_ids:
        historiales = HistorialModificacionPago.objects.filter(
            cuota_id__in=cuota_ids
        ).select_related('cuota_relacionada').order_by('fecha_modificacion')
        for h in historiales:
            if h.cuota_id not in historial_por_cuota:
                historial_por_cuota[h.cuota_id] = []
            historial_por_cuota[h.cuota_id].append(h)
    
    # También buscar cuotas que recibieron monto (fueron modificadas por un pago parcial previo)
    cuotas_con_monto_recibido = {}
    historiales_recibidos = HistorialModificacionPago.objects.filter(
        cuota_id__in=cuota_ids,
        tipo_modificacion='MR'
    ).select_related('cuota_relacionada')
    for h in historiales_recibidos:
        cuotas_con_monto_recibido[h.cuota_id] = h
    
    # Crear workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Cierre {fecha.strftime('%d-%m-%Y')}"
    
    # Estilos
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='198754', end_color='198754', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    modificada_fill = PatternFill(start_color='FFF3CD', end_color='FFF3CD', fill_type='solid')  # Amarillo claro
    recibida_fill = PatternFill(start_color='D1ECF1', end_color='D1ECF1', fill_type='solid')  # Celeste claro
    
    # Título
    ws.merge_cells('A1:S1')
    ws['A1'] = f'CIERRE DE CAJA - {fecha.strftime("%d/%m/%Y")}'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    total_cobrado = pagos.aggregate(total=Sum('monto_pagado'))['total'] or Decimal('0.00')
    total_efectivo = pagos.aggregate(total=Sum('monto_efectivo'))['total'] or Decimal('0.00')
    total_transferencia = pagos.aggregate(total=Sum('monto_transferencia'))['total'] or Decimal('0.00')
    ws.merge_cells('A2:S2')
    ws['A2'] = f'Total cobrado: ${total_cobrado:,.0f} (Efectivo: ${total_efectivo:,.0f} | Transferencia: ${total_transferencia:,.0f}) | Pagos: {pagos.count()} | Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}'
    ws['A2'].alignment = Alignment(horizontal='center')
    
    # Leyenda de colores
    ws.merge_cells('A3:S3')
    ws['A3'] = '■ Amarillo = Pago parcial (se transfirió monto a otra cuota)  |  ■ Celeste = Cuota que recibió monto de otra cuota'
    ws['A3'].font = Font(italic=True, size=9)
    ws['A3'].alignment = Alignment(horizontal='center')
    
    # Headers - ahora con columnas de modificaciones
    headers = ['#', 'Préstamo', 'Cliente', 'Dirección', 'Teléfono', 'Cuota', 'Monto Cuota', 'Cobrado', 
               'Método Pago', 'Efectivo', 'Transferencia', 'Estado', 'Fecha Inicio', 
               '% Interés', 'Fecha Fin Préstamo', 'Cobrador',
               'Modificada', 'Monto Original', 'Observaciones']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
    
    # Anchos
    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 30
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 10
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 15
    ws.column_dimensions['I'].width = 16
    ws.column_dimensions['J'].width = 15
    ws.column_dimensions['K'].width = 15
    ws.column_dimensions['L'].width = 12
    ws.column_dimensions['M'].width = 16
    ws.column_dimensions['N'].width = 12
    ws.column_dimensions['O'].width = 16
    ws.column_dimensions['P'].width = 20
    ws.column_dimensions['Q'].width = 14
    ws.column_dimensions['R'].width = 16
    ws.column_dimensions['S'].width = 45
    
    # Datos
    total = Decimal('0.00')
    for i, pago in enumerate(pagos, 1):
        row = i + 5
        ws.cell(row=row, column=1, value=i).border = border
        ws.cell(row=row, column=2, value=f'#{pago.prestamo.pk}').border = border
        ws.cell(row=row, column=3, value=pago.prestamo.cliente.nombre_completo).border = border
        ws.cell(row=row, column=4, value=pago.prestamo.cliente.direccion or '-').border = border
        ws.cell(row=row, column=5, value=pago.prestamo.cliente.telefono).border = border
        ws.cell(row=row, column=6, value=f'{pago.numero_cuota}/{pago.prestamo.cuotas_pactadas}').border = border
        
        monto_cell = ws.cell(row=row, column=7, value=float(pago.monto_cuota))
        monto_cell.number_format = '#,##0'
        monto_cell.border = border
        
        cobrado_cell = ws.cell(row=row, column=8, value=float(pago.monto_pagado))
        cobrado_cell.number_format = '#,##0'
        cobrado_cell.border = border
        cobrado_cell.font = Font(bold=True, color='198754')
        
        ws.cell(row=row, column=9, value=pago.get_metodo_pago_display()).border = border
        
        ef_cell = ws.cell(row=row, column=10, value=float(pago.monto_efectivo or 0))
        ef_cell.number_format = '#,##0'
        ef_cell.border = border
        
        tr_cell = ws.cell(row=row, column=11, value=float(pago.monto_transferencia or 0))
        tr_cell.number_format = '#,##0'
        tr_cell.border = border
        
        ws.cell(row=row, column=12, value=pago.get_estado_display()).border = border
        ws.cell(row=row, column=13, value=pago.prestamo.fecha_inicio.strftime('%d/%m/%Y')).border = border
        ws.cell(row=row, column=14, value=f'{pago.prestamo.tasa_interes_porcentaje}%').border = border
        ws.cell(row=row, column=15, value=pago.prestamo.fecha_finalizacion.strftime('%d/%m/%Y') if pago.prestamo.fecha_finalizacion else '-').border = border
        ws.cell(row=row, column=16, value=pago.cobrado_por.get_full_name() or pago.cobrado_por.username if pago.cobrado_por else '-').border = border
        
        # --- Columnas de Modificaciones ---
        historial = historial_por_cuota.get(pago.id, [])
        recibido = cuotas_con_monto_recibido.get(pago.id)
        
        fue_modificada = False
        monto_original = ''
        observaciones_parts = []
        row_fill = None
        
        for h in historial:
            if h.tipo_modificacion == 'PP':
                fue_modificada = True
                row_fill = modificada_fill
                if h.monto_restante_transferido > 0:
                    observaciones_parts.append(
                        f'Pago parcial: cobrado ${h.monto_pagado:,.0f} de ${h.monto_cuota_anterior:,.0f}. '
                        f'Restante ${h.monto_restante_transferido:,.0f} transferido'
                    )
                else:
                    observaciones_parts.append(
                        f'Pago parcial: cobrado ${h.monto_pagado:,.0f} de ${h.monto_cuota_anterior:,.0f}'
                    )
            elif h.tipo_modificacion == 'TR':
                destino = f' a cuota #{h.cuota_relacionada.numero_cuota}' if h.cuota_relacionada else ''
                observaciones_parts.append(
                    f'Transferido ${h.monto_restante_transferido:,.0f}{destino}'
                )
                if h.interes_mora > 0:
                    observaciones_parts.append(f'(incluye mora: ${h.interes_mora:,.0f})')
            elif h.tipo_modificacion == 'CE':
                destino = f' (cuota #{h.cuota_relacionada.numero_cuota})' if h.cuota_relacionada else ''
                observaciones_parts.append(
                    f'Cuota especial creada por ${h.monto_restante_transferido:,.0f}{destino}'
                )
        
        if recibido:
            fue_modificada = True
            if not row_fill:
                row_fill = recibida_fill
            monto_original = float(recibido.monto_cuota_anterior)
            origen = f' de cuota #{recibido.cuota_relacionada.numero_cuota}' if recibido.cuota_relacionada else ''
            observaciones_parts.insert(0,
                f'Recibió ${recibido.monto_restante_transferido:,.0f}{origen}'
            )
            if recibido.interes_mora > 0:
                observaciones_parts.insert(1, f'(incluye mora: ${recibido.interes_mora:,.0f})')
        
        mod_cell = ws.cell(row=row, column=17, value='SÍ' if fue_modificada else '-')
        mod_cell.border = border
        mod_cell.alignment = Alignment(horizontal='center')
        if fue_modificada:
            mod_cell.font = Font(bold=True, color='856404')
        
        orig_cell = ws.cell(row=row, column=18, value=monto_original if monto_original else '-')
        if isinstance(monto_original, float):
            orig_cell.number_format = '#,##0'
        orig_cell.border = border
        
        obs_cell = ws.cell(row=row, column=19, value=' | '.join(observaciones_parts) if observaciones_parts else '-')
        obs_cell.border = border
        obs_cell.alignment = Alignment(wrap_text=True)
        
        # Aplicar color de fondo a toda la fila si fue modificada
        if row_fill:
            for col_idx in range(1, 20):
                ws.cell(row=row, column=col_idx).fill = row_fill
        
        total += pago.monto_pagado
    
    # Fila total
    total_row = pagos.count() + 6
    ws.merge_cells(f'A{total_row}:G{total_row}')
    total_label = ws.cell(row=total_row, column=1, value='TOTAL COBRADO:')
    total_label.font = Font(bold=True, size=12)
    total_cell = ws.cell(row=total_row, column=8, value=float(total))
    total_cell.font = Font(bold=True, size=12, color='198754')
    total_cell.number_format = '#,##0'
    
    # Totales efectivo y transferencia
    ef_total_cell = ws.cell(row=total_row, column=10, value=float(total_efectivo))
    ef_total_cell.font = Font(bold=True, size=11)
    ef_total_cell.number_format = '#,##0'
    tr_total_cell = ws.cell(row=total_row, column=11, value=float(total_transferencia))
    tr_total_cell.font = Font(bold=True, size=11)
    tr_total_cell.number_format = '#,##0'
    
    # Registrar auditoría
    RegistroAuditoria.registrar(
        usuario=request.user,
        tipo_accion='OT',
        tipo_modelo='SI',
        descripcion=f'Exportación de cierre de caja a Excel - Fecha: {fecha}',
        ip_address=get_client_ip(request)
    )
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=cierre_caja_{fecha.strftime("%Y%m%d")}.xlsx'
    wb.save(response)
    return response


def construir_excel_planilla_cobrador(fecha, cobrador):
    """
    Arma la hoja de ruta diaria de un cobrador (C3): sus cuotas a cobrar
    (vencidas + de hoy) ordenadas por zona, con dirección, teléfono y
    monto — pensada para llevar en el celular, más simple que la planilla
    general de exportar_planilla_excel (esa es para el back-office).
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    cuotas = Cuota.objects.filter(
        prestamo__estado='AC',
        prestamo__cobrador=cobrador,
        estado__in=['PE', 'PC'],
        fecha_vencimiento__lte=fecha
    ).select_related('prestamo', 'prestamo__cliente', 'prestamo__cliente__ruta').order_by(
        'prestamo__cliente__ruta__orden', 'prestamo__cliente__ruta__nombre', 'prestamo__cliente__apellido'
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    nombre_cobrador = cobrador.get_full_name() or cobrador.username
    ws.title = 'Ruta del día'

    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='0d6efd', end_color='0d6efd', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    ws.merge_cells('A1:F1')
    ws['A1'] = f'RUTA DEL DÍA - {nombre_cobrador} - {fecha.strftime("%d/%m/%Y")}'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')

    total_esperado = sum((c.monto_restante for c in cuotas), Decimal('0.00'))
    ws.merge_cells('A2:F2')
    ws['A2'] = f'Total esperado: ${total_esperado:,.0f} | Clientes a visitar: {cuotas.count()}'
    ws['A2'].alignment = Alignment(horizontal='center')

    headers = ['#', 'Cliente', 'Dirección', 'Teléfono', 'Zona', 'Monto']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border

    for col, width in zip('ABCDEF', [5, 25, 32, 15, 15, 14]):
        ws.column_dimensions[col].width = width

    for i, cuota in enumerate(cuotas, 1):
        row = i + 4
        ws.cell(row=row, column=1, value=i).border = border
        ws.cell(row=row, column=2, value=cuota.prestamo.cliente.nombre_completo).border = border
        ws.cell(row=row, column=3, value=cuota.prestamo.cliente.direccion or '-').border = border
        ws.cell(row=row, column=4, value=cuota.prestamo.cliente.telefono).border = border
        ws.cell(row=row, column=5, value=cuota.prestamo.cliente.ruta.nombre if cuota.prestamo.cliente.ruta else 'Sin zona').border = border
        monto_cell = ws.cell(row=row, column=6, value=float(cuota.monto_restante))
        monto_cell.number_format = '#,##0'
        monto_cell.border = border

    return wb


def construir_excel_cierre_caja(fecha, pagos):
    """
    Arma el Workbook de cierre de caja para una fecha, a partir de un
    queryset de Cuota ya filtrado (por cobrador o completo, según quién
    lo pida). Reutilizado por la exportación manual y por el comando
    programado cierre_caja_automatico (C1).
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    # Pre-cargar historial de modificaciones para las cuotas del día
    cuota_ids = list(pagos.values_list('id', flat=True))
    historial_por_cuota = {}
    if cuota_ids:
        historiales = HistorialModificacionPago.objects.filter(
            cuota_id__in=cuota_ids
        ).select_related('cuota_relacionada').order_by('fecha_modificacion')
        for h in historiales:
            if h.cuota_id not in historial_por_cuota:
                historial_por_cuota[h.cuota_id] = []
            historial_por_cuota[h.cuota_id].append(h)
    
    # También buscar cuotas que recibieron monto (fueron modificadas por un pago parcial previo)
    cuotas_con_monto_recibido = {}
    historiales_recibidos = HistorialModificacionPago.objects.filter(
        cuota_id__in=cuota_ids,
        tipo_modificacion='MR'
    ).select_related('cuota_relacionada')
    for h in historiales_recibidos:
        cuotas_con_monto_recibido[h.cuota_id] = h
    
    # Crear workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Cierre {fecha.strftime('%d-%m-%Y')}"
    
    # Estilos
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='198754', end_color='198754', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    modificada_fill = PatternFill(start_color='FFF3CD', end_color='FFF3CD', fill_type='solid')  # Amarillo claro
    recibida_fill = PatternFill(start_color='D1ECF1', end_color='D1ECF1', fill_type='solid')  # Celeste claro
    
    # Título
    ws.merge_cells('A1:S1')
    ws['A1'] = f'CIERRE DE CAJA - {fecha.strftime("%d/%m/%Y")}'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')
    
    total_cobrado = pagos.aggregate(total=Sum('monto_pagado'))['total'] or Decimal('0.00')
    total_efectivo = pagos.aggregate(total=Sum('monto_efectivo'))['total'] or Decimal('0.00')
    total_transferencia = pagos.aggregate(total=Sum('monto_transferencia'))['total'] or Decimal('0.00')
    ws.merge_cells('A2:S2')
    ws['A2'] = f'Total cobrado: ${total_cobrado:,.0f} (Efectivo: ${total_efectivo:,.0f} | Transferencia: ${total_transferencia:,.0f}) | Pagos: {pagos.count()} | Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}'
    ws['A2'].alignment = Alignment(horizontal='center')
    
    # Leyenda de colores
    ws.merge_cells('A3:S3')
    ws['A3'] = '■ Amarillo = Pago parcial (se transfirió monto a otra cuota)  |  ■ Celeste = Cuota que recibió monto de otra cuota'
    ws['A3'].font = Font(italic=True, size=9)
    ws['A3'].alignment = Alignment(horizontal='center')
    
    # Headers - ahora con columnas de modificaciones
    headers = ['#', 'Préstamo', 'Cliente', 'Dirección', 'Teléfono', 'Cuota', 'Monto Cuota', 'Cobrado', 
               'Método Pago', 'Efectivo', 'Transferencia', 'Estado', 'Fecha Inicio', 
               '% Interés', 'Fecha Fin Préstamo', 'Cobrador',
               'Modificada', 'Monto Original', 'Observaciones']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
    
    # Anchos
    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 30
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 10
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 15
    ws.column_dimensions['I'].width = 16
    ws.column_dimensions['J'].width = 15
    ws.column_dimensions['K'].width = 15
    ws.column_dimensions['L'].width = 12
    ws.column_dimensions['M'].width = 16
    ws.column_dimensions['N'].width = 12
    ws.column_dimensions['O'].width = 16
    ws.column_dimensions['P'].width = 20
    ws.column_dimensions['Q'].width = 14
    ws.column_dimensions['R'].width = 16
    ws.column_dimensions['S'].width = 45
    
    # Datos
    total = Decimal('0.00')
    for i, pago in enumerate(pagos, 1):
        row = i + 5
        ws.cell(row=row, column=1, value=i).border = border
        ws.cell(row=row, column=2, value=f'#{pago.prestamo.pk}').border = border
        ws.cell(row=row, column=3, value=pago.prestamo.cliente.nombre_completo).border = border
        ws.cell(row=row, column=4, value=pago.prestamo.cliente.direccion or '-').border = border
        ws.cell(row=row, column=5, value=pago.prestamo.cliente.telefono).border = border
        ws.cell(row=row, column=6, value=f'{pago.numero_cuota}/{pago.prestamo.cuotas_pactadas}').border = border
        
        monto_cell = ws.cell(row=row, column=7, value=float(pago.monto_cuota))
        monto_cell.number_format = '#,##0'
        monto_cell.border = border
        
        cobrado_cell = ws.cell(row=row, column=8, value=float(pago.monto_pagado))
        cobrado_cell.number_format = '#,##0'
        cobrado_cell.border = border
        cobrado_cell.font = Font(bold=True, color='198754')
        
        ws.cell(row=row, column=9, value=pago.get_metodo_pago_display()).border = border
        
        ef_cell = ws.cell(row=row, column=10, value=float(pago.monto_efectivo or 0))
        ef_cell.number_format = '#,##0'
        ef_cell.border = border
        
        tr_cell = ws.cell(row=row, column=11, value=float(pago.monto_transferencia or 0))
        tr_cell.number_format = '#,##0'
        tr_cell.border = border
        
        ws.cell(row=row, column=12, value=pago.get_estado_display()).border = border
        ws.cell(row=row, column=13, value=pago.prestamo.fecha_inicio.strftime('%d/%m/%Y')).border = border
        ws.cell(row=row, column=14, value=f'{pago.prestamo.tasa_interes_porcentaje}%').border = border
        ws.cell(row=row, column=15, value=pago.prestamo.fecha_finalizacion.strftime('%d/%m/%Y') if pago.prestamo.fecha_finalizacion else '-').border = border
        ws.cell(row=row, column=16, value=pago.cobrado_por.get_full_name() or pago.cobrado_por.username if pago.cobrado_por else '-').border = border
        
        # --- Columnas de Modificaciones ---
        historial = historial_por_cuota.get(pago.id, [])
        recibido = cuotas_con_monto_recibido.get(pago.id)
        
        fue_modificada = False
        monto_original = ''
        observaciones_parts = []
        row_fill = None
        
        for h in historial:
            if h.tipo_modificacion == 'PP':
                fue_modificada = True
                row_fill = modificada_fill
                if h.monto_restante_transferido > 0:
                    observaciones_parts.append(
                        f'Pago parcial: cobrado ${h.monto_pagado:,.0f} de ${h.monto_cuota_anterior:,.0f}. '
                        f'Restante ${h.monto_restante_transferido:,.0f} transferido'
                    )
                else:
                    observaciones_parts.append(
                        f'Pago parcial: cobrado ${h.monto_pagado:,.0f} de ${h.monto_cuota_anterior:,.0f}'
                    )
            elif h.tipo_modificacion == 'TR':
                destino = f' a cuota #{h.cuota_relacionada.numero_cuota}' if h.cuota_relacionada else ''
                observaciones_parts.append(
                    f'Transferido ${h.monto_restante_transferido:,.0f}{destino}'
                )
                if h.interes_mora > 0:
                    observaciones_parts.append(f'(incluye mora: ${h.interes_mora:,.0f})')
            elif h.tipo_modificacion == 'CE':
                destino = f' (cuota #{h.cuota_relacionada.numero_cuota})' if h.cuota_relacionada else ''
                observaciones_parts.append(
                    f'Cuota especial creada por ${h.monto_restante_transferido:,.0f}{destino}'
                )
        
        if recibido:
            fue_modificada = True
            if not row_fill:
                row_fill = recibida_fill
            monto_original = float(recibido.monto_cuota_anterior)
            origen = f' de cuota #{recibido.cuota_relacionada.numero_cuota}' if recibido.cuota_relacionada else ''
            observaciones_parts.insert(0,
                f'Recibió ${recibido.monto_restante_transferido:,.0f}{origen}'
            )
            if recibido.interes_mora > 0:
                observaciones_parts.insert(1, f'(incluye mora: ${recibido.interes_mora:,.0f})')
        
        mod_cell = ws.cell(row=row, column=17, value='SÍ' if fue_modificada else '-')
        mod_cell.border = border
        mod_cell.alignment = Alignment(horizontal='center')
        if fue_modificada:
            mod_cell.font = Font(bold=True, color='856404')
        
        orig_cell = ws.cell(row=row, column=18, value=monto_original if monto_original else '-')
        if isinstance(monto_original, float):
            orig_cell.number_format = '#,##0'
        orig_cell.border = border
        
        obs_cell = ws.cell(row=row, column=19, value=' | '.join(observaciones_parts) if observaciones_parts else '-')
        obs_cell.border = border
        obs_cell.alignment = Alignment(wrap_text=True)
        
        # Aplicar color de fondo a toda la fila si fue modificada
        if row_fill:
            for col_idx in range(1, 20):
                ws.cell(row=row, column=col_idx).fill = row_fill
        
        total += pago.monto_pagado
    
    # Fila total
    total_row = pagos.count() + 6
    ws.merge_cells(f'A{total_row}:G{total_row}')
    total_label = ws.cell(row=total_row, column=1, value='TOTAL COBRADO:')
    total_label.font = Font(bold=True, size=12)
    total_cell = ws.cell(row=total_row, column=8, value=float(total))
    total_cell.font = Font(bold=True, size=12, color='198754')
    total_cell.number_format = '#,##0'
    
    # Totales efectivo y transferencia
    ef_total_cell = ws.cell(row=total_row, column=10, value=float(total_efectivo))
    ef_total_cell.font = Font(bold=True, size=11)
    ef_total_cell.number_format = '#,##0'
    tr_total_cell = ws.cell(row=total_row, column=11, value=float(total_transferencia))
    tr_total_cell.font = Font(bold=True, size=11)
    tr_total_cell.number_format = '#,##0'

    return wb


def construir_excel_morosidad(fecha):
    """
    Arma el Workbook semanal de morosidad (C2): quiénes están atrasados hoy
    y cuánto se espera cobrar en los próximos 7 días. Usado por el comando
    morosidad_semanal.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from datetime import timedelta

    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='dc3545', end_color='dc3545', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    vencidas = Cuota.objects.filter(
        fecha_vencimiento__lt=fecha,
        estado__in=['PE', 'PC'],
        prestamo__estado='AC'
    ).select_related('prestamo', 'prestamo__cliente', 'prestamo__cliente__ruta').order_by('-fecha_vencimiento')
    vencidas = sorted(vencidas, key=lambda c: c.monto_restante, reverse=True)

    proyeccion = Cuota.objects.filter(
        fecha_vencimiento__gt=fecha,
        fecha_vencimiento__lte=fecha + timedelta(days=7),
        estado__in=['PE', 'PC'],
        prestamo__estado='AC'
    ).select_related('prestamo', 'prestamo__cliente').order_by('fecha_vencimiento')

    wb = openpyxl.Workbook()

    # --- Hoja 1: Morosidad ---
    ws = wb.active
    ws.title = 'Morosidad'
    ws.merge_cells('A1:F1')
    ws['A1'] = f'MOROSIDAD AL {fecha.strftime("%d/%m/%Y")}'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A1'].alignment = Alignment(horizontal='center')

    total_adeudado = sum((c.monto_restante for c in vencidas), Decimal('0.00'))
    ws.merge_cells('A2:F2')
    ws['A2'] = f'Total adeudado: ${total_adeudado:,.0f} | Clientes atrasados: {len(set(c.prestamo.cliente_id for c in vencidas))} | Cuotas vencidas: {len(vencidas)}'
    ws['A2'].alignment = Alignment(horizontal='center')

    headers = ['Cliente', 'Teléfono', 'Ruta', 'Préstamo', 'Días de atraso', 'Monto adeudado']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border

    for i, cuota in enumerate(vencidas, 1):
        row = i + 4
        ws.cell(row=row, column=1, value=cuota.prestamo.cliente.nombre_completo).border = border
        ws.cell(row=row, column=2, value=cuota.prestamo.cliente.telefono).border = border
        ws.cell(row=row, column=3, value=cuota.prestamo.cliente.ruta.nombre if cuota.prestamo.cliente.ruta else '-').border = border
        ws.cell(row=row, column=4, value=f'#{cuota.prestamo.pk}').border = border
        ws.cell(row=row, column=5, value=cuota.dias_vencida).border = border
        monto_cell = ws.cell(row=row, column=6, value=float(cuota.monto_restante))
        monto_cell.number_format = '#,##0'
        monto_cell.border = border

    for col, width in zip('ABCDEF', [25, 15, 15, 12, 14, 16]):
        ws.column_dimensions[col].width = width

    # --- Hoja 2: Proyección próxima semana ---
    ws2 = wb.create_sheet('Proyección 7 días')
    ws2.merge_cells('A1:D1')
    ws2['A1'] = f'PROYECCIÓN {(fecha + timedelta(days=1)).strftime("%d/%m")} al {(fecha + timedelta(days=7)).strftime("%d/%m/%Y")}'
    ws2['A1'].font = Font(bold=True, size=14)
    ws2['A1'].alignment = Alignment(horizontal='center')

    total_proyectado = sum((c.monto_restante for c in proyeccion), Decimal('0.00'))
    ws2.merge_cells('A2:D2')
    ws2['A2'] = f'Total a cobrar: ${total_proyectado:,.0f} | Cuotas: {proyeccion.count()}'
    ws2['A2'].alignment = Alignment(horizontal='center')

    headers2 = ['Cliente', 'Préstamo', 'Fecha de vencimiento', 'Monto']
    for col, header in enumerate(headers2, 1):
        cell = ws2.cell(row=4, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border

    for i, cuota in enumerate(proyeccion, 1):
        row = i + 4
        ws2.cell(row=row, column=1, value=cuota.prestamo.cliente.nombre_completo).border = border
        ws2.cell(row=row, column=2, value=f'#{cuota.prestamo.pk}').border = border
        ws2.cell(row=row, column=3, value=cuota.fecha_vencimiento.strftime('%d/%m/%Y')).border = border
        monto_cell2 = ws2.cell(row=row, column=4, value=float(cuota.monto_restante))
        monto_cell2.number_format = '#,##0'
        monto_cell2.border = border

    for col, width in zip('ABCD', [25, 12, 20, 16]):
        ws2.column_dimensions[col].width = width

    return wb


@login_required
def exportar_clientes_excel(request):
    """Exportar lista de clientes a Excel"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        messages.error(request, 'La exportación a Excel no está disponible. Instale openpyxl.')
        return redirect('core:cliente_list')
    
    clientes = Cliente.objects.filter(estado='AC')
    if not es_usuario_admin(request.user):
        clientes = clientes.filter(usuario=request.user)
    clientes = clientes.select_related('ruta', 'tipo_negocio')
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Clientes"
    
    # Estilos
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='198754', end_color='198754', fill_type='solid')
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Headers
    headers = ['#', 'Nombre', 'Apellido', 'Teléfono', 'Dirección', 'Categoría', 'Ruta', 'Tipo Negocio', 'Límite Crédito']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
    
    # Datos
    for i, cliente in enumerate(clientes, 1):
        row = i + 1
        ws.cell(row=row, column=1, value=i).border = border
        ws.cell(row=row, column=2, value=cliente.nombre).border = border
        ws.cell(row=row, column=3, value=cliente.apellido).border = border
        ws.cell(row=row, column=4, value=cliente.telefono).border = border
        ws.cell(row=row, column=5, value=cliente.direccion[:50]).border = border
        ws.cell(row=row, column=6, value=cliente.get_categoria_display()).border = border
        ws.cell(row=row, column=7, value=cliente.ruta.nombre if cliente.ruta else '-').border = border
        ws.cell(row=row, column=8, value=cliente.tipo_negocio.nombre if cliente.tipo_negocio else '-').border = border
        limite_cell = ws.cell(row=row, column=9, value=float(cliente.limite_credito))
        limite_cell.number_format = '#,##0'
        limite_cell.border = border
    
    # Ajustar anchos
    for col in range(1, 10):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 15
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 20
    ws.column_dimensions['E'].width = 30
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=clientes_{datetime.now().strftime("%Y%m%d")}.xlsx'
    
    wb.save(response)
    return response


@login_required
def exportar_prestamos_excel(request):
    """Exportar préstamos a Excel"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Border, Side
    except ImportError:
        messages.error(request, 'La exportación a Excel no está disponible. Instale openpyxl.')
        return redirect('core:prestamo_list')
    
    estado = request.GET.get('estado', '')
    # prefetch_related('cuotas'): monto_pagado/monto_pendiente/cuotas_pagadas
    # hacen una query por préstamo si no está prefetched - con muchos
    # préstamos eso termina en timeout (Internal Server Error) en producción.
    prestamos = Prestamo.objects.select_related('cliente').prefetch_related('cuotas')
    if not es_usuario_admin(request.user):
        prestamos = prestamos.filter(cobrador=request.user)
    if estado:
        prestamos = prestamos.filter(estado=estado)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Préstamos"
    
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='0d6efd', end_color='0d6efd', fill_type='solid')
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    headers = ['#', 'Cliente', 'Dirección', 'Monto', 'Total', 'Pagado', 'Pendiente', 'Cuotas', 'Frecuencia', 'Estado', 'Fecha Inicio', 'Fecha Finalización']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
    
    for i, p in enumerate(prestamos, 1):
        row = i + 1
        ws.cell(row=row, column=1, value=i).border = border
        ws.cell(row=row, column=2, value=p.cliente.nombre_completo).border = border
        ws.cell(row=row, column=3, value=p.cliente.direccion or '-').border = border
        monto_cell = ws.cell(row=row, column=4, value=float(p.monto_solicitado))
        monto_cell.number_format = '#,##0'
        monto_cell.border = border
        total_cell = ws.cell(row=row, column=5, value=float(p.monto_total_a_pagar))
        total_cell.number_format = '#,##0'
        total_cell.border = border
        pagado_cell = ws.cell(row=row, column=6, value=float(p.monto_pagado))
        pagado_cell.number_format = '#,##0'
        pagado_cell.border = border
        pend_cell = ws.cell(row=row, column=7, value=float(p.monto_pendiente))
        pend_cell.number_format = '#,##0'
        pend_cell.border = border
        ws.cell(row=row, column=8, value=f'{p.cuotas_pagadas}/{p.cuotas_pactadas}').border = border
        ws.cell(row=row, column=9, value=p.get_frecuencia_display()).border = border
        ws.cell(row=row, column=10, value=p.get_estado_display()).border = border
        ws.cell(row=row, column=11, value=p.fecha_inicio.strftime('%d/%m/%Y')).border = border
        ws.cell(row=row, column=12, value=p.fecha_finalizacion.strftime('%d/%m/%Y') if p.fecha_finalizacion else '-').border = border
    
    for col in range(1, 13):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 15
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 30
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=prestamos_{datetime.now().strftime("%Y%m%d")}.xlsx'
    
    wb.save(response)
    return response


# ==================== NOTIFICACIONES ====================

class NotificacionListView(LoginRequiredMixin, ListView):
    """Vista de notificaciones del usuario"""
    model = Notificacion
    template_name = 'core/notificacion_list.html'
    context_object_name = 'notificaciones'
    paginate_by = 20
    
    def get_queryset(self):
        qs = Notificacion.objects.filter(
            Q(usuario=self.request.user) | Q(usuario__isnull=True)
        )
        
        # Filtros
        solo_no_leidas = self.request.GET.get('no_leidas', '')
        tipo = self.request.GET.get('tipo', '')
        
        if solo_no_leidas:
            qs = qs.filter(leida=False)
        if tipo:
            qs = qs.filter(tipo=tipo)
        
        return qs.order_by('-fecha_creacion')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tipos_notificacion'] = Notificacion.TipoNotificacion.choices
        context['no_leidas_count'] = Notificacion.objects.filter(
            Q(usuario=self.request.user) | Q(usuario__isnull=True),
            leida=False
        ).count()
        return context


@login_required
def marcar_notificacion_leida(request, pk):
    """Marcar notificación como leída via AJAX"""
    notificacion = get_object_or_404(
        Notificacion,
        pk=pk,
    )
    # Solo el destinatario o notificaciones globales (usuario=null)
    if notificacion.usuario is not None and notificacion.usuario != request.user:
        return JsonResponse({'success': False, 'message': 'Sin permiso'}, status=403)
    notificacion.marcar_como_leida()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('core:notificacion_list')


@login_required
def marcar_todas_leidas(request):
    """Marcar todas las notificaciones como leídas"""
    Notificacion.objects.filter(
        Q(usuario=request.user) | Q(usuario__isnull=True),
        leida=False
    ).update(leida=True, fecha_lectura=timezone.now())
    
    messages.success(request, 'Todas las notificaciones marcadas como leídas.')
    return redirect('core:notificacion_list')


@login_required
def obtener_notificaciones(request):
    """API para obtener notificaciones no leídas (para actualización en tiempo real)"""
    notificaciones = Notificacion.objects.filter(
        Q(usuario=request.user) | Q(usuario__isnull=True),
        leida=False
    ).order_by('-fecha_creacion')[:5]
    
    data = {
        'count': notificaciones.count(),
        'notificaciones': [
            {
                'id': n.pk,
                'titulo': n.titulo,
                'mensaje': n.mensaje[:100],
                'tipo': n.tipo,
                'prioridad': n.prioridad,
                'fecha': n.fecha_creacion.strftime('%d/%m %H:%M'),
                'enlace': n.enlace
            }
            for n in notificaciones
        ]
    }
    return JsonResponse(data)


# ==================== AUDITORÍA ====================

class AuditoriaListView(LoginRequiredMixin, ListView):
    """Vista de registros de auditoría"""
    model = RegistroAuditoria
    template_name = 'core/auditoria_list.html'
    context_object_name = 'registros'
    paginate_by = 50
    
    def dispatch(self, request, *args, **kwargs):
        if not es_usuario_admin(request.user):
            messages.error(request, 'No tienes permiso para ver el historial de auditoría.')
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        qs = super().get_queryset()
        
        # Filtros
        usuario = self.request.GET.get('usuario', '')
        tipo_accion = self.request.GET.get('tipo_accion', '')
        tipo_modelo = self.request.GET.get('tipo_modelo', '')
        fecha_desde = self.request.GET.get('fecha_desde', '')
        fecha_hasta = self.request.GET.get('fecha_hasta', '')
        
        if usuario:
            qs = qs.filter(usuario_id=usuario)
        if tipo_accion:
            qs = qs.filter(tipo_accion=tipo_accion)
        if tipo_modelo:
            qs = qs.filter(tipo_modelo=tipo_modelo)
        if fecha_desde:
            qs = qs.filter(fecha_hora__date__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_hora__date__lte=fecha_hasta)
        
        return qs.select_related('usuario')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Excluir superusuarios del filtro de usuarios (no visibles para admins)
        if not self.request.user.is_superuser:
            context['usuarios'] = User.objects.exclude(is_superuser=True)
        else:
            context['usuarios'] = User.objects.all()
        context['tipos_accion'] = RegistroAuditoria.TipoAccion.choices
        context['tipos_modelo'] = RegistroAuditoria.TipoModelo.choices
        return context


# ==================== RESPALDOS ====================

@login_required
def crear_respaldo(request):
    """Crear respaldo manual de la base de datos"""
    if not es_superadmin(request.user):
        messages.error(request, 'Solo los desarrolladores pueden crear respaldos.')
        return redirect('core:dashboard')
    
    config, _ = ConfiguracionRespaldo.objects.get_or_create(
        defaults={'nombre': 'Respaldo Automático'}
    )
    exito, backup_name, error = config.ejecutar_respaldo()

    if exito:
        RegistroAuditoria.registrar(
            usuario=request.user,
            tipo_accion='RS',
            tipo_modelo='SI',
            descripcion=f'Respaldo manual creado: {backup_name}',
            ip_address=get_client_ip(request)
        )
        messages.success(request, f'Respaldo creado exitosamente: {backup_name}')
    else:
        messages.error(request, f'Error al crear respaldo: {error}')

    return redirect('core:reporte_general')


@login_required
def descargar_respaldo(request, nombre):
    """Descargar un respaldo específico"""
    if not es_superadmin(request.user):
        messages.error(request, 'Solo los desarrolladores pueden descargar respaldos.')
        return redirect('core:dashboard')
    
    from django.conf import settings

    nombre = os.path.basename(nombre)  # evita path traversal (../../)
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    backup_path = os.path.join(backup_dir, nombre)

    if os.path.exists(backup_path) and nombre.startswith('backup_'):
        with open(backup_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename={nombre}'
            return response
    
    messages.error(request, 'El archivo de respaldo no existe.')
    return redirect('core:reporte_general')


class WhatsAppConexionView(LoginRequiredMixin, TemplateView):
    """
    Pantalla para vincular el número de WhatsApp personal (vía QR) que se
    usa para los mensajes automáticos. Solo admin: es una decisión de
    infraestructura, no algo que cada cobrador deba poder tocar.
    """
    template_name = 'core/whatsapp_conexion.html'

    def dispatch(self, request, *args, **kwargs):
        if not es_usuario_admin(request.user):
            messages.error(request, 'Solo un administrador puede gestionar la conexión de WhatsApp.')
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bridge_configurado'] = whatsapp_bridge.bridge_configurado()
        return context


@login_required
def whatsapp_estado(request):
    """Proxy AJAX del /status del bridge — el frontend nunca ve la URL/secreto del bridge directamente."""
    if not es_usuario_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Solo un administrador puede ver esto'}, status=403)

    if not whatsapp_bridge.bridge_configurado():
        return JsonResponse({'success': False, 'message': 'El bridge de WhatsApp no está configurado todavía'}, status=503)

    try:
        estado = whatsapp_bridge.obtener_estado()
    except whatsapp_bridge.WhatsAppBridgeError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=502)

    return JsonResponse({'success': True, 'data': estado})


@login_required
def whatsapp_qr(request):
    """Proxy AJAX del /qr del bridge."""
    if not es_usuario_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Solo un administrador puede ver esto'}, status=403)

    if not whatsapp_bridge.bridge_configurado():
        return JsonResponse({'success': False, 'message': 'El bridge de WhatsApp no está configurado todavía'}, status=503)

    try:
        data = whatsapp_bridge.obtener_qr()
    except whatsapp_bridge.WhatsAppBridgeError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=502)

    return JsonResponse({'success': True, 'data': data})


@login_required
def whatsapp_desconectar(request):
    """Proxy AJAX del /disconnect del bridge."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    if not es_usuario_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Solo un administrador puede hacer esto'}, status=403)

    try:
        whatsapp_bridge.desconectar()
    except whatsapp_bridge.WhatsAppBridgeError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=502)

    return JsonResponse({'success': True, 'message': 'WhatsApp desvinculado'})


class MensajesAutomaticosConfigView(LoginRequiredMixin, TemplateView):
    """
    Pantalla de mensajes automáticos por WhatsApp (Fase 4): confirmación
    antes de activar por primera vez, y configuración completa (días, hora,
    días de semana, texto) de los 3 mensajes una vez activada.
    Solo admin: decide qué se le manda a los clientes en nombre del negocio.
    """
    template_name = 'core/mensajes_automaticos.html'

    def dispatch(self, request, *args, **kwargs):
        if not es_usuario_admin(request.user):
            messages.error(request, 'Solo un administrador puede configurar los mensajes automáticos.')
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['config'] = ConfiguracionMensajesAutomaticos.obtener()
        context['dias_semana_codigos'] = DIAS_SEMANA_CODIGOS
        return context


@login_required
def activar_mensajes_automaticos(request):
    """Confirma y prende el interruptor general. Solo admin."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    if not es_usuario_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Solo un administrador puede hacer esto'}, status=403)

    config = ConfiguracionMensajesAutomaticos.obtener()
    config.activo = True
    if not config.confirmado_en:
        config.confirmado_en = timezone.now()
    config.save(update_fields=['activo', 'confirmado_en'])

    return JsonResponse({'success': True, 'message': 'Mensajes automáticos activados.'})


@login_required
def desactivar_mensajes_automaticos(request):
    """Apaga el interruptor general (sin borrar la configuración ni el historial). Solo admin."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    if not es_usuario_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Solo un administrador puede hacer esto'}, status=403)

    config = ConfiguracionMensajesAutomaticos.obtener()
    config.activo = False
    config.save(update_fields=['activo'])

    return JsonResponse({'success': True, 'message': 'Mensajes automáticos desactivados.'})


@login_required
def guardar_configuracion_mensajes(request):
    """Guarda días/hora/días de semana/plantilla de los 3 mensajes. Solo admin."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    if not es_usuario_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Solo un administrador puede hacer esto'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'JSON inválido'}, status=400)

    config = ConfiguracionMensajesAutomaticos.obtener()

    config.alias_pago = data.get('alias_pago', config.alias_pago)

    try:
        dias_antes = int(data.get('recordatorio_dias_antes', config.recordatorio_dias_antes))
        dias_despues = int(data.get('aviso_mora_dias_despues', config.aviso_mora_dias_despues))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Los días deben ser números'}, status=400)

    if not (0 <= dias_antes <= 10):
        return JsonResponse({'success': False, 'message': 'Días antes del vencimiento: entre 0 y 10'}, status=400)
    if not (1 <= dias_despues <= 30):
        return JsonResponse({'success': False, 'message': 'Días después del vencimiento: entre 1 y 30'}, status=400)

    def dias_semana_validos(valor, default):
        if not isinstance(valor, str):
            return default
        limpio = ''.join(c for c in valor.upper() if c in DIAS_SEMANA_CODIGOS)
        return limpio

    config.recordatorio_activo = bool(data.get('recordatorio_activo', config.recordatorio_activo))
    config.recordatorio_dias_antes = dias_antes
    config.recordatorio_hora = data.get('recordatorio_hora', config.recordatorio_hora)
    config.recordatorio_dias_semana = dias_semana_validos(data.get('recordatorio_dias_semana'), config.recordatorio_dias_semana)
    config.recordatorio_plantilla = data.get('recordatorio_plantilla', config.recordatorio_plantilla)

    config.aviso_dia_activo = bool(data.get('aviso_dia_activo', config.aviso_dia_activo))
    config.aviso_dia_hora = data.get('aviso_dia_hora', config.aviso_dia_hora)
    config.aviso_dia_dias_semana = dias_semana_validos(data.get('aviso_dia_dias_semana'), config.aviso_dia_dias_semana)
    config.aviso_dia_plantilla = data.get('aviso_dia_plantilla', config.aviso_dia_plantilla)

    config.aviso_mora_activo = bool(data.get('aviso_mora_activo', config.aviso_mora_activo))
    config.aviso_mora_dias_despues = dias_despues
    config.aviso_mora_hora = data.get('aviso_mora_hora', config.aviso_mora_hora)
    config.aviso_mora_dias_semana = dias_semana_validos(data.get('aviso_mora_dias_semana'), config.aviso_mora_dias_semana)
    config.aviso_mora_plantilla = data.get('aviso_mora_plantilla', config.aviso_mora_plantilla)

    config.save()

    return JsonResponse({'success': True, 'message': 'Configuración guardada.'})


class RespaldoListView(LoginRequiredMixin, TemplateView):
    """Vista de listado de respaldos disponibles"""
    template_name = 'core/respaldo_list.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not es_superadmin(request.user):
            messages.error(request, 'Solo los desarrolladores pueden ver los respaldos.')
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        from django.conf import settings
        
        context = super().get_context_data(**kwargs)
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        
        backups = []
        if os.path.exists(backup_dir):
            for f in sorted(os.listdir(backup_dir), reverse=True):
                if f.startswith('backup_'):
                    path = os.path.join(backup_dir, f)
                    size = os.path.getsize(path)
                    backups.append({
                        'nombre': f,
                        'tamano': f'{size / 1024 / 1024:.2f} MB',
                        'fecha': datetime.fromtimestamp(os.path.getctime(path))
                    })
        
        context['backups'] = backups
        context['config'] = ConfiguracionRespaldo.objects.first()
        return context


# ==================== REPORTES AUTOMÁTICOS (C1-C3) ====================

class ReportesAutomaticosListView(LoginRequiredMixin, TemplateView):
    """
    Lista los reportes que generan solos los Cron Jobs (cierre de caja diario,
    morosidad semanal, planillas de ruta por cobrador) para descargarlos desde
    el panel. Por ahora es la única forma de acceder a ellos — todavía no se
    envían por WhatsApp/email.
    """
    template_name = 'core/reportes_automaticos.html'

    def dispatch(self, request, *args, **kwargs):
        if not es_usuario_admin(request.user):
            messages.error(request, 'Solo los administradores pueden ver los reportes automáticos.')
            return redirect('core:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from django.conf import settings

        context = super().get_context_data(**kwargs)
        reportes_dir = os.path.join(settings.BASE_DIR, 'reportes')

        reportes = []
        if os.path.exists(reportes_dir):
            for f in sorted(os.listdir(reportes_dir), reverse=True):
                if not f.endswith('.xlsx'):
                    continue
                if f.startswith('cierre_'):
                    tipo = 'Cierre de caja'
                elif f.startswith('morosidad_'):
                    tipo = 'Morosidad semanal'
                elif f.startswith('planilla_'):
                    tipo = 'Planilla de ruta'
                else:
                    tipo = 'Reporte'
                path = os.path.join(reportes_dir, f)
                size = os.path.getsize(path)
                reportes.append({
                    'nombre': f,
                    'tipo': tipo,
                    'tamano': f'{size / 1024:.0f} KB',
                    'fecha': datetime.fromtimestamp(os.path.getctime(path)),
                })

        context['reportes'] = reportes
        return context


@login_required
def descargar_reporte_automatico(request, nombre):
    """Descargar un reporte automático específico (cierre, morosidad o planilla)"""
    if not es_usuario_admin(request.user):
        messages.error(request, 'Solo los administradores pueden descargar reportes.')
        return redirect('core:dashboard')

    from django.conf import settings

    nombre = os.path.basename(nombre)  # evita path traversal (../../)
    reportes_dir = os.path.join(settings.BASE_DIR, 'reportes')
    reporte_path = os.path.join(reportes_dir, nombre)

    nombre_valido = nombre.startswith(('cierre_', 'morosidad_', 'planilla_')) and nombre.endswith('.xlsx')
    if nombre_valido and os.path.exists(reporte_path):
        with open(reporte_path, 'rb') as f:
            response = HttpResponse(
                f.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename={nombre}'
            return response

    messages.error(request, 'El reporte no existe.')
    return redirect('core:reportes_automaticos')


# ==================== UTILIDADES ====================

def get_client_ip(request):
    """Obtener la IP del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ==================== GENERAR NOTIFICACIONES AUTOMÁTICAS ====================

@login_required
def generar_notificaciones(request):
    """Generar notificaciones de cuotas vencidas y por vencer"""
    if not es_usuario_admin(request.user):
        return JsonResponse({'success': False, 'message': 'Sin permisos'}, status=403)
    
    Notificacion.notificar_cuotas_vencidas()
    Notificacion.notificar_cuotas_por_vencer()

    return JsonResponse({'success': True, 'message': 'Notificaciones generadas'})


# ==================== ESTADO PÚBLICO DE PRÉSTAMO ====================

import uuid

def estado_prestamo_publico(request, token):
    """Vista pública (sin auth) que muestra el estado de un préstamo vía token UUID"""
    try:
        token_uuid = uuid.UUID(str(token))
    except (ValueError, AttributeError):
        from django.http import Http404
        raise Http404

    prestamo = get_object_or_404(Prestamo, token_publico=token_uuid, token_activo=True)

    cuotas = prestamo.cuotas.all()
    hoy = fecha_local_hoy()

    # Próxima cuota pendiente
    proxima_cuota = cuotas.filter(
        estado__in=['PE', 'PC'],
        fecha_vencimiento__gte=hoy
    ).order_by('fecha_vencimiento').first()

    # Si no hay futuras, buscar la primera vencida sin pagar
    if not proxima_cuota:
        proxima_cuota = cuotas.filter(
            estado__in=['PE', 'PC']
        ).order_by('fecha_vencimiento').first()

    # Último pago realizado
    ultimo_pago = cuotas.filter(
        estado='PA',
        fecha_pago_real__isnull=False
    ).order_by('-fecha_pago_real').first()

    # Mora automática desactivada: el cobrador la registra manualmente desde el lápiz.
    mora_pendiente = Decimal('0.00')

    # Cuotas vencidas sin pagar
    cuotas_vencidas = cuotas.filter(
        estado__in=['PE', 'PC'],
        fecha_vencimiento__lt=hoy
    ).count()

    context = {
        'prestamo': prestamo,
        'proxima_cuota': proxima_cuota,
        'ultimo_pago': ultimo_pago,
        'mora_pendiente': mora_pendiente,
        'cuotas_vencidas': cuotas_vencidas,
        'hoy': hoy,
    }

    return render(request, 'core/estado_publico.html', context)


@login_required
def regenerar_token_prestamo(request, pk):
    """Regenerar el token público de un préstamo (solo admin/cobrador dueño)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    try:
        if es_usuario_admin(request.user):
            prestamo = Prestamo.objects.get(pk=pk)
        else:
            prestamo = Prestamo.objects.get(pk=pk, cobrador=request.user)

        prestamo.token_publico = uuid.uuid4()
        prestamo.token_activo = True
        prestamo.save(update_fields=['token_publico', 'token_activo'])

        return JsonResponse({
            'success': True,
            'message': 'Link regenerado correctamente',
            'data': {'token': str(prestamo.token_publico)}
        })
    except Prestamo.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Préstamo no encontrado'}, status=404)


@login_required
def toggle_token_prestamo(request, pk):
    """Activar/desactivar el link público de un préstamo"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    try:
        if es_usuario_admin(request.user):
            prestamo = Prestamo.objects.get(pk=pk)
        else:
            prestamo = Prestamo.objects.get(pk=pk, cobrador=request.user)

        prestamo.token_activo = not prestamo.token_activo
        prestamo.save(update_fields=['token_activo'])

        estado = 'activado' if prestamo.token_activo else 'desactivado'
        return JsonResponse({
            'success': True,
            'message': f'Link {estado} correctamente',
            'data': {'activo': prestamo.token_activo}
        })
    except Prestamo.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Préstamo no encontrado'}, status=404)


# ==================== ESTADO PÚBLICO DE CLIENTE (todos sus créditos) ====================

def estado_cliente_publico(request, token):
    """Vista pública (sin auth) que muestra un resumen de todos los créditos de un cliente vía token UUID"""
    try:
        token_uuid = uuid.UUID(str(token))
    except (ValueError, AttributeError):
        from django.http import Http404
        raise Http404

    cliente = get_object_or_404(Cliente, token_publico=token_uuid, token_activo=True)

    prestamos = cliente.prestamos.order_by('-fecha_inicio')
    prestamos_activos = [p for p in prestamos if p.estado == 'AC']
    prestamos_historial = [p for p in prestamos if p.estado != 'AC']

    context = {
        'cliente': cliente,
        'prestamos_activos': prestamos_activos,
        'prestamos_historial': prestamos_historial,
        'hoy': fecha_local_hoy(),
    }

    return render(request, 'core/estado_cliente_publico.html', context)


@login_required
def regenerar_token_cliente(request, pk):
    """Regenerar el token público de un cliente (solo admin/cobrador dueño)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    try:
        if es_usuario_admin(request.user):
            cliente = Cliente.objects.get(pk=pk)
        else:
            cliente = Cliente.objects.get(pk=pk, usuario=request.user)

        cliente.token_publico = uuid.uuid4()
        cliente.token_activo = True
        cliente.save(update_fields=['token_publico', 'token_activo'])

        return JsonResponse({
            'success': True,
            'message': 'Link regenerado correctamente',
            'data': {'token': str(cliente.token_publico)}
        })
    except Cliente.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Cliente no encontrado'}, status=404)


@login_required
def toggle_token_cliente(request, pk):
    """Activar/desactivar el link público de un cliente"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    try:
        if es_usuario_admin(request.user):
            cliente = Cliente.objects.get(pk=pk)
        else:
            cliente = Cliente.objects.get(pk=pk, usuario=request.user)

        cliente.token_activo = not cliente.token_activo
        cliente.save(update_fields=['token_activo'])

        estado = 'activado' if cliente.token_activo else 'desactivado'
        return JsonResponse({
            'success': True,
            'message': f'Link {estado} correctamente',
            'data': {'activo': cliente.token_activo}
        })
    except Cliente.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Cliente no encontrado'}, status=404)


# ==================== NOTAS DE SEGUIMIENTO (recordatorios cortos por préstamo) ====================

def _prestamo_visible_o_404(pk, user):
    """Mismo criterio de permisos que el resto de acciones sobre un préstamo puntual."""
    if es_usuario_admin(user):
        return get_object_or_404(Prestamo, pk=pk)
    return get_object_or_404(Prestamo, pk=pk, cobrador=user)


def _nota_a_json(nota):
    return {
        'id': nota.pk,
        'texto': nota.texto,
        'creado_por': (nota.creado_por.get_full_name() or nota.creado_por.username) if nota.creado_por else '',
        'fecha_creacion': nota.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        'fecha_vencimiento': nota.fecha_vencimiento.strftime('%d/%m/%Y') if nota.fecha_vencimiento else None,
        'vigente': nota.vigente,
    }


@login_required
def crear_nota_prestamo(request, pk):
    """Crea una nota de seguimiento corta sobre un préstamo (AJAX)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    prestamo = _prestamo_visible_o_404(pk, request.user)

    texto = (request.POST.get('texto') or '').strip()
    if not texto:
        return JsonResponse({'success': False, 'message': 'Escribí una nota antes de guardar.'}, status=400)
    if len(texto) > 280:
        return JsonResponse({'success': False, 'message': 'La nota es muy larga (máximo 280 caracteres).'}, status=400)

    duracion = request.POST.get('duracion', NotaSeguimiento.Duracion.UNA_SEMANA)
    if duracion not in NotaSeguimiento.Duracion.values:
        duracion = NotaSeguimiento.Duracion.UNA_SEMANA

    fecha_vencimiento = NotaSeguimiento.calcular_vencimiento(duracion, prestamo)

    nota = NotaSeguimiento.objects.create(
        prestamo=prestamo,
        texto=texto,
        creado_por=request.user,
        fecha_vencimiento=fecha_vencimiento,
    )

    return JsonResponse({
        'success': True,
        'message': 'Nota guardada.',
        'data': _nota_a_json(nota),
    })


@login_required
def eliminar_nota_prestamo(request, pk):
    """Borra una nota de seguimiento (el cobrador la resuelve/descarta a mano)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    if es_usuario_admin(request.user):
        nota = get_object_or_404(NotaSeguimiento, pk=pk)
    else:
        nota = get_object_or_404(NotaSeguimiento, pk=pk, prestamo__cobrador=request.user)

    nota.delete()
    return JsonResponse({'success': True, 'message': 'Nota eliminada.'})


# ============== TAREAS PENDIENTES (widget flotante) ==============

def _tarea_a_json(tarea):
    return {
        'id': tarea.pk,
        'texto': tarea.texto,
        'completada': tarea.completada,
        'prioridad': tarea.prioridad,
        'fecha_vencimiento': tarea.fecha_vencimiento.strftime('%Y-%m-%d') if tarea.fecha_vencimiento else None,
        'vencida': tarea.vencida,
        'orden': tarea.orden,
        'vinculo': tarea.vinculo,
    }


def _tareas_visibles_qs(user):
    """Clientes/préstamos/cuotas que un usuario puede agendar en sus tareas: admin ve todo, cobrador solo lo suyo."""
    if es_usuario_admin(user):
        return Cliente.objects.all(), Prestamo.objects.all(), Cuota.objects.all()
    return (
        Cliente.objects.filter(usuario=user),
        Prestamo.objects.filter(cobrador=user),
        Cuota.objects.filter(prestamo__cobrador=user),
    )


def _resolver_vinculo(request, user):
    """
    Lee tipo_vinculo/vinculo_id del POST y devuelve (cliente, prestamo, cuota, error).
    tipo_vinculo vacío o ausente = sin vínculo (los tres None). Valida que el
    registro elegido sea visible para el usuario (mismo criterio que el resto
    de la app: admin ve todo, cobrador solo lo suyo).
    """
    tipo = (request.POST.get('tipo_vinculo') or '').strip()
    vinculo_id = request.POST.get('vinculo_id')

    if not tipo or not vinculo_id:
        return None, None, None, None

    clientes_qs, prestamos_qs, cuotas_qs = _tareas_visibles_qs(user)

    if tipo == 'cliente':
        cliente = clientes_qs.filter(pk=vinculo_id).first()
        if not cliente:
            return None, None, None, 'Cliente no encontrado.'
        return cliente, None, None, None
    if tipo == 'prestamo':
        prestamo = prestamos_qs.filter(pk=vinculo_id).first()
        if not prestamo:
            return None, None, None, 'Préstamo no encontrado.'
        return None, prestamo, None, None
    if tipo == 'cuota':
        cuota = cuotas_qs.filter(pk=vinculo_id).select_related('prestamo').first()
        if not cuota:
            return None, None, None, 'Cuota no encontrada.'
        return None, None, cuota, None

    return None, None, None, 'Tipo de vínculo inválido.'


@login_required
def listar_tareas(request):
    """Tareas pendientes del usuario logueado (widget flotante, visible en toda la app)."""
    tareas = TareaPendiente.objects.filter(usuario=request.user).select_related(
        'cliente', 'prestamo', 'cuota', 'cuota__prestamo', 'cuota__prestamo__cliente', 'prestamo__cliente'
    )
    return JsonResponse({
        'success': True,
        'data': [_tarea_a_json(t) for t in tareas],
    })


@login_required
def crear_tarea(request):
    """Crea una tarea pendiente (AJAX)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    texto = (request.POST.get('texto') or '').strip()
    if not texto:
        return JsonResponse({'success': False, 'message': 'Escribí una tarea antes de guardar.'}, status=400)
    if len(texto) > 280:
        return JsonResponse({'success': False, 'message': 'La tarea es muy larga (máximo 280 caracteres).'}, status=400)

    prioridad = request.POST.get('prioridad', TareaPendiente.Prioridad.MEDIA)
    if prioridad not in TareaPendiente.Prioridad.values:
        prioridad = TareaPendiente.Prioridad.MEDIA

    fecha_vencimiento = parse_date(request.POST.get('fecha_vencimiento') or '')

    cliente, prestamo, cuota, error = _resolver_vinculo(request, request.user)
    if error:
        return JsonResponse({'success': False, 'message': error}, status=400)

    primer_orden = TareaPendiente.objects.filter(usuario=request.user).count()

    tarea = TareaPendiente.objects.create(
        usuario=request.user, texto=texto, prioridad=prioridad,
        fecha_vencimiento=fecha_vencimiento, orden=primer_orden,
        cliente=cliente, prestamo=prestamo, cuota=cuota,
    )
    return JsonResponse({'success': True, 'data': _tarea_a_json(tarea)})


@login_required
def editar_tarea(request, pk):
    """Edita texto/prioridad/fecha/vínculo de una tarea existente (AJAX)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    tarea = get_object_or_404(TareaPendiente, pk=pk, usuario=request.user)

    texto = (request.POST.get('texto') or '').strip()
    if not texto:
        return JsonResponse({'success': False, 'message': 'Escribí una tarea antes de guardar.'}, status=400)
    if len(texto) > 280:
        return JsonResponse({'success': False, 'message': 'La tarea es muy larga (máximo 280 caracteres).'}, status=400)

    prioridad = request.POST.get('prioridad', tarea.prioridad)
    if prioridad not in TareaPendiente.Prioridad.values:
        prioridad = tarea.prioridad

    cliente, prestamo, cuota, error = _resolver_vinculo(request, request.user)
    if error:
        return JsonResponse({'success': False, 'message': error}, status=400)

    tarea.texto = texto
    tarea.prioridad = prioridad
    tarea.fecha_vencimiento = parse_date(request.POST.get('fecha_vencimiento') or '')
    tarea.cliente = cliente
    tarea.prestamo = prestamo
    tarea.cuota = cuota
    tarea.save()

    return JsonResponse({'success': True, 'data': _tarea_a_json(tarea)})


@login_required
def toggle_tarea(request, pk):
    """Marca/desmarca una tarea como completada (AJAX)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    tarea = get_object_or_404(TareaPendiente, pk=pk, usuario=request.user)
    tarea.completada = not tarea.completada
    tarea.save(update_fields=['completada'])
    return JsonResponse({'success': True, 'data': _tarea_a_json(tarea)})


@login_required
def eliminar_tarea(request, pk):
    """Elimina una tarea pendiente (AJAX)."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    tarea = get_object_or_404(TareaPendiente, pk=pk, usuario=request.user)
    tarea.delete()
    return JsonResponse({'success': True, 'message': 'Tarea eliminada.'})


@login_required
def reordenar_tareas(request):
    """
    Persiste el nuevo orden tras arrastrar tarjetas en el widget. Recibe
    `orden` = lista de ids en el orden deseado (JSON). Ids que no son del
    usuario logueado se ignoran silenciosamente (no se puede reordenar lo
    ajeno, pero tampoco es motivo para romper el pedido de quien sí es dueño).
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    try:
        orden_ids = json.loads(request.body).get('orden', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'Datos inválidos'}, status=400)

    propias = set(TareaPendiente.objects.filter(usuario=request.user).values_list('pk', flat=True))

    for posicion, tarea_id in enumerate(orden_ids):
        if tarea_id in propias:
            TareaPendiente.objects.filter(pk=tarea_id).update(orden=posicion)

    return JsonResponse({'success': True})


@login_required
def buscar_vinculo_tarea(request):
    """Autocompletado para agendar un cliente/préstamo/cuota en una tarea (AJAX)."""
    tipo = request.GET.get('tipo', '')
    q = request.GET.get('q', '').strip()
    if len(q) < 2 or tipo not in ('cliente', 'prestamo', 'cuota'):
        return JsonResponse({'success': True, 'data': []})

    clientes_qs, prestamos_qs, cuotas_qs = _tareas_visibles_qs(request.user)
    resultados = []

    if tipo == 'cliente':
        for c in clientes_qs.filter(Q(nombre__icontains=q) | Q(apellido__icontains=q))[:8]:
            resultados.append({'id': c.pk, 'label': c.nombre_completo})
    elif tipo == 'prestamo':
        qs = prestamos_qs.filter(
            Q(cliente__nombre__icontains=q) | Q(cliente__apellido__icontains=q)
        ).select_related('cliente')[:8]
        for p in qs:
            resultados.append({'id': p.pk, 'label': f'#{p.pk} - {p.cliente.nombre_completo}'})
    elif tipo == 'cuota':
        qs = cuotas_qs.filter(
            Q(prestamo__cliente__nombre__icontains=q) | Q(prestamo__cliente__apellido__icontains=q)
        ).select_related('prestamo', 'prestamo__cliente').order_by('prestamo__cliente__nombre', 'numero_cuota')[:8]
        for c in qs:
            resultados.append({
                'id': c.pk,
                'label': f'{c.prestamo.cliente.nombre_completo} - Cuota {c.numero_cuota}/{c.prestamo.cuotas_pactadas}',
            })

    return JsonResponse({'success': True, 'data': resultados})
