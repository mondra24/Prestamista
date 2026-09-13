# Bridge de WhatsApp (número personal)

Servicio interno, separado de Django, que conecta un número de WhatsApp
personal vía QR (multi-dispositivo) y expone una API HTTP mínima para que
el sistema le pida mandar mensajes. Usa [Baileys](https://github.com/WhiskeySockets/Baileys),
una librería **no oficial** — no es la API de Meta Business.

**Riesgo a tener presente:** Meta no aprueba este método. El número puede
quedar baneado sin aviso. Se recomienda usar un número secundario para
esto, no el personal.

## Correr en local

```bash
cd whatsapp-bridge
npm install
BRIDGE_SECRET=un-secreto-cualquiera npm start
```

Con el server corriendo, `GET /qr` (mandando el header `X-Bridge-Secret`)
devuelve un PNG en base64 para escanear desde WhatsApp → Dispositivos
vinculados. Una vez escaneado, `GET /status` pasa a `{"connected": true}`.

## Deploy en Railway

Este servicio va como **segundo servicio dentro del mismo proyecto**
(`Financiera-Thomas`), no reemplaza al servicio `web` de Django:

1. En el proyecto de Railway: **New Service → Deploy from GitHub repo**,
   mismo repo (`mondra24/Prestamista`), pero con **Root Directory** =
   `whatsapp-bridge` (así Railway lo trata como un proyecto Node aparte).
2. Agregar un **Volume** montado en `/data` (o la ruta que se use) y
   setear la variable `AUTH_DIR=/data/auth_session` — sin esto, cada
   redeploy borra la sesión y hay que re-escanear el QR.
3. Variables de entorno del servicio:
   - `BRIDGE_SECRET`: un secreto largo y random (ej. generado con
     `openssl rand -hex 32`). El mismo valor va en el servicio `web` de
     Django como `WHATSAPP_BRIDGE_SECRET`.
   - `AUTH_DIR`: la ruta del Volume del paso 2.
4. **Networking**: dejar este servicio **sin dominio público** (no
   generar un Public Domain en Railway). Django le habla por la red
   privada de Railway usando el hostname interno
   (`<nombre-del-servicio>.railway.internal`) — ver
   `WHATSAPP_BRIDGE_URL` en la configuración de Django.
5. Healthcheck de Railway: apuntar a `/health` (no requiere secreto).

## API

Todas las rutas excepto `/health` requieren el header `X-Bridge-Secret`.

| Método | Ruta          | Descripción                                    |
|--------|---------------|-------------------------------------------------|
| GET    | `/health`     | Sin auth. Para el healthcheck de Railway.       |
| GET    | `/status`     | `{ connected, phone }`                          |
| GET    | `/qr`         | `{ qr, connected }` — `qr` es un PNG en base64  |
| POST   | `/disconnect` | Desvincula el dispositivo                       |
| POST   | `/send`       | `{ to, message }` → `{ success, message_id }`   |
