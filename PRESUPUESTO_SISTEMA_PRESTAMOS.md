# 📋 PRESUPUESTO PROFESIONAL
## Sistema de Gestión de Préstamos "Préstamos"

---

**Proveedor:** ITU Devs  
**Cliente:** _________________________________  
**Fecha de Emisión:** 9 de febrero de 2026  
**Validez del Presupuesto:** 30 días  
**Nº Presupuesto:** PRE-2026-001

---

## 1. DESCRIPCIÓN DEL PROYECTO

Sistema web completo de gestión de préstamos, diseñado con enfoque Mobile-First (PWA), optimizado para uso en campo mediante dispositivos móviles. Permite la administración integral de préstamos, clientes, cobros y reportes.

---

## 2. ALCANCE FUNCIONAL DEL SISTEMA

### 2.1 Módulo de Préstamos
| Funcionalidad | Descripción |
|---------------|-------------|
| Creación de préstamos | Con cálculo automático de intereses y cuotas |
| Frecuencias de pago | Diario, semanal, quincenal, mensual |
| Renovación | Suma automática de saldo pendiente al nuevo monto |
| Estados | Activo, Finalizado, Cancelado, Renovado |
| Historial completo | Trazabilidad de todos los movimientos |

### 2.2 Módulo de Cobros
| Funcionalidad | Descripción |
|---------------|-------------|
| Cobros en tiempo real | Sin recargar página (AJAX) |
| Pagos parciales | Con opciones: ignorar, agregar a próxima cuota, crear cuota especial |
| Vista diaria | Cobros organizados por cliente y ruta |
| Registro de pagos | Con fecha, monto y observaciones |

### 2.3 Módulo de Clientes
| Funcionalidad | Descripción |
|---------------|-------------|
| Gestión completa | Alta, baja, modificación |
| Categorización | Excelente, Regular, Moroso, Nuevo |
| Rutas de cobro | Asignación y organización geográfica |
| Tipos de negocio | Clasificación personalizable |
| Límites de crédito | Por categoría y tipo de cliente |

### 2.4 Módulo de Usuarios y Seguridad
| Rol | Permisos |
|-----|----------|
| **Administrador** | Acceso total: usuarios, configuración, reportes, préstamos |
| **Supervisor** | Gestión de cobros, reportes, consultas |
| **Cobrador** | Solo cobros del día y consultas básicas |

### 2.5 Módulo de Reportes
| Reporte | Descripción |
|---------|-------------|
| Cierre de caja | Resumen diario de cobros y pendientes |
| Planilla de impresión | Formato optimizado para imprimir |
| Reporte general | Estado de cartera, morosidad, proyecciones |
| Dashboard | Métricas en tiempo real |

### 2.6 Características Técnicas
| Característica | Detalle |
|----------------|---------|
| Diseño responsivo | Mobile-First, uso con una mano |
| PWA | Instalable como aplicación en celular |
| Navegación inferior | Estilo app móvil |
| Modo offline | Consultas básicas sin conexión |
| Notificaciones | Alertas de cuotas vencidas |

---

## 3. TECNOLOGÍAS UTILIZADAS

| Componente | Tecnología |
|------------|------------|
| Backend | Python 3.8+ / Django 4.2+ |
| Base de Datos | SQLite (desarrollo) / PostgreSQL (producción) |
| Frontend | HTML5, CSS3, JavaScript ES6+, Bootstrap 5.3 |
| Formularios | Django Crispy Forms + Bootstrap 5 |
| Iconos | Bootstrap Icons |
| Autenticación | Django Auth con perfiles personalizados |

---

## 4. INVERSIÓN - DESARROLLO

### 4.1 Precio Base de Contado

| Concepto | Valor |
|----------|-------|
| Desarrollo completo del sistema | **$500 USD** |
| Descuento por pago de contado | 15% |
| **PRECIO CONTADO** | **$425 USD** |

---

### 4.2 Opciones de Pago en Cuotas (Con Financiamiento)

#### Plan A - 3 Cuotas
| Detalle | Valor |
|---------|-------|
| Capital | $500 USD |
| Interés (10%) | $50 USD |
| **Total a pagar** | **$550 USD** |
| **Cuota mensual** | **$183.33 USD** |

| Cuota | Fecha Vencimiento | Monto |
|-------|-------------------|-------|
| 1ª | Al confirmar | $183.33 USD |
| 2ª | 30 días después | $183.33 USD |
| 3ª | 60 días después | $183.34 USD |

---

#### Plan B - 5 Cuotas ⭐ RECOMENDADO
| Detalle | Valor |
|---------|-------|
| Capital | $500 USD |
| Interés (20%) | $100 USD |
| **Total a pagar** | **$600 USD** |
| **Cuota mensual** | **$120 USD** |

