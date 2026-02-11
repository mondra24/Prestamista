"""
Template tags personalizados para formateo de moneda en Pesos Argentinos
Formato: $ 1.000.000 (punto como separador de miles)
"""
from django import template
from decimal import Decimal

register = template.Library()


@register.filter(name='formato_ars')
def formato_ars(value, decimales=0):
    """
    Formatea un número al estilo de pesos argentinos.
    Usa punto como separador de miles y coma para decimales.
    
    Ejemplo: 1234567.89 -> 1.234.567,89
    
    Uso en template: {{ monto|formato_ars }} o {{ monto|formato_ars:2 }}
    """
    if value is None:
        return '$0'
    
    try:
        # Convertir a Decimal para precisión
        if isinstance(value, str):
            value = Decimal(value.replace(',', '.'))
        else:
            value = Decimal(str(value))
        
        # Redondear según decimales especificados
        if decimales == 0:
            value = value.quantize(Decimal('1'))
        else:
            format_str = '0.' + '0' * decimales
            value = value.quantize(Decimal(format_str))
        
        # Separar parte entera y decimal
        str_value = str(abs(value))
        
        if '.' in str_value:
            parte_entera, parte_decimal = str_value.split('.')
        else:
            parte_entera = str_value
            parte_decimal = ''
        
        # Agregar puntos como separador de miles
        parte_entera_formateada = ''
        for i, digito in enumerate(reversed(parte_entera)):
            if i > 0 and i % 3 == 0:
                parte_entera_formateada = '.' + parte_entera_formateada
            parte_entera_formateada = digito + parte_entera_formateada
        
        # Construir resultado
        resultado = parte_entera_formateada
        if parte_decimal and decimales > 0:
            resultado += ',' + parte_decimal
        
        # Agregar signo negativo si corresponde
        if value < 0:
            resultado = '-' + resultado
        
        return resultado
    except (ValueError, TypeError, Exception):
        return str(value)


@register.filter(name='dinero')
def dinero(value, decimales=0):
    """
    Formatea como dinero con símbolo de peso.
    
    Ejemplo: 1234567 -> $1.234.567
    
    Uso en template: {{ monto|dinero }} o {{ monto|dinero:2 }}
    """
    formateado = formato_ars(value, decimales)
    return f'${formateado}'


@register.filter(name='dinero_completo')
def dinero_completo(value):
    """
    Formatea como dinero mostrando siempre 2 decimales.
    
    Ejemplo: 1234567.5 -> $1.234.567,50
    """
    return dinero(value, 2)


@register.simple_tag
def formato_moneda(value, simbolo='$', decimales=0, mostrar_cero=True):
    """
    Tag más flexible para formatear moneda.
    
    Uso: {% formato_moneda monto "$" 2 True %}
    """
    if value is None or (value == 0 and not mostrar_cero):
        return ''
    
    formateado = formato_ars(value, decimales)
    return f'{simbolo}{formateado}'


@register.filter(name='formato_miles')
def formato_miles(value):
    """
    Solo formatea con separador de miles (sin símbolo de moneda).
    
    Ejemplo: 1234567 -> 1.234.567
    """
    return formato_ars(value, 0)


@register.filter(name='numero_raw')
def numero_raw(value):
    """
    Devuelve el número sin formato, ideal para data attributes de HTML.
    Usa punto como separador decimal (formato JavaScript/internacional).
    
    Ejemplo: 100000.50 -> 100000.50
    
    Uso en template: data-monto="{{ monto|numero_raw }}"
    """
    if value is None:
        return '0'
    
    try:
        if isinstance(value, str):
            # Convertir de formato argentino a número
            value = value.replace('.', '').replace(',', '.')
        return str(float(value))
    except (ValueError, TypeError):
        return '0'
