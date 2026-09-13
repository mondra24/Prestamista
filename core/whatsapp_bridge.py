"""
Cliente HTTP para el bridge de WhatsApp (número personal, vía QR).

Es un servicio Node.js separado (ver whatsapp-bridge/ en la raíz del repo)
que corre en un segundo servicio de Railway, en red privada. Este módulo
solo le habla por HTTP — no es la API oficial de Meta, ver core/whatsapp.py
para ese otro camino (independiente, no se mezclan).

Variables de entorno:
    WHATSAPP_BRIDGE_URL     ej. http://whatsapp-bridge.railway.internal:3000
    WHATSAPP_BRIDGE_SECRET  mismo valor que BRIDGE_SECRET del servicio Node
"""
import os

import requests

TIMEOUT_SEGUNDOS = 10


class WhatsAppBridgeError(Exception):
    """Error al hablar con el bridge de WhatsApp (no configurado, caído, o rechazó el pedido)"""


def bridge_configurado():
    """True si las variables de entorno del bridge están cargadas"""
    return bool(os.environ.get('WHATSAPP_BRIDGE_URL') and os.environ.get('WHATSAPP_BRIDGE_SECRET'))


def _headers():
    return {'X-Bridge-Secret': os.environ.get('WHATSAPP_BRIDGE_SECRET', '')}


def _url(path):
    base = os.environ.get('WHATSAPP_BRIDGE_URL', '').rstrip('/')
    return f'{base}{path}'


def obtener_estado():
    """Retorna {'connected': bool, 'phone': str|None}. Lanza WhatsAppBridgeError si el bridge no responde."""
    if not bridge_configurado():
        raise WhatsAppBridgeError('El bridge de WhatsApp no está configurado')
    try:
        response = requests.get(_url('/status'), headers=_headers(), timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException as e:
        raise WhatsAppBridgeError(f'No se pudo conectar con el bridge: {e}')
    if response.status_code != 200:
        raise WhatsAppBridgeError(f'El bridge respondió con error ({response.status_code})')
    return response.json()


def obtener_qr():
    """Retorna {'qr': str|None (PNG en base64), 'connected': bool}. Lanza WhatsAppBridgeError si falla."""
    if not bridge_configurado():
        raise WhatsAppBridgeError('El bridge de WhatsApp no está configurado')
    try:
        response = requests.get(_url('/qr'), headers=_headers(), timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException as e:
        raise WhatsAppBridgeError(f'No se pudo conectar con el bridge: {e}')
    if response.status_code != 200:
        raise WhatsAppBridgeError(f'El bridge respondió con error ({response.status_code})')
    return response.json()


def desconectar():
    """Desvincula el dispositivo. Lanza WhatsAppBridgeError si falla."""
    if not bridge_configurado():
        raise WhatsAppBridgeError('El bridge de WhatsApp no está configurado')
    try:
        response = requests.post(_url('/disconnect'), headers=_headers(), timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException as e:
        raise WhatsAppBridgeError(f'No se pudo conectar con el bridge: {e}')
    if response.status_code != 200:
        raise WhatsAppBridgeError(f'El bridge respondió con error ({response.status_code})')
    return response.json()


def enviar_mensaje(telefono, texto):
    """
    Manda un mensaje de texto libre por WhatsApp. A diferencia de la API de
    Meta, acá no hace falta plantilla aprobada ni ventana de 24hs.
    Retorna el message_id si sale bien. Lanza WhatsAppBridgeError si falla
    (incluye el caso "no está conectado").
    """
    if not bridge_configurado():
        raise WhatsAppBridgeError('El bridge de WhatsApp no está configurado')
    try:
        response = requests.post(
            _url('/send'),
            headers=_headers(),
            json={'to': telefono, 'message': texto},
            timeout=TIMEOUT_SEGUNDOS
        )
    except requests.RequestException as e:
        raise WhatsAppBridgeError(f'No se pudo conectar con el bridge: {e}')

    if response.status_code == 409:
        raise WhatsAppBridgeError('WhatsApp no está conectado')
    if response.status_code != 200:
        raise WhatsAppBridgeError(f'El bridge rechazó el mensaje ({response.status_code}): {response.text}')

    data = response.json()
    return data.get('message_id')
