# 📋 PRESUPUESTO
## Contrato Automático + Pagaré Online + Firma Electrónica — PrestaFácil

---

**Proveedor:** ITU Devs
**Cliente:** Thomas
**Fecha de Emisión:** 4 de septiembre de 2026
**Validez del Presupuesto:** 30 días
**Nº Presupuesto:** PRE-2026-003

---

## 1. PEDIDO ORIGINAL

Thomas solicitó evaluar la viabilidad de:
1. Generar automáticamente un **PDF del contrato de préstamo** al crear/renovar un préstamo.
2. Emitir un **pagaré online** junto con el contrato.
3. Incorporar **firma digital/electrónica** para que el cliente firme ambos documentos desde la plataforma.

Este desarrollo queda **fuera del alcance acordado originalmente** y se cotiza como funcionalidad nueva sobre la instancia activa.

---

## 2. FACTIBILIDAD TÉCNICA

**Conclusión: sí, las tres cosas son técnicamente viables.**

### 2.1 PDF automático de contrato y pagaré
Se generan con una librería estándar de Python (ej. WeasyPrint) a partir de un template HTML con los datos del préstamo (cliente, monto, cuotas, tasa, fechas). Se usa un texto estándar/genérico de contrato y pagaré (mismo tipo de modelo que usan otras financieras informales) — dado el uso que le va a dar Thomas, no se contempla una revisión legal formal del texto; si en algún momento se necesita, se puede ajustar el template sin problema.

### 2.2 Firma electrónica propia (in-app)
El cliente firma con el dedo en la pantalla del celular del cobrador (canvas táctil). Se registra evidencia de respaldo: hash del PDF, IP, fecha/hora, geolocalización, y opcionalmente un código OTP enviado por WhatsApp (aprovechando el número que Thomas ya habilitó). Esto queda todo dentro del propio sistema, sin depender de ningún proveedor externo ni generar costo por documento firmado.

**Importante:** esto es una firma electrónica simple (Art. 288 Código Civil y Comercial), no una "firma digital" en el sentido estricto de la Ley 25.506 (que requiere certificado de una Autoridad Certificante licenciada). Para el uso que le va a dar Thomas (préstamos chicos, cliente presente con el cobrador) es más que suficiente y evita la complejidad/costo de esa otra vía.

---

## 3. ALCANCE Y ESTIMACIÓN DE HORAS

Cotizado a **$7 USD/hora** (tarifa de Thomas para modificaciones sobre la instancia activa — distinta a la tarifa general de referencia de `CONTEXTO_SISTEMA_PARA_PRESUPUESTOS.md`, sección 6.5, que aplica a clientes nuevos).

| Fase | Ítem | Estimación |
|---|---|---|
| 1 | PDF automático de contrato (template + datos dinámicos + descarga/envío) | 8-12 hs |
| 2 | PDF automático de pagaré (template) | 4-6 hs |
| 3 | Firma propia: captura táctil + hash + evidencia + OTP por WhatsApp | 20-30 hs |
| 4 | Pruebas end-to-end, ajustes y documentación | 6-8 hs |
| — | **Mantenimiento mensual** (soporte y ajustes menores post-entrega) | — |

**Precio del paquete completo (Fases 1+2+3+4):** precio especial acordado con Thomas, **tope $190 USD**, + mantenimiento mensual de **$3-4 USD**.

*Nota: el rango de horas de la tabla es la estimación de esfuerzo real; el precio final es un valor especial para Thomas (tope $190 USD) que no surge de multiplicar horas × tarifa, sino de un acuerdo puntual.*

---

## 4. DEFINICIONES PENDIENTES

- Volumen estimado de préstamos/mes (para dimensionar el uso, no cambia el precio del paquete).
- Estado real de la habilitación de WhatsApp de Thomas (qué API/proveedor está usando) para confirmar que se puede enviar el OTP desde ahí sin costo adicional de mensajería.

---

## 5. CRONOGRAMA ESTIMADO

| Fase | Duración |
|---|---|
| Fases 1+2 (PDFs) | 3-4 días hábiles |
| Fase 3 (firma propia) | 4-6 días hábiles |
| Pruebas y ajustes | 1-2 días hábiles |

---

## 6. EXCLUSIONES

- Costo de mensajería de WhatsApp, si el proveedor que usa Thomas cobra por mensaje enviado.
- El mantenimiento mensual ($3-4 USD) cubre soporte y ajustes menores; no incluye desarrollo de funcionalidades nuevas, que se cotiza aparte.

---

*Presupuesto de referencia sujeto a ajuste una vez definidos los puntos de la sección 4. Precios en dólares estadounidenses (USD), no incluyen impuestos.*

**© 2026 ITU Devs**
