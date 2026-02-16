"""
Data migration: Asignar cobrador a préstamos existentes.
Copia el valor de cliente.usuario al campo prestamo.cobrador
para todos los préstamos que no tienen cobrador asignado.
"""
from django.db import migrations


def populate_cobrador(apps, schema_editor):
    """Asignar cobrador = cliente.usuario para préstamos existentes"""
    Prestamo = apps.get_model('core', 'Prestamo')
    for prestamo in Prestamo.objects.filter(cobrador__isnull=True).select_related('cliente'):
        if prestamo.cliente and prestamo.cliente.usuario_id:
            prestamo.cobrador_id = prestamo.cliente.usuario_id
            prestamo.save(update_fields=['cobrador'])


def reverse_populate(apps, schema_editor):
    """Reversa: limpiar cobrador"""
    Prestamo = apps.get_model('core', 'Prestamo')
    Prestamo.objects.all().update(cobrador=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_add_cobrador_to_prestamo'),
    ]

    operations = [
        migrations.RunPython(populate_cobrador, reverse_populate),
    ]
