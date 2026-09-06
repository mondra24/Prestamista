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

**Conclusión: sí, las tres cosas son técnicamente viables.** El punto que define costo y complejidad es qué tipo de firma se usa.

### 2.1 PDF automático de contrato y pagaré — sin complicaciones
Se generan con una librería estándar de Python (ej. WeasyPrint) a partir de un template HTML con los datos del préstamo (cliente, monto, cuotas, tasa, fechas). El pagaré debe incluir los requisitos legales del Decreto-Ley 5965/63 (denominación "pagaré", promesa incondicional de pago, plazo, lugar de pago, fecha y lugar de emisión). **El texto legal exacto del contrato y del pagaré lo debe validar un abogado/contador de Thomas** — nosotros lo integramos en el sistema, no redactamos el contenido legal.

### 2.2 Firma — dos caminos posibles

| | Firma electrónica propia (in-app) | Proveedor externo (ZapSign, VaFirma, Signia, etc.) |
|---|---|---|
| **Cómo funciona** | Cliente firma con el dedo en la pantalla del celular del cobrador (canvas táctil) + se registra evidencia: hash del PDF, IP, fecha/hora, geolocalización, y opcionalmente un código OTP enviado por WhatsApp (aprovechando el número que Thomas ya habilitó) | Se sube el documento a la API del proveedor, que gestiona el flujo de firma y devuelve el PDF firmado con certificado de integridad |
| **Validez legal** | Firma electrónica simple (Art. 288 Código Civil y Comercial) — válida, pero si se cuestiona la firma, quien la invoca debe poder probar autoría e integridad. Por eso conviene reforzar con evidencia (OTP + hash + geolocalización) | Los proveedores serios cumplen automáticamente los requisitos de validez y entregan certificado de integridad — menos riesgo legal para Thomas |
| **Costo recurrente** | Ninguno (queda todo en el propio sistema) | Sí, por documento firmado o por suscripción mensual (ronda entre USD 6 y USD 16/mes en los planes de entrada, según proveedor y volumen — a confirmar con cotización directa al proveedor porque no publican precios fijos para Argentina) |
| **Tiempo de desarrollo** | Mayor (hay que construir la captura, la evidencia y el flujo de verificación) | Menor (es principalmente integración de API) |
| **Dependencia de terceros** | Ninguna | Sí — si el proveedor cambia precios/API o da de baja el servicio, hay que migrar |

**Recomendación:** para el volumen y tipo de operación de PrestaFácil (préstamos chicos, cobro en la calle, cliente presente físicamente con el cobrador), la **firma propia con OTP por WhatsApp** es la opción más costo-efectiva a mediano plazo, porque no genera costo por documento y aprovecha el WhatsApp que Thomas ya está habilitando. La opción de proveedor externo tiene sentido si se prioriza velocidad de entrega o se quiere el respaldo legal de un tercero certificador.

**Importante:** ninguna de las dos opciones es "firma digital" en el sentido estricto de la Ley 25.506 (la que requiere certificado emitido por una Autoridad Certificante licenciada y token). Esa variante da máxima validez legal pero es cara e impráctica para este caso de uso (no tiene sentido pedirle a cada cliente que tramite un certificado digital para firmar un préstamo). Se recomienda **no** ir por ese camino salvo que Thomas tenga un requisito legal específico que lo exija.

---

## 3. ALCANCE Y ESTIMACIÓN DE HORAS

Cotizado a **$7 USD/hora** (tarifa de Thomas para modificaciones sobre la instancia activa — distinta a la tarifa general de referencia de `CONTEXTO_SISTEMA_PARA_PRESUPUESTOS.md`, sección 6.5, que aplica a clientes nuevos), fraccionable en fases independientes.

| Fase | Ítem | Estimación | Costo |
|---|---|---|---|
| 1 | PDF automático de contrato (template + datos dinámicos + descarga/envío) | 8-12 hs | $56-$84 USD |
| 2 | PDF automático de pagaré (template con requisitos legales) | 4-6 hs | $28-$42 USD |
| 3a | Firma propia: captura táctil + hash + evidencia + OTP por WhatsApp | 20-30 hs | $140-$210 USD |
| 3b | *(alternativa a 3a)* Integración con proveedor externo de firma (API) | 12-18 hs | $84-$126 USD + costo mensual del proveedor |
| 4 | Pruebas end-to-end, ajustes y documentación | 6-8 hs | $42-$56 USD |
| — | **Mantenimiento mensual** (soporte y ajustes menores post-entrega) | — | **$3-4 USD/mes** |

**Paquete recomendado (Fases 1+2+3a+4):** precio especial acordado con Thomas, **tope $180 USD**, + mantenimiento mensual de **$3-4 USD** (soporte y ajustes menores post-entrega).
**Paquete con proveedor externo (Fases 1+2+3b+4):** $210-$308 USD + suscripción mensual del proveedor (a cotizar).

*Nota: el rango de horas de la tabla es la estimación de esfuerzo real; el precio del paquete recomendado es un valor especial para Thomas (tope $180 USD) que no surge de multiplicar horas × tarifa, sino de un acuerdo puntual. Los demás puntos (texto legal, volumen, WhatsApp) siguen pendientes de cerrar — ver sección 4.*

---

## 4. DEFINICIONES PENDIENTES (antes de cerrar precio final)

- Texto definitivo del contrato y del pagaré, validado por un abogado/contador de Thomas.
- Si el pagaré requiere valor de título ejecutivo (cobro judicial) — esto puede exigir asesoramiento legal adicional sobre el mecanismo de firma a usar.
- Volumen estimado de préstamos/mes, para decidir si conviene firma propia (sin costo por documento) o proveedor externo (costo por documento, pero menos desarrollo).
- Estado real de la habilitación de WhatsApp de Thomas (qué API/proveedor está usando) para confirmar que se puede enviar el OTP desde ahí sin costo adicional de mensajería.

---

## 5. CRONOGRAMA ESTIMADO

| Fase | Duración |
|---|---|
| Fases 1+2 (PDFs) | 3-4 días hábiles |
| Fase 3a (firma propia) o 3b (proveedor externo) | 4-6 días hábiles / 2-3 días hábiles |
| Pruebas y ajustes | 1-2 días hábiles |

---

## 6. EXCLUSIONES

- Redacción o validación legal del texto del contrato/pagaré (a cargo de un abogado/contador de Thomas).
- Costo de suscripción del proveedor externo de firma, si se elige esa opción (se cotiza aparte según el proveedor y volumen).
- Costo de mensajería de WhatsApp, si el proveedor que usa Thomas cobra por mensaje enviado.
- El mantenimiento mensual ($3-4 USD) cubre soporte y ajustes menores; no incluye desarrollo de funcionalidades nuevas, que se cotiza aparte.

---

*Presupuesto de referencia sujeto a ajuste una vez definidos los puntos de la sección 4. Precios en dólares estadounidenses (USD), no incluyen impuestos.*

**© 2026 ITU Devs**
