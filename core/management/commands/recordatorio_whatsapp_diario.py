"""
Job programado (Railway Cron Job): recordatorio diario de WhatsApp (B1),
pensado para correr a las 10:00 ART. Cada cliente con una cuota que vence
hoy o que ya está vencida recibe un mensaje con el monto y la fecha.

No hace nada (ni gasta conversaciones de Meta) hasta que:
1. ConfiguracionWhatsApp.activo esté en True (Django Admin), y
2. Existan las variables de entorno WHATSAPP_ACCESS_TOKEN y
   WHATSAPP_PHONE_NUMBER_ID (ver core/whatsapp.py).
Ambas cosas solo tienen sentido una vez completada el alta del negocio en
Meta y aprobada la plantilla del recordatorio.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Cuota, ConfiguracionWhatsApp, EnvioWhatsApp, Notificacion, PerfilUsuario, fecha_local_hoy
from core.templatetags.currency_filters import formato_ars
from core.whatsapp import enviar_plantilla_whatsapp, whatsapp_configurado, WhatsAppError


class Command(BaseCommand):
    help = 'Envía el recordatorio diario de WhatsApp a clientes con cuota vencida o que vence hoy'

    def handle(self, *args, **options):
        if not ConfiguracionWhatsApp.esta_activo():
            self.stdout.write('WhatsApp desactivado en configuración, no se envía nada.')
            return

        if not whatsapp_configurado():
            self.stdout.write(self.style.WARNING(
                'ConfiguracionWhatsApp.activo=True pero faltan las variables de entorno de Meta '
                '(WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID). No se envía nada.'
            ))
            return

        config = ConfiguracionWhatsApp.obtener()
        hoy = fecha_local_hoy()

        cuotas = Cuota.objects.filter(
            fecha_vencimiento__lte=hoy,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).select_related('prestamo', 'prestamo__cliente')

        enviados = 0
        fallidos = 0
        for cuota in cuotas:
            if EnvioWhatsApp.ya_enviado_hoy(cuota, EnvioWhatsApp.Tipo.RECORDATORIO):
                continue

            cliente = cuota.prestamo.cliente
            try:
                message_id = enviar_plantilla_whatsapp(
                    telefono=cliente.telefono,
                    nombre_plantilla=config.template_recordatorio,
                    parametros=[formato_ars(cuota.monto_restante), cuota.fecha_vencimiento.strftime('%d/%m/%Y')],
                    idioma=config.idioma_plantillas
                )
                EnvioWhatsApp.objects.create(
                    cliente=cliente, cuota=cuota, tipo=EnvioWhatsApp.Tipo.RECORDATORIO,
                    exitoso=True, message_id=message_id
                )
                enviados += 1
            except WhatsAppError as e:
                EnvioWhatsApp.objects.create(
                    cliente=cliente, cuota=cuota, tipo=EnvioWhatsApp.Tipo.RECORDATORIO,
                    exitoso=False, error=str(e)
                )
                fallidos += 1

        self.stdout.write(self.style.SUCCESS(f'Recordatorios enviados: {enviados}. Fallidos: {fallidos}.'))

        if fallidos:
            administradores = User.objects.filter(
                Q(is_superuser=True) | Q(perfil__rol=PerfilUsuario.Rol.ADMIN)
            ).distinct()
            for admin in administradores:
                Notificacion.crear_notificacion(
                    tipo='AS',
                    titulo=f'Fallaron {fallidos} recordatorio(s) de WhatsApp',
                    mensaje=f'De los recordatorios de hoy, {fallidos} no se pudieron enviar. '
                            f'Revisá el registro de envíos en el Django Admin (Envíos de WhatsApp) para el detalle.',
                    usuario=admin,
                    prioridad='ME',
                    enlace='/admin/core/enviowhatsapp/'
                )
