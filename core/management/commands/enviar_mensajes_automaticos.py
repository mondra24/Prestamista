"""
Job programado (Railway Cron Job): los 3 mensajes automáticos configurables
por WhatsApp (número personal, vía bridge — Fase 4 del plan mostrado en la
demo). Pensado para correr una vez por día.

No manda nada hasta que:
1. ConfiguracionMensajesAutomaticos.activo esté en True (se prende una sola
   vez, después de la confirmación explícita en la pantalla de mensajes
   automáticos), y
2. El bridge de WhatsApp (whatsapp-bridge/) esté configurado y conectado.

Cada uno de los 3 mensajes tiene su propio interruptor, día de la semana y
plantilla configurables, independientes entre sí.

Pausa entre envíos: mandar todos los mensajes del día en ráfaga (sin espera)
es el patrón que más fácil detectan los sistemas anti-spam de WhatsApp en un
número personal no verificado (Baileys). Por eso cada envío exitoso o
fallido espera un tiempo aleatorio antes de seguir con el próximo — ver
PAUSA_MIN_SEGUNDOS / PAUSA_MAX_SEGUNDOS.
"""
import random
import time
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import Cuota, ConfiguracionMensajesAutomaticos, EnvioWhatsApp, Notificacion, PerfilUsuario, fecha_local_hoy

PAUSA_MIN_SEGUNDOS = 20
PAUSA_MAX_SEGUNDOS = 60
from core import whatsapp_bridge


class Command(BaseCommand):
    help = 'Envía los 3 mensajes automáticos configurables (recordatorio, aviso del día, aviso de mora) por WhatsApp'

    def handle(self, *args, **options):
        config = ConfiguracionMensajesAutomaticos.obtener()

        if not config.activo:
            self.stdout.write('Mensajes automáticos desactivados en configuración, no se envía nada.')
            return

        if not whatsapp_bridge.bridge_configurado():
            self.stdout.write(self.style.WARNING(
                'ConfiguracionMensajesAutomaticos.activo=True pero el bridge de WhatsApp no está '
                'configurado (WHATSAPP_BRIDGE_URL / WHATSAPP_BRIDGE_SECRET). No se envía nada.'
            ))
            return

        try:
            estado_bridge = whatsapp_bridge.obtener_estado()
        except whatsapp_bridge.WhatsAppBridgeError as e:
            self.stdout.write(self.style.WARNING(f'No se pudo consultar el bridge de WhatsApp: {e}. No se envía nada.'))
            return

        if not estado_bridge.get('connected'):
            self.stdout.write(self.style.WARNING('El bridge de WhatsApp no está conectado. No se envía nada.'))
            return

        hoy = fecha_local_hoy()
        enviados = 0
        fallidos = 0

        if config.recordatorio_activo and ConfiguracionMensajesAutomaticos.dia_activo(config.recordatorio_dias_semana, hoy):
            e, f = self._procesar(
                fecha=hoy + timedelta(days=config.recordatorio_dias_antes),
                tipo=EnvioWhatsApp.Tipo.RECORDATORIO_PREVENTIVO,
                plantilla=config.recordatorio_plantilla,
                config=config,
            )
            enviados += e
            fallidos += f

        if config.aviso_dia_activo and ConfiguracionMensajesAutomaticos.dia_activo(config.aviso_dia_dias_semana, hoy):
            e, f = self._procesar(
                fecha=hoy,
                tipo=EnvioWhatsApp.Tipo.AVISO_DIA,
                plantilla=config.aviso_dia_plantilla,
                config=config,
            )
            enviados += e
            fallidos += f

        if config.aviso_mora_activo and ConfiguracionMensajesAutomaticos.dia_activo(config.aviso_mora_dias_semana, hoy):
            e, f = self._procesar(
                fecha=hoy - timedelta(days=config.aviso_mora_dias_despues),
                tipo=EnvioWhatsApp.Tipo.AVISO_MORA,
                plantilla=config.aviso_mora_plantilla,
                config=config,
            )
            enviados += e
            fallidos += f

        self.stdout.write(self.style.SUCCESS(f'Mensajes automáticos enviados: {enviados}. Fallidos: {fallidos}.'))

        if fallidos:
            administradores = User.objects.filter(
                Q(is_superuser=True) | Q(perfil__rol=PerfilUsuario.Rol.ADMIN)
            ).distinct()
            for admin in administradores:
                Notificacion.crear_notificacion(
                    tipo='AS',
                    titulo=f'Fallaron {fallidos} mensaje(s) automático(s) de WhatsApp',
                    mensaje='De los mensajes automáticos de hoy, algunos no se pudieron enviar. '
                            'Revisá el registro de envíos en el Django Admin (Envíos de WhatsApp) para el detalle.',
                    usuario=admin,
                    prioridad='ME',
                    enlace='/admin/core/enviowhatsapp/'
                )

    def _procesar(self, fecha, tipo, plantilla, config):
        """Manda un tipo de mensaje a todas las cuotas que vencen en `fecha`. Retorna (enviados, fallidos)."""
        cuotas = Cuota.objects.filter(
            fecha_vencimiento=fecha,
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).select_related('prestamo', 'prestamo__cliente')

        enviados = 0
        fallidos = 0
        for cuota in cuotas:
            if EnvioWhatsApp.ya_enviado_hoy(cuota, tipo):
                continue

            cliente = cuota.prestamo.cliente
            texto = config.renderizar_plantilla(plantilla, cuota)
            try:
                message_id = whatsapp_bridge.enviar_mensaje(cliente.telefono, texto)
                EnvioWhatsApp.objects.create(
                    cliente=cliente, cuota=cuota, tipo=tipo, canal=EnvioWhatsApp.Canal.PERSONAL,
                    exitoso=True, message_id=message_id
                )
                enviados += 1
            except whatsapp_bridge.WhatsAppBridgeError as e:
                EnvioWhatsApp.objects.create(
                    cliente=cliente, cuota=cuota, tipo=tipo, canal=EnvioWhatsApp.Canal.PERSONAL,
                    exitoso=False, error=str(e)
                )
                fallidos += 1

            time.sleep(random.uniform(PAUSA_MIN_SEGUNDOS, PAUSA_MAX_SEGUNDOS))

        return enviados, fallidos
