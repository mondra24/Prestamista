# 🗄️ PrestaFácil - Estructura de Base de Datos

Documentación completa del esquema de base de datos del sistema de préstamos.

---

## 📊 Diagrama de Relaciones (ER)

```mermaid
erDiagram
    AUTH_USER ||--o| PERFIL_USUARIO : "tiene perfil"
    AUTH_USER ||--o{ RUTA_COBRO : "es cobrador"
    AUTH_USER ||--o{ CLIENTE : "gestiona"
    AUTH_USER ||--o{ REGISTRO_AUDITORIA : "genera"
    AUTH_USER ||--o{ NOTIFICACION : "recibe"

    TIPO_NEGOCIO ||--o{ CLIENTE : "clasifica"
    RUTA_COBRO ||--o{ CLIENTE : "pertenece a"

    CLIENTE ||--o{ PRESTAMO : "solicita"

    PRESTAMO ||--o{ CUOTA : "genera"
    PRESTAMO ||--o| PRESTAMO : "renueva desde"

    CUOTA ||--o{ INTERES_MORA : "acumula"

    CONFIG_PLANILLA }o--o{ COLUMNA_PLANILLA : "incluye"

    AUTH_USER {
        int id PK
        string username
        string password
        string email
        bool is_superuser
    }

    PERFIL_USUARIO {
        int id PK
        int user_id FK "→ auth_user (CASCADE)"
        string rol "AD | CO | SU"
        string telefono
        bool activo
        datetime fecha_creacion
    }

    RUTA_COBRO {
        int id PK
        string nombre
        string zona
        int cobrador_id FK "→ auth_user (SET_NULL)"
        string dia_cobro "LU|MA|MI|JU|VI|SA|DO|TD"
        int orden
        bool activa
    }

    TIPO_NEGOCIO {
        int id PK
        string nombre "UNIQUE"
        string descripcion
        bool activo
    }

    CONFIG_CREDITO {
        int id PK
        string categoria "UNIQUE: A|B|C|D"
        decimal monto_minimo
        decimal monto_maximo
        decimal tasa_interes_min
        decimal tasa_interes_max
        int plazo_maximo_dias
        bool requiere_garantia
    }

    CLIENTE {
        int id PK
        int usuario_id FK "→ auth_user (SET_NULL)"
        string cedula "UNIQUE"
        string nombre
        string apellido
        string telefono
        string direccion
        int tipo_negocio_id FK "→ tipo_negocio (SET_NULL)"
        string nombre_negocio
        string categoria "A|B|C|D"
        decimal limite_credito
        int ruta_cobro_id FK "→ ruta_cobro (SET_NULL)"
        string dia_pago_preferido
        bool activo
        datetime fecha_registro
    }

    PRESTAMO {
        int id PK
        int cliente_id FK "→ cliente (PROTECT)"
        decimal monto
        decimal tasa_interes
        int cuotas_pactadas
        string frecuencia_pago "DI|SE|QU|ME"
        decimal monto_cuota
        decimal monto_total
        decimal saldo_pendiente
        string estado "AC|PA|VE|RE|CA"
        date fecha_inicio
        date fecha_finalizacion
        int prestamo_anterior_id FK "→ prestamo (SET_NULL)"
        datetime fecha_creacion
    }

    CUOTA {
        int id PK
        int prestamo_id FK "→ prestamo (CASCADE)"
        int numero_cuota "UNIQUE con prestamo"
        decimal monto_cuota
        decimal monto_pagado
        date fecha_vencimiento
        date fecha_pago
        string estado "PE|PA|PC|VE"
        decimal interes_mora_cobrado
        datetime fecha_creacion
    }

    REGISTRO_AUDITORIA {
        int id PK
        int usuario_id FK "→ auth_user (SET_NULL)"
        string tipo_accion "CR|MO|EL|CO|RE|LO|OT"
        string tipo_modelo
        int modelo_id
        text descripcion
        text datos_anteriores "JSON"
        text datos_nuevos "JSON"
        string ip_address
        datetime fecha_hora
    }

    NOTIFICACION {
        int id PK
        int usuario_id FK "→ auth_user (CASCADE)"
        string tipo "CV|CP|PF|CM|CR|RN|AS|IN"
        string prioridad "AL|ME|BA"
        string titulo
        text mensaje
        string enlace
        bool leida
        datetime fecha_creacion
    }

    CONFIG_MORA {
        int id PK
        string nombre
        decimal porcentaje_diario
        int dias_gracia
        bool aplicar_automaticamente
        decimal monto_minimo_mora
        bool activo
    }

    INTERES_MORA {
        int id PK
        int cuota_id FK "→ cuota (CASCADE)"
        date fecha_calculo
        int dias_mora
        decimal porcentaje_aplicado
        decimal monto_base
        decimal monto_interes
        bool agregado_manualmente
        bool pagado
        date fecha_pago
    }

    CONFIG_RESPALDO {
        int id PK
        string nombre
        bool activo
        int frecuencia_horas
        string ruta_destino
        int mantener_ultimos
        datetime ultimo_respaldo
    }

    COLUMNA_PLANILLA {
        int id PK
        string nombre_columna "UNIQUE"
        string titulo_mostrar
        int orden
        bool visible
        string ancho
    }

    CONFIG_PLANILLA {
        int id PK
        string nombre_empresa
        string titulo_planilla
        bool mostrar_logo
        bool mostrar_totales
        text notas_pie
    }
```

