# PrestaFácil - Sistema de Gestión de Préstamos

Sistema web de gestión de préstamos optimizado para dispositivos móviles (Mobile-First). Diseñado para que un prestamista pueda cobrar en la calle usando su celular.

![Django](https://img.shields.io/badge/Django-4.2+-green)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-purple)
![Railway](https://img.shields.io/badge/Deploy-Railway-blueviolet)

## 🚀 Demo en Vivo

**URL:** `https://tu-proyecto.up.railway.app`

## ✨ Características Principales

### 💰 Gestión de Préstamos
- **Creación de préstamos** con cálculo automático de intereses
- **Generación automática de cuotas** según frecuencia (diario, semanal, quincenal, mensual)
- **Renovación de préstamos** sumando saldo pendiente al nuevo monto
- **Estados de préstamo**: Activo, Finalizado, Cancelado, Renovado

### 📱 Cobros
- **Cobros AJAX**: Registra pagos sin recargar la página
- **Pagos parciales flexibles** con opciones:
  - Ignorar el restante
  - Agregar a la próxima cuota
  - Crear cuota especial
- **Vista de cobros del día** organizada por cliente
- **Próximos 7 días**: Ver cuotas que vencen próximamente

### 👥 Gestión de Clientes
- Categorización: Excelente, Regular, Moroso, Nuevo
- Estado: Activo/Inactivo
- Historial de préstamos por cliente
- Rutas de cobro asignables

### 👤 Sistema de Usuarios y Roles
- **Administrador**: Acceso total al sistema
- **Supervisor**: Gestión de cobros y reportes
- **Cobrador**: Solo cobros y consultas

### 📊 Reportes y Exportación
- Cierre de caja diario
- Planilla de impresión optimizada
- Resumen de cartera
- **Exportación a Excel** (clientes, préstamos, planillas)

### 🔔 Sistema de Notificaciones
- Alertas de cuotas vencidas
- Notificaciones de cobros realizados
- Auditoría de acciones del sistema

### 🎨 Interfaz
- **Mobile-First**: Optimizada para uso con una sola mano
- **Navegación Bottom Nav**: Estilo aplicación móvil
- **PWA Ready**: Puede instalarse como app
- **Formato moneda argentina**: $1.234.567,89

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Backend | Python 3.11 / Django 4.2+ |
| Base de Datos | SQLite (dev) / PostgreSQL (prod) |
| Frontend | HTML5, JavaScript ES6+, Bootstrap 5.3 |
| Formularios | django-crispy-forms + crispy-bootstrap5 |
| Iconografía | Bootstrap Icons |
| Deploy | Railway + Gunicorn + WhiteNoise |
| Excel | openpyxl |

## 📦 Instalación Local

### Requisitos Previos
- Python 3.8 o superior
- pip (gestor de paquetes de Python)
- Git

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/financiera.git
cd financiera
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

### Paso 4: Aplicar migraciones

```bash
python manage.py migrate
```

### Paso 5: Crear superusuario

```bash
python manage.py createsuperuser
```

### Paso 6: Cargar datos de prueba (opcional)

```bash
python cargar_datos.py
```

### Paso 7: Iniciar servidor

```bash
python manage.py runserver
```

Acceder a: http://127.0.0.1:8000

## 🚀 Deploy en Railway

### Archivos necesarios (ya incluidos)
- `requirements.txt` - Dependencias Python
- `Procfile` - Comando de inicio
- `runtime.txt` - Versión de Python

### Pasos para deploy

#### 1. Subir a GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/financiera.git
git push -u origin main
```

#### 2. Configurar Railway
1. Ir a [railway.app](https://railway.app) y loguearse con GitHub
2. **New Project** → **Provision PostgreSQL** (crear base de datos)
3. **New** → **GitHub Repo** → Seleccionar tu repositorio
4. Copiar `DATABASE_URL` de PostgreSQL → Variables del proyecto Django

#### 3. Configurar Variables en Railway
En tu proyecto Django → **Variables**:
| Variable | Valor |
|----------|-------|
| `DATABASE_URL` | (copiar de PostgreSQL) |
| `SECRET_KEY` | (generar una clave segura) |
| `DJANGO_DEBUG` | `False` |

#### 4. Configurar Build Command
En **Settings** → **Build Command**:
```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
```

#### 5. Crear superusuario
En Railway → **Shell**:
```bash
python manage.py createsuperuser
```

Tu app estará en: `https://tu-proyecto.up.railway.app`

## 🧪 Tests

Ejecutar suite de tests (66 tests):
```bash
python manage.py test core -v 2
```

## 📁 Estructura del Proyecto

```
financiera/
├── core/                       # Aplicación principal
│   ├── models.py              # Cliente, Prestamo, Cuota, Notificacion, Auditoria
│   ├── views.py               # Vistas y lógica de negocio
│   ├── forms.py               # Formularios con validaciones
│   ├── urls.py                # URLs de la aplicación
│   ├── admin.py               # Panel de administración
│   ├── tests.py               # Suite de tests (66 tests)
│   └── templatetags/          # Filtros personalizados (formato ARS)
│
├── prestamos_config/          # Configuración Django
│   ├── settings.py            # Configuración (Railway-ready)
│   └── wsgi.py                # WSGI para Gunicorn
│
├── templates/                 # Templates HTML
│   ├── base.html              # Template base con navegación
│   └── core/                  # Templates de la app
│
├── static/                    # CSS, JS, imágenes
├── Procfile                   # Comando para Railway
├── runtime.txt                # Python 3.11
├── requirements.txt           # Dependencias
└── README.md                  # Documentación
```

## 💵 Formato de Moneda

El sistema usa formato argentino:
- Separador de miles: punto (.)
- Separador decimal: coma (,)
- Ejemplo: `$1.234.567,89`

## 🔐 Roles y Permisos

| Rol | Cobros | Clientes | Préstamos | Usuarios | Admin |
|-----|--------|----------|-----------|----------|-------|
| Administrador | ✅ | ✅ | ✅ | ✅ | ✅ |
| Supervisor | ✅ | ✅ | ✅ | ❌ | ❌ |
| Cobrador | ✅ | 👁️ | 👁️ | ❌ | ❌ |

*👁️ = Solo lectura*

## 📱 Capturas de Pantalla

### Dashboard
Panel principal con estadísticas del día: cobros realizados, pendientes, clientes activos.

### Cobros
Vista optimizada para cobrar en la calle con botones grandes y confirmación visual.

### Planilla
Vista de impresión con cuotas del día y próximos 7 días.

## 🎨 Colores del Sistema

| Estado | Color | Uso |
|--------|-------|-----|
| Pagado/Excelente | 🟢 Verde | #198754 |
| Pendiente/Regular | 🟠 Naranja | #fd7e14 |
| Moroso/Vencido | 🔴 Rojo | #dc3545 |
| Nuevo/Info | 🔵 Azul | #0d6efd |

## 📄 Licencia

Proyecto privado - Todos los derechos reservados.

---

Desarrollado con ❤️ usando Django y Bootstrap 5
