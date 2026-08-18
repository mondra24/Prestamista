# Generated manually, siguiendo el mismo patrón seguro que
# 0020_add_token_publico_prestamo.py (agregar nullable, poblar, luego
# volver unique) para no romper con clientes ya existentes en producción.

from django.db import migrations, models
import uuid


def generar_uuids_existentes(apps, schema_editor):
    """Genera UUIDs únicos para clientes existentes"""
    Cliente = apps.get_model('core', 'Cliente')
    for cliente in Cliente.objects.all():
        cliente.token_publico = uuid.uuid4()
        cliente.save(update_fields=['token_publico'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_cuota_core_cuota_estado_e94d11_idx_and_more'),
    ]

    operations = [
        # Paso 1: Agregar token_activo (simple, con default)
        migrations.AddField(
            model_name='cliente',
            name='token_activo',
            field=models.BooleanField(default=True, verbose_name='Link Público del Cliente Activo'),
        ),
        # Paso 2: Agregar token_publico SIN unique (para poder poblar)
        migrations.AddField(
            model_name='cliente',
            name='token_publico',
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True, verbose_name='Token Público del Cliente'),
        ),
        # Paso 3: Poblar UUIDs únicos en registros existentes
        migrations.RunPython(generar_uuids_existentes, migrations.RunPython.noop),
        # Paso 4: Hacer el campo NOT NULL + unique + db_index
        migrations.AlterField(
            model_name='cliente',
            name='token_publico',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True, verbose_name='Token Público del Cliente'),
        ),
    ]
