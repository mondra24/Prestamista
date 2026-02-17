<p align="center">
  <img src="https://img.shields.io/badge/PrestaFácil-Sistema%20de%20Préstamos-blue?style=for-the-badge&logo=django&logoColor=white" alt="PrestaFácil"/>
</p>

<h1 align="center">💰 PrestaFácil</h1>

<p align="center">
  <strong>Sistema integral de gestión de préstamos y cobranzas</strong><br>
  Diseñado para cobrar en la calle desde el celular
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Django-4.2-092E20?style=flat-square&logo=django&logoColor=white" alt="Django 4.2"/>
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11"/>
  <img src="https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=flat-square&logo=bootstrap&logoColor=white" alt="Bootstrap 5.3"/>
  <img src="https://img.shields.io/badge/PostgreSQL-17-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/Deploy-Railway-blueviolet?style=flat-square&logo=railway&logoColor=white" alt="Railway"/>
  <img src="https://img.shields.io/badge/PWA-Ready-orange?style=flat-square&logo=pwa&logoColor=white" alt="PWA"/>
</p>

---

## 📋 Tabla de Contenidos

- [Descripción](#-descripción)
- [Características](#-características)
- [Arquitectura](#-arquitectura)
- [Modelos de Datos](#-modelos-de-datos)
- [Roles y Permisos](#-roles-y-permisos)
- [Endpoints y Vistas](#-endpoints-y-vistas)
- [Stack Tecnológico](#-stack-tecnológico)
- [Instalación Local](#-instalación-local)
- [Deploy en Railway](#-deploy-en-railway)
- [Exportaciones Excel](#-exportaciones-excel)
- [Formato de Moneda](#-formato-de-moneda)
- [Configuraciones Administrables](#%EF%B8%8F-configuraciones-administrables)

---

## 📖 Descripción

**PrestaFácil** es un sistema web **Mobile-First** para la gestión completa del ciclo de vida de préstamos personales. Permite a un equipo de cobradores administrar clientes, crear préstamos, registrar pagos en la calle desde el celular, y al administrador supervisar toda la operación en tiempo real.

### ¿Para quién es?

| Rol | Uso principal |
|-----|---------------|
| **Administrador** | Supervisar cobradores, ver reportes, gestionar usuarios y configuraciones |
| **Cobrador** | Cobrar cuotas en la calle, gestionar sus clientes y préstamos |
| **Supervisor** | Revisar reportes y planillas sin gestionar usuarios |

---

## ✨ Características

### 💰 Préstamos
- Creación con cálculo automático de intereses y cuotas
- Frecuencias: **Diario**, **Semanal**, **Quincenal**, **Mensual**
- Renovación de préstamos (suma saldo pendiente al nuevo monto)
- Estados: `Activo` → `Finalizado` | `Renovado` | `Cancelado`
- Límites de crédito configurables por categoría de cliente

### 📱 Cobros en Tiempo Real
- **Cobros AJAX** — sin recargar la página
- **Pagos parciales** con 3 opciones para el restante:
  - 🔹 Ignorar (queda como saldo en la cuota)
  - 🔹 Sumar a la próxima cuota
  - 🔹 Crear cuota especial con fecha personalizada
- **Métodos de pago**: Efectivo, Transferencia, Mixto
- **Interés por mora** configurable (% diario, días de gracia)
- Vista organizada: Vencidas → Hoy → Próximos 7 días → Resto del mes

### 📊 Historial de Modificaciones
- Rastreo completo de cada pago: montos anteriores y nuevos
- Tipos registrados:
  - `Pago Parcial` · `Pago Completo` · `Transferencia a Próxima`
  - `Cuota Especial Creada` · `Monto Recibido de Otra Cuota`
- Accesible desde: detalle del préstamo, cobros del día, cierre de caja
- Botón **"Modificada"** en cuotas con historial para ver el origen del monto

### 👥 Clientes
- Categorización: **Excelente** · **Regular** · **Moroso** · **Nuevo**
- Asignación a rutas de cobro y tipos de negocio
- Un cliente puede ser compartido entre cobradores
- El admin ve todos los préstamos de cada cobrador en el mismo cliente
- Límite de crédito individual o por categoría

### 📋 Reportes y Planillas
- **Dashboard** con estadísticas del día en tiempo real
- **Cierre de caja** diario con detalle de pagos
- **Planilla de impresión** con cuotas del día y vencidas
- **Reporte general** de cartera

### 📥 Exportación Excel
- Planilla de cobros (con # préstamo, datos del cliente, cuotas)
- Cierre de caja (pagos del día con historial de modificaciones en color)
- Lista de clientes completa
- Lista de préstamos con estados

### 🔔 Notificaciones y Auditoría
- Alertas de cuotas vencidas y cobros realizados
- Registro de auditoría de todas las acciones del sistema
- Sistema de respaldos de base de datos

### 🎨 Interfaz Mobile-First
- Navegación inferior estilo app (Bottom Nav)
- **PWA** — instalable como aplicación en el celular
- Diseño responsive optimizado para uso con una mano
- Formato moneda argentina: `$1.234.567,89`

---

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                         │
│  HTML5 + Bootstrap 5.3 + JavaScript ES6 (AJAX)     │
│  Templates Django · PWA · Bootstrap Icons           │
├─────────────────────────────────────────────────────┤
│                    BACKEND                          │
│  Django 4.2 · Class-Based Views · AJAX Endpoints    │
│  django-crispy-forms · openpyxl · WhiteNoise        │
├─────────────────────────────────────────────────────┤
│                  BASE DE DATOS                      │
│  SQLite (desarrollo) │ PostgreSQL 17 (producción)   │
├─────────────────────────────────────────────────────┤
│                    DEPLOY                           │
│  Railway · Gunicorn · WhiteNoise (estáticos)        │
└─────────────────────────────────────────────────────┘
```

---

## 🗃 Modelos de Datos

El sistema tiene **15 modelos** organizados en 4 grupos:

### 👤 Usuarios y Configuración

| Modelo | Descripción |
|--------|-------------|
| `PerfilUsuario` | Extiende User de Django con rol (Admin / Supervisor / Cobrador), teléfono y estado |
| `RutaCobro` | Rutas/zonas geográficas con color y orden para organizar la planilla |
| `TipoNegocio` | Categorías de negocio con límite de crédito sugerido |
| `ConfiguracionCredito` | Límites de crédito por categoría de cliente |
| `ConfiguracionMora` | Porcentaje diario de mora, días de gracia, monto mínimo |

### 💼 Negocio Principal

| Modelo | Descripción |
|--------|-------------|
| `Cliente` | Datos personales, categoría, ruta, tipo negocio, límite crédito, usuario asignado |
| `Prestamo` | Monto, tasa, cuotas, frecuencia, cobrador, estado, soporte de renovaciones |
| `Cuota` | Cada cuota generada: monto, fecha, estado (Pendiente / Pagada / Parcial), método de pago |
| `HistorialModificacionPago` | Registro detallado de cada modificación durante pagos parciales |
| `InteresMora` | Registro de intereses por mora calculados y cobrados |

### 📊 Planilla y Reportes

| Modelo | Descripción |
|--------|-------------|
| `ColumnaPlanilla` | Columnas personalizables de la planilla de impresión |
| `ConfiguracionPlanilla` | Configuración general de la planilla (título, formato) |

### 🔧 Sistema

| Modelo | Descripción |
|--------|-------------|
| `RegistroAuditoria` | Log de acciones (quién, qué, cuándo, dirección IP) |
| `Notificacion` | Alertas para usuarios (vencimientos, cobros, sistema) |
| `ConfiguracionRespaldo` | Configuración de backups automáticos |

### Diagrama de Relaciones

```
User ──1:1──► PerfilUsuario (rol, teléfono)
  │
  ├──1:N──► Cliente (usuario asignado)
  │            │
  │            ├──1:N──► Prestamo
  │            │            │
  │            │            ├──1:N──► Cuota
  │            │            │           │
  │            │            │           ├──1:N──► HistorialModificacionPago
  │            │            │           └──1:N──► InteresMora
  │            │            │
  │            │            └── FK ──► Prestamo (prestamo_anterior / renovación)
  │            │
  │            ├── FK ──► RutaCobro
  │            └── FK ──► TipoNegocio
  │
  └──1:N──► Prestamo (cobrador)
```

---

## 🔐 Roles y Permisos

| Acción | Admin | Supervisor | Cobrador |
|--------|:-----:|:----------:|:--------:|
| Ver dashboard | ✅ | ✅ | ✅ |
| Cobrar cuotas propias | ✅ | ✅ | ✅ |
| Cobrar cuotas de otros | ❌ | ❌ | ❌ |
| Ver préstamos de otros cobradores | ✅ | ❌ | ❌ |
| Ver historial de modificaciones | ✅ | ✅ | ✅ |
| Crear / editar clientes | ✅ | ✅ | ✅ |
| Ver todos los clientes | ✅ | ❌ | ❌ |
| Crear préstamos | ✅ | ✅ | ✅ |
| Renovar préstamos | ✅ | ✅ | ✅ |
| Reportes y planillas | ✅ | ✅ | ❌ |
| Exportar Excel | ✅ | ✅ | ✅ |
| Cierre de caja | ✅ | ✅ | ✅ |
| Gestionar usuarios | ✅ | ❌ | ❌ |
| Ver auditoría | ✅ | ❌ | ❌ |
| Gestionar respaldos | ✅ | ❌ | ❌ |
| Panel Django Admin | ✅ | ❌ | ❌ |

> **Nota:** Cuando dos cobradores comparten un cliente, el admin puede ver todos los préstamos de ambos cobradores en el detalle del cliente, pero **solo el cobrador asignado puede cobrar sus propias cuotas**.

---

## 🌐 Endpoints y Vistas

### Páginas Principales

| URL | Vista | Descripción |
|-----|-------|-------------|
| `/` | `DashboardView` | Panel principal con estadísticas del día |
| `/cobros/` | `CobrosView` | Cuotas para cobrar: vencidas, hoy, semana, mes |
| `/cierre-caja/` | `CierreCajaView` | Resumen de pagos cobrados en el día |
| `/planilla/` | `PlanillaImpresionView` | Planilla imprimible de cobros |
| `/reportes/` | `ReporteGeneralView` | Reporte general de cartera |

### Clientes

| URL | Vista | Descripción |
|-----|-------|-------------|
| `/clientes/` | `ClienteListView` | Lista con búsqueda y filtros por categoría |
| `/clientes/nuevo/` | `ClienteCreateView` | Formulario de creación |
| `/clientes/<id>/` | `ClienteDetailView` | Detalle con todos los préstamos activos e historial |
| `/clientes/<id>/editar/` | `ClienteUpdateView` | Edición de datos |

### Préstamos

| URL | Vista | Descripción |
|-----|-------|-------------|
| `/prestamos/` | `PrestamoListView` | Lista filtrable por estado |
| `/prestamos/nuevo/` | `PrestamoCreateView` | Crear préstamo con cálculo automático |
| `/prestamos/<id>/` | `PrestamoDetailView` | Detalle con cuotas, progreso e historial |
| `/prestamos/<id>/renovar/` | `RenovarPrestamoView` | Renovación sumando saldo pendiente |

### API (AJAX)

| URL | Método | Descripción |
|-----|--------|-------------|
| `/api/cobrar/<id>/` | `POST` | Registrar pago de cuota |
| `/api/cuotas-hoy/` | `GET` | Cuotas del día (tiempo real) |
| `/api/cliente/<id>/categoria/` | `POST` | Cambiar categoría de cliente |
| `/api/buscar-clientes/` | `GET` | Búsqueda de clientes |
| `/api/notificaciones/` | `GET` | Obtener notificaciones pendientes |
| `/api/generar-notificaciones/` | `POST` | Generar alertas de vencimientos |

### Exportaciones Excel

| URL | Descripción |
|-----|-------------|
| `/exportar/planilla/` | Planilla de cobros del día |
| `/exportar/cierre/` | Cierre de caja con historial de modificaciones |
| `/exportar/clientes/` | Lista completa de clientes |
| `/exportar/prestamos/` | Lista de préstamos con estados |

### Administración

| URL | Descripción |
|-----|-------------|
| `/usuarios/` | Gestión de usuarios y roles |
| `/notificaciones/` | Centro de notificaciones |
| `/auditoria/` | Log de auditoría del sistema |
| `/respaldos/` | Gestión de backups de BD |

---

## 🛠 Stack Tecnológico

| Capa | Tecnología | Uso |
|------|------------|-----|
| **Backend** | Python 3.11 / Django 4.2 | Framework web, ORM, autenticación |
| **BD Desarrollo** | SQLite | Base de datos local |
| **BD Producción** | PostgreSQL 17 | Base de datos en Railway |
| **Frontend** | HTML5, JS ES6+, Bootstrap 5.3 | Interfaz responsive Mobile-First |
| **Formularios** | django-crispy-forms + crispy-bootstrap5 | Formularios estilizados |
| **Iconos** | Bootstrap Icons | Iconografía consistente |
| **Excel** | openpyxl | Generación de reportes .xlsx |
| **Estáticos** | WhiteNoise | Servir CSS/JS en producción |
| **Servidor** | Gunicorn | Servidor WSGI de producción |
| **Deploy** | Railway | Hosting con PostgreSQL incluido |
| **Config** | django-environ / dj-database-url | Variables de entorno |

---

## 📦 Instalación Local

### Requisitos
- Python 3.8+ → [python.org](https://python.org)
- Git → [git-scm.com](https://git-scm.com)

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/mondra24/Prestamista.git
cd Prestamista

# 2. Crear entorno virtual
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Aplicar migraciones
python manage.py migrate

# 5. Crear superusuario
python manage.py createsuperuser

# 6. (Opcional) Cargar datos de prueba
python cargar_datos.py

# 7. Iniciar servidor
python manage.py runserver
```

Abrir en el navegador: **http://127.0.0.1:8000**

### Comandos de gestión disponibles

```bash
python manage.py create_superuser_if_not_exists   # Crear admin si no existe
python manage.py load_sample_data                  # Cargar datos de ejemplo
python manage.py assign_clients_to_users           # Asignar clientes a cobradores
python manage.py update_credit_limits              # Actualizar límites de crédito
```

---

## 🚀 Deploy en Railway

### Archivos de configuración (incluidos)

| Archivo | Propósito |
|---------|-----------|
| `requirements.txt` | 14 dependencias Python |
| `Procfile` | Migrate + collectstatic + gunicorn |
| `runtime.txt` | Python `3.11.9` |

### Pasos

1. **Subir a GitHub** — push del repositorio
2. **Railway** → New Project → Provision **PostgreSQL**
3. **Railway** → New → GitHub Repo → seleccionar el repositorio
4. **Variables de entorno:**

| Variable | Valor |
|----------|-------|
| `DATABASE_URL` | *(copiar de PostgreSQL)* |
| `SECRET_KEY` | *(generar clave segura)* |
| `DJANGO_DEBUG` | `False` |

5. **Build Command:**
```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

6. El `Procfile` ejecuta automáticamente migraciones y crea superusuario al iniciar.

---

## 📥 Exportaciones Excel

Todas las exportaciones generan archivos `.xlsx` con formato profesional:

| Exportación | Columnas principales | Notas |
|-------------|---------------------|-------|
| **Planilla** | #, Préstamo, Cliente, Tel., Dirección, Cuota, Monto, Zona, Frecuencia, Fecha Fin, Estado, Mora, Notas | Totales por zona |
| **Cierre** | #, Préstamo, Cliente, Tel., Cuota, Monto Cuota, Pagado, Restante, Estado, Método, Mora, Zona, Fecha, Cobrador, Ref., Notas, Tipo Modif., Monto Anterior, Detalle | Marca amarilla en cuotas modificadas |
| **Clientes** | Nombre, Apellido, Teléfono, Dirección, Categoría, Estado, Ruta, Tipo Negocio | Colores por categoría |
| **Préstamos** | Datos del préstamo, cliente, cobrador, progreso | Filtrable por estado |

---

## 💵 Formato de Moneda

El sistema usa **formato argentino**:

```
$1.234.567,89
 │  │  │   │└─ centavos
 │  │  │   └── separador decimal (coma)
 │  │  └────── separador de miles (punto)
 │  └──────── miles
 └─────────── símbolo peso
```

Implementado con template tags personalizados en `core/templatetags/currency_filters.py`.

---

## ⚙️ Configuraciones Administrables

Todo se gestiona desde el **Django Admin** (`/admin/`):

| Configuración | Qué permite |
|---------------|-------------|
| **Rutas de Cobro** | Crear zonas geográficas con color y orden para la planilla |
| **Tipos de Negocio** | Categorizar clientes por tipo de comercio con crédito sugerido |
| **Config. de Crédito** | Límites de préstamo por categoría (Excelente, Regular, Moroso, Nuevo) |
| **Config. de Mora** | Porcentaje diario, días de gracia, monto mínimo, aplicación automática |
| **Columnas Planilla** | Personalizar qué columnas aparecen en la planilla de impresión |
| **Config. Planilla** | Título, formato y opciones generales de la planilla |
| **Config. Respaldo** | Frecuencia y retención de backups |

---

## 📁 Estructura del Proyecto

```
Prestamista/
│
├── core/                          # Aplicación principal
│   ├── models.py                  # 15 modelos de datos
│   ├── views.py                   # ~2100 líneas (vistas + API + exports)
│   ├── forms.py                   # Formularios con validaciones
│   ├── urls.py                    # 35 endpoints
│   ├── admin.py                   # Panel admin personalizado
│   ├── templatetags/
│   │   └── currency_filters.py    # Filtros: dinero, numero_raw
│   └── management/commands/       # Comandos personalizados
│       ├── create_superuser_if_not_exists.py
│       ├── load_sample_data.py
│       ├── assign_clients_to_users.py
│       └── update_credit_limits.py
│
├── templates/
│   ├── base.html                  # Layout base con bottom-nav y PWA
│   ├── registration/login.html    # Página de login
│   └── core/                      # 16 templates de la app
│       ├── dashboard.html
│       ├── cobros.html            # 4 secciones con historial
│       ├── cierre_caja.html       # Cierre diario con historial
│       ├── planilla_impresion.html
│       ├── cliente_*.html         # CRUD clientes
│       ├── prestamo_*.html        # CRUD + detalle + renovación
│       ├── reporte_general.html
│       ├── usuario_*.html         # Gestión usuarios
│       ├── notificacion_list.html
│       ├── auditoria_list.html
│       └── respaldo_list.html
│
├── static/
│   ├── css/main.css               # Estilos Mobile-First (~2000 líneas)
│   ├── js/main.js                 # AJAX, modales, serviceworker
│   └── manifest.json              # Configuración PWA
│
├── prestamos_config/              # Configuración Django
│   ├── settings.py                # Dual DB (SQLite / PostgreSQL)
│   ├── urls.py
│   └── wsgi.py
│
├── backups/                       # Respaldos locales .sqlite3
├── requirements.txt               # 14 dependencias
├── Procfile                       # Comando Railway
├── runtime.txt                    # Python 3.11.9
└── manage.py
```

---

## 🎨 Guía Visual

### Colores de Estado

| Estado | Color | Código |
|--------|:-----:|--------|
| ✅ Pagado / Excelente | 🟢 Verde | `#198754` |
| ⏳ Pendiente / Regular | 🟠 Naranja | `#fd7e14` |
| ❌ Moroso / Vencido | 🔴 Rojo | `#dc3545` |
| 🆕 Nuevo / Info | 🔵 Azul | `#0d6efd` |
| ⚠️ Modificado / Parcial | 🟡 Amarillo | `#ffc107` |

### Badges del Historial de Modificaciones

| Tipo | Color | Significado |
|------|-------|-------------|
| `Pago Parcial` | 🟡 Amarillo | Se pagó menos del total de la cuota |
| `Pago Completo` | 🟢 Verde | Cuota pagada en su totalidad |
| `Restante a Próxima` | 🔵 Celeste | Sobrante transferido a la siguiente cuota |
| `Cuota Especial` | 🔵 Azul | Se creó cuota nueva con fecha especial |
| `Monto Recibido` | ⚫ Gris | Cuota que recibió monto de otra cuota |

---

## 📄 Licencia

Proyecto privado — Todos los derechos reservados.

---

<p align="center">
  Desarrollado con ❤️ usando <strong>Django</strong> y <strong>Bootstrap 5</strong>
</p>
