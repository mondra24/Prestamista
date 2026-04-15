# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proyecto

**PrestaFácil** — Sistema de gestión de préstamos con Django 4.2. Aplicación mobile-first con PWA para que cobradores gestionen clientes, préstamos y cobros en campo. Desplegado en Railway con PostgreSQL.

## Comandos de desarrollo

```bash
# Servidor local
python manage.py runserver

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Tests
python manage.py test core

# Datos iniciales y de prueba
python manage.py init_data                        # Configuraciones base (mora, crédito, etc.)
python manage.py create_superuser_if_not_exists   # Crea admin si no existe
python manage.py load_sample_data                 # Datos de ejemplo
python manage.py generate_test_volume             # Dataset grande para testing

# Otros comandos útiles
python manage.py db_check                         # Validar integridad de BD
python manage.py assign_clients_to_users          # Asignar clientes a usuarios
python manage.py update_credit_limits             # Actualizar límites de crédito
```

## Arquitectura

Aplicación Django monolítica con una sola app `core`. Todo el código de negocio está en:

- **`core/models.py`** — 15 modelos. Los principales: `PerfilUsuario` (roles), `Cliente`, `Prestamo`, `Cuota`, `InteresMora`, `HistorialModificacionPago`
- **`core/views.py`** — Vistas basadas en clases (CBV) + funciones AJAX. Todas usan `LoginRequiredMixin`
- **`core/forms.py`** — Formularios con crispy-bootstrap5. `PrestamoForm` auto-calcula monto total
- **`core/urls.py`** — Namespace `core`. Endpoints AJAX bajo `api/`
- **`core/templatetags/currency_filters.py`** — Filtros `|dinero`, `|formato_ars`, `|numero_raw` para formato ARS

### Configuración Django

- Settings: `prestamos_config/settings.py`
- Idioma: `es-ar`, timezone: `America/Argentina/Buenos_Aires`
- BD: SQLite (dev), PostgreSQL (prod via `DATABASE_URL`)
- Estáticos: WhiteNoise, crispy-bootstrap5

### Roles y permisos

Tres roles en `PerfilUsuario.Rol`: `AD` (Admin), `CO` (Cobrador), `SU` (Supervisor).

```python
# Helpers en views.py
es_usuario_admin(user)  # Superuser o rol AD
es_superadmin(user)     # Solo superuser

# Patrón de filtrado: admin ve todo, cobrador solo lo suyo
if es_usuario_admin(user):
    queryset = Model.objects.all()
else:
    queryset = Model.objects.filter(user=user)
```

### Estados clave

| Modelo    | Códigos                                                        |
|-----------|----------------------------------------------------------------|
| Cuota     | `PE` (Pendiente), `PC` (Parcial), `PA` (Pagada Completa)      |
| Préstamo  | `AC` (Activo), `FI` (Finalizado), `CA` (Cancelado), `RE` (Renovado) |
| Cliente   | Categorías: `EX`, `RE`, `MO`, `NU`. Estado: `AC`, `IN`        |
| Frecuencia| `DI`, `SE`, `QU`, `ME`, `PU` (Pago Único)                     |

### Endpoints AJAX

Los cobros se procesan sin recarga de página. Las funciones `cobrar_cuota`, `editar_cobro`, `anular_pago_cuota` en `views.py` reciben POST y retornan `JsonResponse` con estructura `{success, message, data}`.

### Frontend

- Templates en `templates/core/`, base layout en `templates/base.html`
- CSS: `static/css/main.css` (mobile-first)
- JS: `static/js/main.js` (AJAX, modales, PWA service worker, formateo de moneda)
- Filtros de moneda: usar `|dinero` en templates para formato `$1.234.567`

## Convenciones importantes

- **Moneda**: usar `Decimal` siempre, nunca `float`. Formatear solo en presentación con filtros de template
- **Fechas**: usar `fecha_local_hoy()` (definida en models.py) para obtener la fecha actual en timezone Argentina
- **Templates de moneda**: `{{ monto|dinero }}` para pesos, `{{ monto|numero_raw }}` para atributos data en HTML

## Deploy (Railway)

El `Procfile` ejecuta en orden: `db_check` → `migrate` → `init_data` → `create_superuser_if_not_exists` → `collectstatic` → `gunicorn`. Variables requeridas: `DATABASE_URL`, `SECRET_KEY`, `DEBUG=False`.
