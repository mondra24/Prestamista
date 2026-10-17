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
const fs = require('fs');
const express = require('express');
const QRCode = require('qrcode');
const pino = require('pino');

// Baileys 7 es un módulo ESM: no se puede require(), se carga con import()
// dinámico antes de abrir el primer socket.
let makeWASocket;
let DisconnectReason;
let fetchLatestBaileysVersion;
let useMultiFileAuthState;
async function cargarBaileys() {
    if (makeWASocket) return;
    const baileys = await import('@whiskeysockets/baileys');
    makeWASocket = baileys.default || baileys.makeWASocket;
    ({ DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } = baileys);
}

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

// Evita que dos reintentos simultáneos abran dos sockets a la vez (dos
// sockets sobre la misma sesión se pelean y WhatsApp corta ambos).
let reconectando = false;

async function iniciarConexion() {
    if (reconectando) return;
    reconectando = true;
    try {
        await abrirSocket();
    } finally {
        reconectando = false;
    }
}

// Estado de entrega de los últimos mensajes mandados (id → estado). Baileys
// devuelve éxito apenas el mensaje sale del socket, pero eso no significa que
// WhatsApp lo haya aceptado ni que le haya llegado a la persona: la
// confirmación llega después por messages.update.
const ESTADOS = { 0: 'error', 1: 'pendiente', 2: 'enviado', 3: 'entregado', 4: 'leido', 5: 'leido' };
const entregas = new Map();
const MAX_ENTREGAS = 500;

function registrarEntrega(id, estadoNuevo) {
    if (!id) return;
    const actual = entregas.get(id);
    if (!actual) {
        if (entregas.size >= MAX_ENTREGAS) entregas.delete(entregas.keys().next().value);
        entregas.set(id, { estado: estadoNuevo, actualizado: Date.now() });
        return;
    }
    actual.estado = estadoNuevo;
    actual.actualizado = Date.now();
}

async function abrirSocket() {
    await cargarBaileys();
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

    // WhatsApp rechaza (error 405) las versiones de protocolo viejas y en ese
    // caso nunca se genera el QR. Si no se puede consultar la última versión,
    // se sigue con la que trae la librería.
    let version;
    try {
        ({ version } = await fetchLatestBaileysVersion());
    } catch (e) {
        logger.warn({ err: e }, 'No se pudo consultar la última versión de WhatsApp Web');
    }

    if (sock) {
        sock.ev.removeAllListeners();
        try { sock.end(undefined); } catch (e) { /* ya estaba cerrado */ }
    }

    sock = makeWASocket({
        auth: state,
        logger,
        printQRInTerminal: false,
        ...(version ? { version } : {}),
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('messages.update', (updates) => {
        for (const { key, update } of updates) {
            if (!key || !key.fromMe || !entregas.has(key.id)) continue;
            if (update && update.status !== undefined) {
                registrarEntrega(key.id, ESTADOS[update.status] || String(update.status));
            }
        }
    });

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
                // El usuario desvinculó el dispositivo (desde el celular o
                // con "Desvincular"), o WhatsApp lo hizo solo por
                // inactividad. No hay sesión que recuperar: se borran las
                // credenciales viejas y se abre una conexión limpia, que es
                // la que genera el QR nuevo. Sin esto el QR no volvía a
                // aparecer hasta reiniciar el servicio.
                estado.telefono = null;
                estado.qrDataUrl = null;
                logger.warn('Sesión de WhatsApp cerrada, se genera un nuevo QR');
                try {
                    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
                } catch (e) {
                    logger.error({ err: e }, 'No se pudo borrar la sesión vieja');
                }
                setTimeout(() => iniciarConexion().catch((err) => {
                    logger.error({ err }, 'Error al reiniciar la conexión');
                }), 1000);
            } else {
                // Corte de red u otro problema transitorio: reintentar.
                logger.warn({ statusCode }, 'Conexión perdida, reintentando');
                setTimeout(() => iniciarConexion().catch((err) => {
                    logger.error({ err }, 'Error al reintentar la conexión');
                }), 3000);
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

// Estado real de entrega de un mensaje ya mandado por /send.
app.get('/message/:id', (req, res) => {
    const e = entregas.get(req.params.id);
    if (!e) return res.status(404).json({ success: false, message: 'Mensaje desconocido' });
    res.json({ success: true, status: e.estado });
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

/**
 * WhatsApp identifica a los celulares argentinos con un "9" después del 54
 * (ej: 549 11 1234-5678), aunque nadie lo marque así al llamar. Si el número
 * llega sin el 54 completo, el JID queda mal armado y Baileys lo acepta
 * igual (devuelve message_id) pero el mensaje nunca le llega a nadie — no
 * tira error, se pierde en silencio. Los números de clientes se cargan en
 * formato local (ej. "1123866766"), así que hay que completarlos acá.
 */
function normalizarNumeroAR(numero) {
    let digitos = String(numero).replace(/\D/g, '');
    if (digitos.startsWith('0')) digitos = digitos.substring(1);
    if (digitos.startsWith('549')) return digitos;
    if (digitos.startsWith('54')) return '549' + digitos.substring(2);
    return '549' + digitos;
}

app.post('/send', async (req, res) => {
    if (!estado.conectado || !sock) {
        return res.status(409).json({ success: false, message: 'WhatsApp no está conectado' });
    }

    const { to, message } = req.body || {};
    if (!to || !message) {
        return res.status(400).json({ success: false, message: 'Faltan "to" o "message"' });
    }

    const digitos = normalizarNumeroAR(to);
    if (!digitos) {
        return res.status(400).json({ success: false, message: 'Número inválido' });
    }
    const jid = `${digitos}@s.whatsapp.net`;

    try {
        const resultado = await sock.sendMessage(jid, { text: message });
        const messageId = resultado && resultado.key ? resultado.key.id : null;
        registrarEntrega(messageId, 'pendiente');
        res.json({ success: true, message_id: messageId });
    } catch (e) {
        logger.error({ err: e }, 'Error al enviar mensaje');
        res.status(502).json({ success: false, message: 'No se pudo enviar el mensaje' });
    }
});

app.listen(PORT, () => {
    logger.info(`Bridge de WhatsApp escuchando en el puerto ${PORT}`);
});
