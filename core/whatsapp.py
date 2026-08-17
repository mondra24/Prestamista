"""
Cliente mínimo para la WhatsApp Cloud API de Meta (B1).

Las credenciales viven SOLO en variables de entorno — nunca en la base de
datos ni en el código — mismo criterio que SECRET_KEY/DATABASE_URL en
settings.py:

    WHATSAPP_ACCESS_TOKEN    token permanente del System User de Meta
    WHATSAPP_PHONE_NUMBER_ID ID del número de WhatsApp Business verificado
    WHATSAPP_API_VERSION     opcional, default 'v21.0'

Mensajes fuera de la ventana de 24hs de conversación (como un recordatorio
que arranca la charla) solo se pueden mandar con una plantilla ya aprobada
por Meta — por eso esta función solo sabe mandar plantillas, no texto libre.
"""
import os

import requests

API_VERSION = os.environ.get('WHATSAPP_API_VERSION', 'v21.0')
TIMEOUT_SEGUNDOS = 15


class WhatsAppError(Exception):
    """Error al enviar un mensaje por WhatsApp (credenciales, red, o rechazo de Meta)"""


def whatsapp_configurado():
    """True si las credenciales de Meta están cargadas como variables de entorno"""
    return bool(os.environ.get('WHATSAPP_ACCESS_TOKEN') and os.environ.get('WHATSAPP_PHONE_NUMBER_ID'))


def normalizar_telefono_ar(telefono):
    """
    Aproxima el número al formato E.164 que espera Meta (código de país sin
    '+', sin el 0 de larga distancia). Los números de celular argentinos
    tienen reglas particulares (el '9' extra después del 54) que solo se
    pueden terminar de validar probando contra la API real de Meta una vez
    dado de alta el número — dejar registrado para revisar en ese momento.
    """
    digitos = ''.join(c for c in telefono if c.isdigit())
    if digitos.startswith('54'):
        return digitos
    if digitos.startswith('0'):
        digitos = digitos[1:]
    return f'54{digitos}'


def enviar_plantilla_whatsapp(telefono, nombre_plantilla, parametros, idioma='es_AR'):
    """
    Envía un mensaje de plantilla aprobada por Meta.
    parametros: lista de strings, en el mismo orden que las variables
    {{1}}, {{2}}... definidas en la plantilla aprobada en Meta.
    Retorna el message_id de Meta si sale bien. Lanza WhatsAppError si falla.
    """
    if not whatsapp_configurado():
        raise WhatsAppError('WhatsApp no está configurado (faltan las variables de entorno)')

    token = os.environ.get('WHATSAPP_ACCESS_TOKEN')
    phone_number_id = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')

    url = f'https://graph.facebook.com/{API_VERSION}/{phone_number_id}/messages'
    payload = {
        'messaging_product': 'whatsapp',
        'to': normalizar_telefono_ar(telefono),
        'type': 'template',
        'template': {
            'name': nombre_plantilla,
            'language': {'code': idioma},
            'components': [{
                'type': 'body',
                'parameters': [{'type': 'text', 'text': str(p)} for p in parametros]
            }]
        }
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT_SEGUNDOS)
    except requests.RequestException as e:
        raise WhatsAppError(f'Error de conexión con WhatsApp: {e}')

    if response.status_code != 200:
        raise WhatsAppError(f'WhatsApp rechazó el mensaje ({response.status_code}): {response.text}')

    data = response.json()
    mensajes = data.get('messages') or [{}]
    return mensajes[0].get('id')
