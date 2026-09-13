/**
 * Bridge de WhatsApp (número personal, vía QR / multi-dispositivo).
 *
 * Servicio interno, NUNCA expuesto públicamente: puede mandar mensajes en
 * nombre del número vinculado. Django le habla por HTTP usando el secreto
 * compartido en BRIDGE_SECRET (header X-Bridge-Secret).
 *
 * No es la API oficial de Meta — usa Baileys, una librería no oficial que
 * imita al cliente de WhatsApp Web. Ver core/whatsapp_bridge.py del lado
 * de Django para el cliente que consume esta API.
 *
 * Variables de entorno:
 *   BRIDGE_SECRET   obligatorio. Rechaza cualquier pedido sin este header.
 *   AUTH_DIR        dónde persiste la sesión vinculada (default ./auth_session).
 *                    En Railway debe apuntar a un Volume montado, si no,
 *                    cada redeploy pide re-escanear el QR.
 *   PORT            puerto HTTP (default 3000, Railway lo inyecta solo).
 */
const express = require('express');
const QRCode = require('qrcode');
const pino = require('pino');
const {
    default: makeWASocket,
    DisconnectReason,
    useMultiFileAuthState,
} = require('@whiskeysockets/baileys');

const BRIDGE_SECRET = process.env.BRIDGE_SECRET;
const AUTH_DIR = process.env.AUTH_DIR || './auth_session';
const PORT = process.env.PORT || 3000;

if (!BRIDGE_SECRET) {
    console.error('Falta BRIDGE_SECRET en las variables de entorno. No se inicia el servicio.');
    process.exit(1);
}

const logger = pino({ level: process.env.LOG_LEVEL || 'warn' });

// Estado en memoria: la fuente de verdad es Baileys/WhatsApp, esto es solo
// una foto para responder rápido a Django sin bloquear en cada request.
const estado = {
    conectado: false,
    telefono: null,
    qrDataUrl: null,
};

let sock = null;

async function iniciarConexion() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

    sock = makeWASocket({
        auth: state,
        logger,
        printQRInTerminal: false,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            try {
                estado.qrDataUrl = await QRCode.toDataURL(qr);
            } catch (e) {
                logger.error({ err: e }, 'No se pudo generar el PNG del QR');
            }
        }

        if (connection === 'open') {
            estado.conectado = true;
            estado.qrDataUrl = null;
            estado.telefono = sock.user && sock.user.id ? sock.user.id.split(':')[0] : null;
            logger.info('WhatsApp conectado');
        }

        if (connection === 'close') {
            estado.conectado = false;
            const statusCode = lastDisconnect && lastDisconnect.error && lastDisconnect.error.output
                ? lastDisconnect.error.output.statusCode
                : null;
            const deslogueado = statusCode === DisconnectReason.loggedOut;

            if (deslogueado) {
                // El usuario desvinculó el dispositivo desde el celular, o
                // WhatsApp lo desvinculó solo por inactividad prolongada.
                // No hay sesión que recuperar: hay que volver a escanear.
                estado.telefono = null;
                estado.qrDataUrl = null;
                logger.warn('Sesión de WhatsApp cerrada, hace falta un nuevo QR');
            } else {
                // Corte de red u otro problema transitorio: reintentar.
                logger.warn({ statusCode }, 'Conexión perdida, reintentando');
                setTimeout(iniciarConexion, 3000);
            }
        }
    });
}

iniciarConexion().catch((e) => {
    logger.error({ err: e }, 'Error inicial al conectar con WhatsApp');
});

// ---------------- API HTTP ----------------

const app = express();
app.use(express.json());

// Sin secreto: Railway lo usa para el healthcheck del deploy. No expone
// nada sensible (ni siquiera si está conectado o no).
app.get('/health', (req, res) => res.json({ ok: true }));

app.use((req, res, next) => {
    if (req.get('X-Bridge-Secret') !== BRIDGE_SECRET) {
        return res.status(401).json({ success: false, message: 'Secreto inválido' });
    }
    next();
});

app.get('/status', (req, res) => {
    res.json({ connected: estado.conectado, phone: estado.telefono });
});

app.get('/qr', (req, res) => {
    if (estado.conectado) {
        return res.json({ qr: null, connected: true });
    }
    res.json({ qr: estado.qrDataUrl, connected: false });
});

app.post('/disconnect', async (req, res) => {
    try {
        if (sock) {
            await sock.logout();
        }
        res.json({ success: true, message: 'Desvinculado' });
    } catch (e) {
        logger.error({ err: e }, 'Error al desvincular');
        res.status(500).json({ success: false, message: 'Error al desvincular' });
    }
});

app.post('/send', async (req, res) => {
    if (!estado.conectado || !sock) {
        return res.status(409).json({ success: false, message: 'WhatsApp no está conectado' });
    }

    const { to, message } = req.body || {};
    if (!to || !message) {
        return res.status(400).json({ success: false, message: 'Faltan "to" o "message"' });
    }

    const digitos = String(to).replace(/\D/g, '');
    if (!digitos) {
        return res.status(400).json({ success: false, message: 'Número inválido' });
    }
    const jid = `${digitos}@s.whatsapp.net`;

    try {
        const resultado = await sock.sendMessage(jid, { text: message });
        res.json({ success: true, message_id: resultado && resultado.key ? resultado.key.id : null });
    } catch (e) {
        logger.error({ err: e }, 'Error al enviar mensaje');
        res.status(502).json({ success: false, message: 'No se pudo enviar el mensaje' });
    }
});

app.listen(PORT, () => {
    logger.info(`Bridge de WhatsApp escuchando en el puerto ${PORT}`);
});
