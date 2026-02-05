# Préstamos - Sistema de Gestión de Préstamos

Sistema web de gestión de préstamos optimizado para dispositivos móviles (Mobile-First). Diseñado para que un prestamista pueda cobrar en la calle usando su celular.

![Django](https://img.shields.io/badge/Django-4.2+-green)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-purple)

## Características Principales

### Gestión de Préstamos
- **Creación de préstamos** con cálculo automático de intereses
- **Generación automática de cuotas** según frecuencia (diario, semanal, quincenal, mensual)
- **Renovación de préstamos** sumando saldo pendiente al nuevo monto
- **Estados de préstamo**: Activo, Finalizado, Cancelado, Renovado

### Cobros
- **Cobros AJAX**: Registra pagos sin recargar la página
- **Pagos parciales flexibles** con opciones:
  - Ignorar el restante
  - Agregar a la próxima cuota
  - Crear cuota especial
- **Vista de cobros del día** organizada por cliente

### Gestión de Clientes
- Categorización: Excelente, Regular, Moroso, Nuevo
- Estado: Activo/Inactivo
- Historial de préstamos por cliente

### Sistema de Usuarios y Roles
- **Administrador**: Acceso total al sistema
- **Supervisor**: Gestión de cobros y reportes
- **Cobrador**: Solo cobros y consultas

### Reportes
- Cierre de caja diario
- Planilla de impresión optimizada
- Resumen de cartera

### Interfaz
- **Mobile-First**: Optimizada para uso con una sola mano
- **Navegación Bottom Nav**: Estilo aplicación móvil
- **PWA Ready**: Puede instalarse como app

## Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Backend | Python 3.8+ / Django 4.2+ |
| Base de Datos | SQLite (dev) / PostgreSQL (prod) |
| Frontend | HTML5, JavaScript ES6+, Bootstrap 5.3 |
| Formularios | django-crispy-forms + crispy-bootstrap5 |
| Iconografía | Bootstrap Icons |
| Autenticación | Django Auth + Perfiles personalizados |

## Instalación

### Requisitos Previos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)
- Git

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/mondra24/Prestamista.git
cd Prestamista
```

### Paso 2: Crear entorno virtual

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Paso 3: Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 4: Configurar variables de entorno

Crear archivo `.env` en la raíz del proyecto:

```env
DEBUG=True
SECRET_KEY=tu-clave-secreta-muy-segura-aqui-cambiar-en-produccion
DATABASE_URL=sqlite:///db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
```

> **Nota**: Para producción, genera una SECRET_KEY segura y configura DEBUG=False

### Paso 5: Aplicar migraciones

```bash
python manage.py migrate
```

### Paso 6: Crear superusuario

```bash
python manage.py createsuperuser
```

### Paso 7: Cargar datos de prueba (opcional)

```bash
python cargar_datos.py
```

### Paso 8: Iniciar servidor de desarrollo

```bash
python manage.py runserver
```

Acceder a: http://127.0.0.1:8000

## Estructura del Proyecto

```
Prestamista/
├── core/                       # Aplicación principal
│   ├── models.py              # Modelos: Cliente, Prestamo, Cuota, PerfilUsuario
│   ├── views.py               # Vistas y lógica de negocio
│   ├── forms.py               # Formularios con validaciones
│   ├── urls.py                # URLs de la aplicación
│   ├── admin.py               # Panel de administración Django
│   └── migrations/            # Migraciones de BD
│
├── prestamos_config/           # Configuración del proyecto Django
│   ├── settings.py            # Configuración general
│   ├── urls.py                # URLs principales
│   └── wsgi.py                # Configuración WSGI
│
├── templates/                  # Templates HTML
│   ├── base.html              # Template base con navegación
│   ├── registration/          # Templates de login/logout
│   └── core/                  # Templates de la aplicación
│       ├── dashboard.html     # Panel principal
│       ├── cobros.html        # Vista de cobros
│       ├── cliente_list.html  # Lista de clientes
│       ├── prestamo_list.html # Lista de préstamos
│       ├── usuario_list.html  # Gestión de usuarios
│       └── ...
│
├── static/                     # Archivos estáticos
│   ├── css/main.css           # Estilos personalizados
│   ├── js/main.js             # JavaScript principal
│   └── manifest.json          # Manifest PWA
│
├── .env                        # Variables de entorno (no incluir en repo)
├── .gitignore                  # Archivos ignorados por git
├── requirements.txt            # Dependencias Python
├── cargar_datos.py            # Script para datos de prueba
├── manage.py                  # CLI de Django
└── README.md                  # Esta documentación
```

## Modelos de Datos

### PerfilUsuario
Extiende el usuario de Django con roles y permisos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| user | OneToOne(User) | Usuario de Django |
| rol | CharField | AD=Admin, SU=Supervisor, CO=Cobrador |
| telefono | CharField | Teléfono de contacto |
| activo | Boolean | Estado del perfil |

### Cliente

| Campo | Tipo | Descripción |
|-------|------|-------------|
| nombre | CharField | Nombre del cliente |
| apellido | CharField | Apellido del cliente |
| telefono | CharField | Teléfono principal |
| direccion | TextField | Dirección completa |
| categoria | CharField | EX=Excelente, RE=Regular, MO=Moroso, NU=Nuevo |
| estado | CharField | AC=Activo, IN=Inactivo |

### Préstamo

| Campo | Tipo | Descripción |
|-------|------|-------------|
| cliente | ForeignKey | Cliente asociado |
| monto_solicitado | Decimal | Monto del préstamo |
| tasa_interes | Decimal | Porcentaje de interés |
| cuotas_pactadas | Integer | Número de cuotas |
| frecuencia | CharField | DI=Diario, SE=Semanal, QU=Quincenal, ME=Mensual |
| fecha_inicio | Date | Fecha de inicio |
| estado | CharField | AC=Activo, FI=Finalizado, CA=Cancelado, RE=Renovado |

### Cuota

| Campo | Tipo | Descripción |
|-------|------|-------------|
| prestamo | ForeignKey | Préstamo asociado |
| numero_cuota | Integer | Número de la cuota |
| monto_cuota | Decimal | Monto a pagar |
| fecha_vencimiento | Date | Fecha límite de pago |
| monto_pagado | Decimal | Monto pagado (parciales) |
| fecha_pago_real | DateTime | Fecha en que se pagó |
| estado | CharField | PE=Pendiente, PA=Pagado, PC=Parcial |

## URLs y Navegación

### Públicas (requieren login)

| URL | Vista | Descripción |
|-----|-------|-------------|
| `/` | Dashboard | Panel principal con resumen |
| `/cobros/` | Cobros | Lista de cobros del día |
| `/clientes/` | ClienteList | Lista de clientes |
| `/clientes/nuevo/` | ClienteCreate | Crear cliente |
| `/clientes/<id>/editar/` | ClienteUpdate | Editar cliente |
| `/prestamos/` | PrestamoList | Lista de préstamos |
| `/prestamos/nuevo/` | PrestamoCreate | Crear préstamo |
| `/prestamos/<id>/renovar/` | RenovarPrestamo | Renovar préstamo |
| `/cierre-caja/` | CierreCaja | Cierre de caja diario |
| `/reportes/` | Reportes | Reportes generales |
| `/planilla/` | Planilla | Planilla para imprimir |

### Administración

| URL | Descripción |
|-----|-------------|
| `/usuarios/` | Gestión de usuarios (solo admin) |
| `/usuarios/nuevo/` | Crear usuario |
| `/usuarios/<id>/editar/` | Editar usuario |
| `/admin/` | Panel de administración Django |

### API (AJAX)

| Método | URL | Descripción |
|--------|-----|-------------|
| POST | `/api/cobrar/<cuota_id>/` | Registrar cobro |
| POST | `/api/cobrar-parcial/<cuota_id>/` | Cobro parcial con opciones |

## API de Cobros

### Cobro Completo
```javascript
POST /api/cobrar/<cuota_id>/
Content-Type: application/json

Response: { "success": true, "message": "Cuota cobrada" }
```

### Cobro Parcial
```javascript
POST /api/cobrar-parcial/<cuota_id>/
Content-Type: application/json

{
    "monto": 15000,
    "accion_restante": "proxima"  // "ignorar" | "proxima" | "especial"
}

Response: { "success": true, "message": "Pago parcial registrado" }
```

## Roles y Permisos

| Rol | Cobros | Clientes | Préstamos | Usuarios | Admin |
|-----|--------|----------|-----------|----------|-------|
| Administrador | ✅ | ✅ | ✅ | ✅ | ✅ |
| Supervisor | ✅ | ✅ | ✅ | ❌ | ❌ |
| Cobrador | ✅ | 👁️ | 👁️ | ❌ | ❌ |

*👁️ = Solo lectura*

## Colores del Sistema

| Color | Código | Uso |
|-------|--------|-----|
| Verde | #198754 | Pagado, Excelente |
| Naranja | #fd7e14 | Pendiente, Regular |
| Rojo | #dc3545 | Moroso, Vencido |
| Azul | #0d6efd | Nuevo, Info |
| Gris | #6c757d | Inactivo |

## Configuración para Producción

### 1. Variables de entorno

```env
DEBUG=False
SECRET_KEY=clave-super-segura-generada-aleatoriamente
DATABASE_URL=postgres://user:password@host:5432/dbname
ALLOWED_HOSTS=tudominio.com,www.tudominio.com
```

### 2. Instalar dependencias adicionales

```bash
pip install psycopg2-binary gunicorn whitenoise
```

### 3. Configurar archivos estáticos

```bash
python manage.py collectstatic
```

### 4. Ejecutar con Gunicorn

```bash
gunicorn prestamos_config.wsgi:application --bind 0.0.0.0:8000
```

## Credenciales por Defecto

Si ejecutaste `cargar_datos.py`:

| Usuario | Contraseña | Rol |
|---------|------------|-----|
| admin | admin123 | Administrador |

> **Importante**: Cambia estas credenciales en producción.

## Soporte

Para reportar bugs o solicitar funcionalidades, crea un issue en el repositorio.

## Licencia

Proyecto privado - Todos los derechos reservados.

---

Desarrollado con Django y Bootstrap 5
