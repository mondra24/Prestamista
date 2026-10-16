"""
Job programado (Railway Cron Job): los 3 mensajes automáticos configurables
por WhatsApp (número personal, vía bridge — Fase 4 del plan mostrado en la
demo). Pensado para correr CADA HORA.

Correr seguido es lo que hace que una desvinculación de WhatsApp no pierda
los mensajes del día: cada corrida manda solo lo que todavía falta
(EnvioWhatsApp.ya_enviado_hoy evita repetir), así que cuando Thomas vuelve
a escanear el QR, en la próxima corrida se envía lo que quedó pendiente.

No manda nada hasta que:
1. ConfiguracionMensajesAutomaticos.activo esté en True (se prende una sola
   vez, después de la confirmación explícita en la pantalla de mensajes
   automáticos), y
2. El bridge de WhatsApp (whatsapp-bridge/) esté configurado y conectado.

Cada uno de los 3 mensajes tiene su propio interruptor, día de la semana,
hora y plantilla configurables, independientes entre sí. Un mensaje se
manda desde su hora configurada (y no más tarde de HORA_LIMITE_DEFAULT, para
no avisarle a un cliente de noche si el QR se re-vinculó tarde).

Si hay mensajes por mandar y WhatsApp no está conectado, se avisa a los
administradores (una sola vez por día) para que re-escaneen el QR.

Pausa entre envíos: mandar todos los mensajes del día en ráfaga (sin espera)
es el patrón que más fácil detectan los sistemas anti-spam de WhatsApp en un
número personal no verificado (Baileys). Por eso cada envío exitoso o
fallido espera un tiempo aleatorio antes de seguir con el próximo — ver
PAUSA_MIN_SEGUNDOS / PAUSA_MAX_SEGUNDOS.

Opción --simular: no habla con el bridge para enviar ni escribe nada, solo
muestra qué mensajes mandaría en este momento (sirve para probar en
producción sin mandarle nada a nadie).
"""
import random
import time
from datetime import datetime, time as hora_del_dia, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.models import Cuota, ConfiguracionMensajesAutomaticos, EnvioWhatsApp, Notificacion, PerfilUsuario, fecha_local_hoy
from core import whatsapp_bridge

PAUSA_MIN_SEGUNDOS = 20
PAUSA_MAX_SEGUNDOS = 60

# Pasada esta hora ya no se manda un mensaje atrasado (salvo que su hora
# configurada sea más tarde: entonces se acepta hasta fin del día).
HORA_LIMITE_DEFAULT = hora_del_dia(21, 0)

# Un mismo mensaje que falló esta cantidad de veces hoy no se reintenta más
# (ej. número inválido): si no, cada corrida horaria lo volvería a probar.
MAX_INTENTOS_FALLIDOS_POR_DIA = 2

URL_CONEXION_WHATSAPP = '/whatsapp/conexion/'


def hora_local_ahora():
    """Hora actual en el timezone de Argentina (aislado para poder fijarla en los tests)"""
    return timezone.localtime().time().replace(microsecond=0)


def _en_ventana(hora_envio, ahora):
    """True si `ahora` está entre la hora configurada del mensaje y el límite del día"""
    if isinstance(hora_envio, str):
        hora_envio = datetime.strptime(hora_envio[:5], '%H:%M').time()
    limite = HORA_LIMITE_DEFAULT if hora_envio < hora_del_dia(19, 0) else hora_del_dia(23, 59, 59)
    return hora_envio <= ahora <= limite