---

## 🔗 Resumen de Relaciones

### Flujo principal del negocio

```
Usuario (cobrador) → gestiona → Clientes → solicitan → Préstamos → generan → Cuotas
```

### Tabla de Foreign Keys

| Tabla Origen | Campo | Tabla Destino | on_delete | Descripción |
|---|---|---|---|---|
| `PerfilUsuario` | `user` | `auth_user` | **CASCADE** | Si se borra el user, se borra el perfil |
| `RutaCobro` | `cobrador` | `auth_user` | **SET_NULL** | Ruta queda sin cobrador asignado |
| `Cliente` | `usuario` | `auth_user` | **SET_NULL** | Cliente queda sin cobrador |
| `Cliente` | `tipo_negocio` | `TipoNegocio` | **SET_NULL** | Cliente queda sin tipo |
| `Cliente` | `ruta_cobro` | `RutaCobro` | **SET_NULL** | Cliente queda sin ruta |
| `Prestamo` | `cliente` | `Cliente` | **PROTECT** | ⛔ No se puede borrar cliente con préstamos |
| `Prestamo` | `prestamo_anterior` | `Prestamo` | **SET_NULL** | Cadena de renovaciones |
| `Cuota` | `prestamo` | `Prestamo` | **CASCADE** | Si se borra préstamo, se borran cuotas |
| `InteresMora` | `cuota` | `Cuota` | **CASCADE** | Si se borra cuota, se borran sus moras |
| `RegistroAuditoria` | `usuario` | `auth_user` | **SET_NULL** | Log permanece sin usuario |
| `Notificacion` | `usuario` | `auth_user` | **CASCADE** | Si se borra user, se borran sus notificaciones |

### Reglas de protección importantes

- 🛡️ **PROTECT en Prestamo → Cliente**: No podés eliminar un cliente que tenga préstamos asociados. Hay que cancelar/eliminar los préstamos primero.
- 🔄 **CASCADE en Cuota → Prestamo**: Al eliminar un préstamo, todas sus cuotas se eliminan automáticamente.
- 🔄 **CASCADE en InteresMora → Cuota**: Al eliminar una cuota, se eliminan sus registros de mora.
- ⚡ **SET_NULL en Cliente → Usuario**: Si se elimina un usuario del sistema, los clientes que tenía asignados quedan sin cobrador pero no se pierden.

---

## 📋 Valores de los campos Choice

### Estados de Préstamo (`Prestamo.estado`)
| Código | Valor | Significado |
|---|---|---|
| `AC` | Activo | Préstamo en curso con cuotas por cobrar |
| `PA` | Pagado | Todas las cuotas fueron cobradas |
| `VE` | Vencido | Tiene cuotas vencidas sin pagar |
| `RE` | Refinanciado | Se renovó en un nuevo préstamo |
| `CA` | Cancelado | Cancelado manualmente |

### Estados de Cuota (`Cuota.estado`)
| Código | Valor | Significado |
|---|---|---|
| `PE` | Pendiente | Aún no se ha cobrado |
| `PA` | Pagada | Cobrada completamente |
| `PC` | Parcialmente Cobrada | Se cobró una parte |
| `VE` | Vencida | Pasó la fecha y no se cobró |