| Cuota | Fecha Vencimiento | Monto |
|-------|-------------------|-------|
| 1ª | Al confirmar | $120 USD |
| 2ª | 30 días después | $120 USD |
| 3ª | 60 días después | $120 USD |
| 4ª | 90 días después | $120 USD |
| 5ª | 120 días después | $120 USD |

---

#### Plan C - 6 Cuotas
| Detalle | Valor |
|---------|-------|
| Capital | $500 USD |
| Interés (30%) | $150 USD |
| **Total a pagar** | **$650 USD** |
| **Cuota mensual** | **$108.33 USD** |

| Cuota | Fecha Vencimiento | Monto |
|-------|-------------------|-------|
| 1ª - 6ª | Mensual | $108.33 USD c/u |

---

#### Plan D - 10 Cuotas
| Detalle | Valor |
|---------|-------|
| Capital | $500 USD |
| Interés (50%) | $250 USD |
| **Total a pagar** | **$750 USD** |
| **Cuota mensual** | **$75 USD** |

| Cuota | Fecha Vencimiento | Monto |
|-------|-------------------|-------|
| 1ª - 10ª | Mensual | $75 USD c/u |

---

## 5. INFRAESTRUCTURA MENSUAL

### 5.1 Opción Económica - $9 USD/mes

| Servicio | Proveedor | Costo Mensual |
|----------|-----------|---------------|
| Servidor VPS (1GB RAM, 25GB SSD) | DigitalOcean | $6.00 USD |
| Base de datos | SQLite (incluido) | $0.00 USD |
| Certificado SSL | Let's Encrypt | $0.00 USD |
| Dominio (.com) | Namecheap | $1.00 USD |
| Backup semanal | Snapshot básico | $2.00 USD |
| **TOTAL MENSUAL** | | **$9.00 USD** |

---

### 5.2 Opción Recomendada - $15 USD/mes

| Servicio | Proveedor | Costo Mensual |
|----------|-----------|---------------|
| Servidor VPS (2GB RAM, 50GB SSD) | DigitalOcean/Vultr | $10.00 USD |
| Base de datos | PostgreSQL (incluido) | $0.00 USD |
| Certificado SSL | Let's Encrypt | $0.00 USD |
| Dominio (.com) | Namecheap | $1.00 USD |
| Backup diario automatizado | | $3.00 USD |
| Monitoreo uptime | UptimeRobot | $1.00 USD |
| **TOTAL MENSUAL** | | **$15.00 USD** |

---

### 5.3 Opción Ultra-Económica - $5 USD/mes

| Servicio | Proveedor | Costo Mensual |
|----------|-----------|---------------|
| Hosting | Railway Free Tier + upgrade mínimo | $4.00 USD |
| Dominio | Freenom (.tk) o subdominio | $0-1.00 USD |
| SSL | Incluido | $0.00 USD |
| **TOTAL MENSUAL** | | **$5.00 USD** |

*Nota: Limitado a bajo volumen de operaciones*

---

## 6. MANTENIMIENTO (OPCIONAL)

### 6.1 Plan de Mantenimiento Básico - $15 USD/mes

| Servicio Incluido | Frecuencia |
|-------------------|------------|
| Actualizaciones de seguridad | Mensual |
| Backup verificado | Semanal |
| Monitoreo de disponibilidad | 24/7 |
| Soporte por WhatsApp/Email | Horario laboral |
| Corrección de bugs menores | Ilimitado |
| Reporte de estado | Mensual |

---

### 6.2 Sin Contrato de Mantenimiento

| Servicio | Costo |
|----------|-------|
| Soporte por incidencia | $25 USD/hora |
| Corrección de bugs críticos | $35 USD/hora |
| Nuevas funcionalidades | A cotizar |

*El sistema puede operar sin mantenimiento contratado*

---

## 7. ENTREGABLES

| Nº | Entregable | Formato |
|----|------------|---------|
| 1 | Sistema web completo funcionando | Instalado en servidor |
| 2 | Código fuente completo | Repositorio Git |
| 3 | Base de datos configurada | PostgreSQL/SQLite |
| 4 | Usuarios iniciales creados | Admin + usuarios de prueba |
| 5 | Manual de usuario | PDF / Video |
| 6 | Capacitación | 1 hora por videollamada |
| 7 | Documentación técnica | README + comentarios en código |

---

## 8. CRONOGRAMA DE ENTREGA