class Command(BaseCommand):
    help = 'Envía los 3 mensajes automáticos configurables (recordatorio, aviso del día, aviso de mora) por WhatsApp'

    def add_arguments(self, parser):
        parser.add_argument(
            '--simular', action='store_true',
            help='No envía ni registra nada: solo muestra qué mensajes saldrían ahora.'
        )

    def handle(self, *args, **options):
        self.simular = options['simular']
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

        hoy = fecha_local_hoy()
        ahora = hora_local_ahora()
        tareas = self._tareas_de_ahora(config, hoy, ahora)
        pendientes = [(tarea, cuota) for tarea in tareas for cuota in self._cuotas_pendientes(tarea)]

        if not pendientes:
            self.stdout.write('No hay mensajes pendientes en este momento.')
            return

        motivo_sin_conexion = None
        try:
            estado_bridge = whatsapp_bridge.obtener_estado()
            if not estado_bridge.get('connected'):
                motivo_sin_conexion = 'El bridge de WhatsApp no está conectado.'
        except whatsapp_bridge.WhatsAppBridgeError as e:
            motivo_sin_conexion = f'No se pudo consultar el bridge de WhatsApp: {e}.'

        if motivo_sin_conexion:
            self.stdout.write(self.style.WARNING(
                f'{motivo_sin_conexion} {len(pendientes)} mensaje(s) pendiente(s), no se envía nada.'
            ))
            if not self.simular:
                self._avisar_sin_conexion(len(pendientes))
            return

        if self.simular:
            self.stdout.write(self.style.WARNING(f'SIMULACIÓN: se enviarían {len(pendientes)} mensaje(s) ahora:'))
            for tarea, cuota in pendientes:
                cliente = cuota.prestamo.cliente
                self.stdout.write(f'  - {tarea["tipo"].label}: {cliente.nombre_completo} (cuota {cuota.fecha_vencimiento})')
            return

        if self._hay_otra_corrida_en_curso():
            self.stdout.write('Hay otra corrida enviando mensajes en este momento, se saltea esta.')
            return

        enviados, fallidos = self._enviar(config, pendientes)
        self.stdout.write(self.style.SUCCESS(f'Mensajes automáticos enviados: {enviados}. Fallidos: {fallidos}.'))

        if fallidos:
            self._avisar_fallidos(fallidos)

    # ------------------------------------------------------------------ qué toca mandar

    def _tareas_de_ahora(self, config, hoy, ahora):
        """Los tipos de mensaje que, por día de semana y hora, corresponde mandar ahora"""
        tareas = []
        if (config.recordatorio_activo
                and ConfiguracionMensajesAutomaticos.dia_activo(config.recordatorio_dias_semana, hoy)
                and _en_ventana(config.recordatorio_hora, ahora)):
            tareas.append({
                'tipo': EnvioWhatsApp.Tipo.RECORDATORIO_PREVENTIVO,
                'fecha': hoy + timedelta(days=config.recordatorio_dias_antes),
                'plantilla': config.recordatorio_plantilla,
            })
        if (config.aviso_dia_activo
                and ConfiguracionMensajesAutomaticos.dia_activo(config.aviso_dia_dias_semana, hoy)
                and _en_ventana(config.aviso_dia_hora, ahora)):
            tareas.append({
                'tipo': EnvioWhatsApp.Tipo.AVISO_DIA,
                'fecha': hoy,
                'plantilla': config.aviso_dia_plantilla,
            })
        if (config.aviso_mora_activo
                and ConfiguracionMensajesAutomaticos.dia_activo(config.aviso_mora_dias_semana, hoy)
                and _en_ventana(config.aviso_mora_hora, ahora)):
            tareas.append({
                'tipo': EnvioWhatsApp.Tipo.AVISO_MORA,
                'fecha': hoy - timedelta(days=config.aviso_mora_dias_despues),
                'plantilla': config.aviso_mora_plantilla,
            })
        return tareas

    def _cuotas_pendientes(self, tarea):
        """Cuotas de esa fecha a las que todavía no se les mandó este mensaje hoy (y no agotaron reintentos)"""
        cuotas = Cuota.objects.filter(
            fecha_vencimiento=tarea['fecha'],
            estado__in=['PE', 'PC'],
            prestamo__estado='AC'
        ).select_related('prestamo', 'prestamo__cliente')
        return [
            c for c in cuotas
            if not EnvioWhatsApp.ya_enviado_hoy(c, tarea['tipo'])
            and EnvioWhatsApp.intentos_fallidos_hoy(c, tarea['tipo']) < MAX_INTENTOS_FALLIDOS_POR_DIA
        ]

    # ------------------------------------------------------------------ envío

    def _hay_otra_corrida_en_curso(self):
        """
        Cada envío espera hasta PAUSA_MAX_SEGUNDOS antes del siguiente, así que
        una corrida activa siempre deja un registro reciente. Evita que dos
        corridas horarias solapadas (muchos clientes) manden el mismo mensaje.
        """
        margen = timezone.now() - timedelta(seconds=PAUSA_MAX_SEGUNDOS * 2)
        return EnvioWhatsApp.objects.filter(canal=EnvioWhatsApp.Canal.PERSONAL, fecha_envio__gte=margen).exists()

    def _enviar(self, config, pendientes):
        enviados = 0
        fallidos = 0
        for tarea, cuota in pendientes:
            cliente = cuota.prestamo.cliente
            texto = config.renderizar_plantilla(tarea['plantilla'], cuota)
            try:
                message_id = whatsapp_bridge.enviar_mensaje(cliente.telefono, texto)
                EnvioWhatsApp.objects.create(
                    cliente=cliente, cuota=cuota, tipo=tarea['tipo'], canal=EnvioWhatsApp.Canal.PERSONAL,
                    exitoso=True, message_id=message_id
                )
                enviados += 1
            except whatsapp_bridge.WhatsAppBridgeError as e:
                if whatsapp_bridge.ERROR_NO_CONECTADO in str(e):
                    # Se cayó la sesión a mitad de la corrida: no es culpa del
                    # mensaje, no se cuenta como fallido. Queda pendiente.
                    self.stdout.write(self.style.WARNING('WhatsApp se desconectó durante el envío, se corta la corrida.'))
                    self._avisar_sin_conexion(len(pendientes) - enviados - fallidos)
                    break
                EnvioWhatsApp.objects.create(
                    cliente=cliente, cuota=cuota, tipo=tarea['tipo'], canal=EnvioWhatsApp.Canal.PERSONAL,
                    exitoso=False, error=str(e)
                )
                fallidos += 1

            time.sleep(random.uniform(PAUSA_MIN_SEGUNDOS, PAUSA_MAX_SEGUNDOS))
        return enviados, fallidos

    # ------------------------------------------------------------------ avisos a administradores

    def _administradores(self):
        return User.objects.filter(
            Q(is_superuser=True) | Q(perfil__rol=PerfilUsuario.Rol.ADMIN)
        ).distinct()

    def _notificar_una_vez_por_dia(self, titulo, mensaje, enlace):
        """Crea la notificación a cada admin, salvo que ya tenga una igual de hoy (la corrida es horaria)"""
        hoy = fecha_local_hoy()
        for admin in self._administradores():
            ya_avisado = Notificacion.objects.filter(
                usuario=admin, tipo='AS', titulo=titulo, fecha_creacion__date=hoy
            ).exists()
            if ya_avisado:
                continue
            Notificacion.crear_notificacion(
                tipo='AS', titulo=titulo, mensaje=mensaje, usuario=admin, prioridad='AL', enlace=enlace
            )

    def _avisar_sin_conexion(self, cantidad):
        self._notificar_una_vez_por_dia(
            titulo='WhatsApp desconectado: hay mensajes sin enviar',
            mensaje=f'Hay {cantidad} mensaje(s) automático(s) esperando para salir, pero WhatsApp no está '
                    'conectado. Entrá a WhatsApp y escaneá el QR: al reconectar se envían solos en la '
                    'próxima hora.',
            enlace=URL_CONEXION_WHATSAPP,
        )

    def _avisar_fallidos(self, fallidos):
        self._notificar_una_vez_por_dia(
            titulo='Fallaron mensajes automáticos de WhatsApp',
            mensaje=f'De los mensajes automáticos de hoy, {fallidos} no se pudieron enviar. '
                    'Revisá el registro de envíos en el Django Admin (Envíos de WhatsApp) para el detalle.',
            enlace='/admin/core/enviowhatsapp/',
        )