### Frecuencia de Pago (`Prestamo.frecuencia_pago`)
| Código | Valor | Días entre cuotas |
|---|---|---|
| `DI` | Diario | 1 día |
| `SE` | Semanal | 7 días |
| `QU` | Quincenal | 15 días |
| `ME` | Mensual | 30 días |

### Categoría de Cliente (`Cliente.categoria`)
| Código | Significado | Descripción |
|---|---|---|
| `A` | Excelente | Historial impecable de pagos |
| `B` | Bueno | Buen pagador con algún atraso menor |
| `C` | Regular | Atrasos frecuentes |
| `D` | Nuevo | Sin historial |

### Roles de Usuario (`PerfilUsuario.rol`)
| Código | Rol | Permisos |
|---|---|---|
| `AD` | Administrador | Acceso total al sistema |
| `SU` | Supervisor | Gestión de cobros y reportes |
| `CO` | Cobrador | Solo cobros y consultas |

### Tipos de Notificación (`Notificacion.tipo`)
| Código | Significado |
|---|---|
| `CV` | Cuota Vencida |
| `CP` | Cuota por Vencer |
| `PF` | Préstamo Finalizado |
| `CM` | Cliente Moroso |
| `CR` | Cobro Realizado |
| `RN` | Renovación |
| `AS` | Alerta del Sistema |
| `IN` | Información |

### Tipos de Auditoría (`RegistroAuditoria.tipo_accion`)
| Código | Significado |
|---|---|
| `CR` | Creación |
| `MO` | Modificación |
| `EL` | Eliminación |
| `CO` | Cobro |
| `RE` | Renovación |
| `LO` | Login |
| `OT` | Otro |

---

## 📇 Índices de la Base de Datos

| Tabla | Campos del Índice | Tipo |
|---|---|---|
| `Cliente` | `cedula` | UNIQUE |
| `Prestamo` | `-fecha_creacion` | INDEX |
| `Prestamo` | `estado` | INDEX |
| `Prestamo` | `cliente, estado` | INDEX compuesto |
| `Cuota` | `prestamo, numero_cuota` | UNIQUE TOGETHER |
| `Cuota` | `fecha_vencimiento` | INDEX |
| `Cuota` | `estado` | INDEX |
| `Cuota` | `prestamo, estado` | INDEX compuesto |
| `RegistroAuditoria` | `-fecha_hora` | INDEX |
| `RegistroAuditoria` | `tipo_accion` | INDEX |
| `RegistroAuditoria` | `usuario` | INDEX |
| `RegistroAuditoria` | `tipo_modelo, modelo_id` | INDEX compuesto |
| `TipoNegocio` | `nombre` | UNIQUE |
| `ConfigCredito` | `categoria` | UNIQUE |
| `ColumnaPlanilla` | `nombre_columna` | UNIQUE |

---

## 🔢 Conteo de Tablas: 15

| # | Tabla Django | Tabla en PostgreSQL |
|---|---|---|
| 1 | `PerfilUsuario` | `core_perfilusuario` |
| 2 | `RutaCobro` | `core_rutacobro` |
| 3 | `TipoNegocio` | `core_tiponegocio` |
| 4 | `ConfiguracionCredito` | `core_configuracioncredito` |
| 5 | `ColumnaPlanilla` | `core_columnaplanilla` |
| 6 | `ConfiguracionPlanilla` | `core_configuracionplanilla` |
| 7 | `Cliente` | `core_cliente` |
| 8 | `Prestamo` | `core_prestamo` |
| 9 | `Cuota` | `core_cuota` |
| 10 | `RegistroAuditoria` | `core_registroauditoria` |
| 11 | `Notificacion` | `core_notificacion` |
| 12 | `ConfiguracionRespaldo` | `core_configuracionrespaldo` |
| 13 | `ConfiguracionMora` | `core_configuracionmora` |
| 14 | `InteresMora` | `core_interesmora` |
| 15 | `ConfiguracionPlanilla_columnas` | M2M intermedia (auto) |

> ℹ️ Además existen las tablas estándar de Django: `auth_user`, `auth_group`, `auth_permission`, `django_session`, `django_migrations`, `django_content_type`, `django_admin_log`.