| Fase | Actividad | Duración | Entrega |
|------|-----------|----------|---------|
| 1 | Confirmación y pago inicial | Día 0 | - |
| 2 | Configuración de servidor | 1-2 días | Acceso a servidor |
| 3 | Despliegue del sistema | 1-2 días | Sistema en línea |
| 4 | Configuración inicial | 1 día | Datos de prueba |
| 5 | Capacitación | Acordar | Sesión grabada |
| **Total** | | **3-5 días hábiles** | |

---

## 9. CONDICIONES COMERCIALES

### 9.1 Formas de Pago Aceptadas
- Transferencia bancaria nacional
- PayPal
- Criptomonedas (USDT, BTC)
- Efectivo (según ubicación)
- Western Union / MoneyGram

### 9.2 Política de Pagos en Cuotas
- **Primera cuota:** Requerida para iniciar el proyecto
- **Siguientes cuotas:** Vencen cada 30 días calendario
- **Mora por atraso:** 5% adicional por cada semana de retraso
- **Suspensión:** Acceso suspendido con más de 30 días de mora
- **Cancelación anticipada:** Descuento del 5% sobre saldo pendiente

### 9.3 Garantía
- 30 días de soporte post-entrega incluido
- Corrección de bugs sin costo adicional durante garantía
- 1 ajuste menor incluido (cambio de colores, textos, logo)

### 9.4 Exclusiones
- Hosting e infraestructura (se cotiza aparte)
- Contenido (logos, textos, imágenes del cliente)
- Nuevas funcionalidades no especificadas
- Capacitación adicional

---

## 10. RESUMEN DE INVERSIÓN

### Opción Contado + Infraestructura Económica

| Concepto | Único | Mensual |
|----------|-------|---------|
| Desarrollo (15% desc.) | $425 USD | - |
| Infraestructura | - | $9 USD |
| Mantenimiento | - | $0 (opcional) |
| **Inversión inicial** | **$434 USD** | |
| **Costo mensual** | | **$9 USD** |

---

### Opción 5 Cuotas + Infraestructura Recomendada ⭐

| Concepto | Cuota 1 | Cuotas 2-5 | Mensual posterior |
|----------|---------|------------|-------------------|
| Desarrollo | $120 USD | $120 USD | - |
| Infraestructura | $15 USD | $15 USD | $15 USD |
| **Total** | **$135 USD** | **$135 USD** | **$15 USD** |

| Resumen Total Plan 5 Cuotas |  |
|-----------------------------|--|
| Total desarrollo | $600 USD |
| Total infraestructura (5 meses) | $75 USD |
| **Gran Total** | **$675 USD** |

---

## 11. COMPARATIVA DE PLANES

| Plan | Cuotas | Cuota/Mes | Total Dev | Interés | Ahorro vs 10 cuotas |
|------|--------|-----------|-----------|---------|---------------------|
| **Contado** | 1 | $425 | $425 | 0% | $325 USD |
| **3 Cuotas** | 3 | $183.33 | $550 | 10% | $200 USD |
| **5 Cuotas** | 5 | $120 | $600 | 20% | $150 USD |
| **6 Cuotas** | 6 | $108.33 | $650 | 30% | $100 USD |
| **10 Cuotas** | 10 | $75 | $750 | 50% | - |

---

## 12. ACEPTACIÓN DEL PRESUPUESTO

**Plan seleccionado:**

☐ Contado ($425 USD)  
☐ 3 Cuotas ($550 USD)  
☐ 5 Cuotas ($600 USD) ⭐  
☐ 6 Cuotas ($650 USD)  
☐ 10 Cuotas ($750 USD)

**Infraestructura:**

☐ Ultra-económica ($5/mes)  
☐ Económica ($9/mes)  
☐ Recomendada ($15/mes) ⭐

**Mantenimiento:**

☐ Sin contrato  
☐ Básico ($15/mes)

---

**Cliente:**

Nombre: _________________________________

Documento/ID: _________________________________

Teléfono: _________________________________

Email: _________________________________

Firma: _________________________________

Fecha: _________________________________

---

**Proveedor:**

Nombre: ITU Devs

Representante: _________________________________

Firma: _________________________________

Fecha: 9 de febrero de 2026

---

## 13. CONTACTO

| Medio | Información |
|-------|-------------|
| Email | [correo@itudevs.com] |
| WhatsApp | [+XX XXX XXX XXXX] |
| Horario | Lunes a Viernes, 9:00 - 18:00 |

---

*Este presupuesto tiene validez de 30 días a partir de la fecha de emisión. Los precios están expresados en dólares estadounidenses (USD). No incluye impuestos aplicables según jurisdicción del cliente.*

**© 2026 ITU Devs - Todos los derechos reservados**
