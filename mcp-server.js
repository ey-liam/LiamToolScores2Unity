const http = require('http');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

const PORT = parseInt(process.env.LIAM_SCORES_MCP_PORT || '17421', 10);
const ROOT_DIR = __dirname;
const HTML_PATH = path.join(ROOT_DIR, 'index.html');

let commandSeq = 1;
const commandQueue = [];
const pendingResolvers = new Map();
const waitingPolls = [];
let lastBrowserSeen = 0;

function enqueueBrowserCommand(action, params = {}, timeoutMs = 15000) {
    return new Promise(async (resolve) => {
        if (Date.now() - lastBrowserSeen > 6000) {
            openBrowserIfNeeded();
            await waitForBrowserConnection(8000);
        }

        const id = 'cmd_' + (commandSeq++) + '_' + Date.now();
        const item = { id, command: { action, params } };

        const timer = setTimeout(() => {
            pendingResolvers.delete(id);
            resolve({
                ok: false,
                error: 'Timeout esperando respuesta de la ventana de LiamToolScores2Unity en http://127.0.0.1:' + PORT
            });
        }, timeoutMs);

        pendingResolvers.set(id, (result) => {
            clearTimeout(timer);
            resolve(result);
        });

        if (waitingPolls.length > 0) {
            const pollRes = waitingPolls.shift();
            sendJson(pollRes, 200, item);
        } else {
            commandQueue.push(item);
        }
    });
}

function waitForBrowserConnection(maxWaitMs) {
    return new Promise((resolve) => {
        const start = Date.now();
        const check = () => {
            if (Date.now() - lastBrowserSeen < 4000) return resolve(true);
            if (Date.now() - start >= maxWaitMs) return resolve(false);
            setTimeout(check, 250);
        };
        check();
    });
}

let browserLaunchAttempted = 0;
function openBrowserIfNeeded() {
    if (Date.now() - browserLaunchAttempted < 10000) return;
    browserLaunchAttempted = Date.now();
    const url = `http://127.0.0.1:${PORT}/`;
    if (process.platform === 'win32') {
        exec(`start "" "${url}"`);
    } else if (process.platform === 'darwin') {
        exec(`open "${url}"`);
    } else {
        exec(`xdg-open "${url}"`);
    }
}

function sendJson(res, status, obj) {
    const body = JSON.stringify(obj);
    res.writeHead(status, {
        'Content-Type': 'application/json; charset=utf-8',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Private-Network': 'true'
    });
    res.end(body);
}

const MCP_TOOLS = [
    {
        name: 'scores_capture_screenshot',
        description: 'Toma una captura PNG en tiempo real del viewport del ScoringFX en el navegador para que la IA inspeccione visualmente el texto, los colores, los rayos aditivos y las partículas.',
        inputSchema: {
            type: 'object',
            properties: {
                feedback: { 
                    type: 'string', 
                    enum: ['Perfect', 'Super', 'Good', 'Ok', 'Bad', 'Gold', 'GoldMiss'],
                    description: 'Nombre del feedback a capturar (por defecto el activo).'
                },
                time: { 
                    type: 'number', 
                    description: 'Tiempo en segundos a inspeccionar (o dejar vacío para el clímax visual).'
                },
                background: { 
                    type: 'string', 
                    enum: ['dark', 'jd', 'check', 'black', 'white'],
                    default: 'jd'
                }
            }
        }
    },
    {
        name: 'scores_get_state',
        description: 'Obtiene el estado completo de la herramienta: plantilla cargada, lista de las 21 plantillas disponibles, feedback activo, capas de texto, partículas y parámetros globales.',
        inputSchema: {
            type: 'object',
            properties: {}
        }
    },
    {
        name: 'scores_load_template',
        description: 'Carga una de las 21 plantillas originales extraídas de Just Dance Next (Spine 4.0).',
        inputSchema: {
            type: 'object',
            properties: {
                templateName: {
                    type: 'string',
                    description: 'Nombre de la plantilla (ej: Basic, Neon, Aqua, Candy, Flamepassion, TropicalPlants, etc.)'
                }
            },
            required: ['templateName']
        }
    },
    {
        name: 'scores_customize_feedback',
        description: 'Personaliza instantáneamente el texto, tipografía, colores (degradado, doble contorno, resplandor exterior glow) o escala de tiempo de cualquiera de los feedbacks.',
        inputSchema: {
            type: 'object',
            properties: {
                feedback: {
                    type: 'string',
                    enum: ['Perfect', 'Super', 'Good', 'Ok', 'Bad', 'Gold', 'GoldMiss'],
                    description: 'Elemento a modificar.'
                },
                text: { type: 'string', description: 'Texto que se mostrará (ej: PERFECT, GENIAL, COOL).' },
                font: { type: 'string', description: 'Fuente (ej: JustDanceBold, Arial Black, Impact).' },
                primaryColor: { type: 'string', description: 'Color primario en hex (ej: #22d3ee).' },
                secondaryColor: { type: 'string', description: 'Color secundario inferior del degradado (ej: #ffffff).' },
                strokeColor: { type: 'string', description: 'Color del contorno principal (ej: #02131a).' },
                strokeWidth: { type: 'number', description: 'Grosor del contorno (px).' },
                glowColor: { type: 'string', description: 'Color del resplandor glow (ej: #22d3ee).' },
                glowBlur: { type: 'number', description: 'Radio de difusión del glow (px).' },
                extrudeDepth: { type: 'number', description: 'Profundidad de extrusión 3D simulada.' },
                timeScale: { type: 'number', description: 'Velocidad de reproducción (1.0 = normal).' },
                includeScreenshot: { type: 'boolean', default: true }
            },
            required: ['feedback']
        }
    },
    {
        name: 'scores_configure_particles',
        description: 'Añade o configura partículas y rayos de fondo para un feedback específico.',
        inputSchema: {
            type: 'object',
            properties: {
                feedback: {
                    type: 'string',
                    enum: ['Perfect', 'Super', 'Good', 'Ok', 'Bad', 'Gold', 'GoldMiss']
                },
                shape: {
                    type: 'string',
                    enum: ['Estrella', 'Rombo', 'Rayo', 'Glow', 'Chispa', 'Anillo', 'Nota', 'Corazón'],
                    default: 'Estrella'
                },
                count: { type: 'number', description: 'Cantidad de partículas (ej: 30).' },
                colorA: { type: 'string', description: 'Color inicial en hex.' },
                colorB: { type: 'string', description: 'Color final en hex.' },
                additive: { type: 'boolean', default: true, description: 'Blend aditivo para máxima brillantez.' },
                gravity: { type: 'number', description: 'Gravedad (+ cae, - sube).' },
                speed: { type: 'number', description: 'Velocidad de explosión.' },
                includeScreenshot: { type: 'boolean', default: true }
            },
            required: ['feedback']
        }
    },
    {
        name: 'scores_export_unity_bundle',
        description: 'Compila y guarda en disco el paquete oficial Spine 4.0.64 para Just Dance Next (ScoringFX_<Nombre>.{skel,atlas,png}, miniatura 256x256, catalog_item.json y SHA256SUMS.txt) y opcionalmente el paquete standalone LiamFX.',
        inputSchema: {
            type: 'object',
            properties: {
                outputDir: {
                    type: 'string',
                    description: 'Ruta absoluta en disco donde guardar la carpeta ScoringFX_<Nombre>/ (ej: C:/Entregas_JDNext).'
                },
                includeLiamFX: {
                    type: 'boolean',
                    default: false,
                    description: 'Si es true, guarda además una subcarpeta LiamFX_Standalone/ para proyectos Unity independientes.'
                }
            }
        }
    }
];

function buildToolResponseContent(res, extraText) {
    const content = [];
    if (extraText) {
        content.push({ type: 'text', text: extraText });
    }
    if (res && res.screenshot && res.screenshot.dataUrl) {
        const base64Data = res.screenshot.dataUrl.replace(/^data:image\/png;base64,/, '');
        const capturePath = path.join(ROOT_DIR, 'mcp_last_capture.png');
        try {
            fs.writeFileSync(capturePath, Buffer.from(base64Data, 'base64'));
        } catch (e) {}
        content.push({
            type: 'image',
            data: base64Data,
            mimeType: 'image/png'
        });
    }
    const cleanCopy = { ...res };
    if (cleanCopy.screenshot) {
        cleanCopy.screenshot = { captured: true, savedTo: path.join(ROOT_DIR, 'mcp_last_capture.png') };
    }
    content.push({
        type: 'text',
        text: JSON.stringify(cleanCopy, null, 2)
    });
    return { content };
}

async function handleMcpToolCall(name, args) {
    switch (name) {
        case 'scores_capture_screenshot': {
            const res = await enqueueBrowserCommand('capture_screenshot', args);
            if (!res || !res.ok) {
                return {
                    isError: true,
                    content: [{ type: 'text', text: `Error al capturar pantalla: ${res && res.error ? res.error : 'Fallo de comunicación con la ventana'}` }]
                };
            }
            return buildToolResponseContent(res, `Captura exitosa de ScoringFX (${args.feedback || 'actual'})`);
        }

        case 'scores_get_state': {
            const res = await enqueueBrowserCommand('get_state', args);
            if (!res || !res.ok) {
                return {
                    isError: true,
                    content: [{ type: 'text', text: `Error al obtener estado: ${res && res.error ? res.error : 'Ventana no responde'}` }]
                };
            }
            return {
                content: [{ type: 'text', text: JSON.stringify(res.state, null, 2) }]
            };
        }

        case 'scores_load_template': {
            const res = await enqueueBrowserCommand('load_template', args);
            if (!res || !res.ok) {
                return {
                    isError: true,
                    content: [{ type: 'text', text: `Error cargando plantilla: ${res && res.error ? res.error : 'Fallo'}` }]
                };
            }
            return buildToolResponseContent(res, `Plantilla '${args.templateName}' cargada correctamente.`);
        }

        case 'scores_customize_feedback': {
            const res = await enqueueBrowserCommand('customize_feedback', args);
            if (!res || !res.ok) {
                return {
                    isError: true,
                    content: [{ type: 'text', text: `Error al personalizar feedback: ${res && res.error ? res.error : 'Fallo'}` }]
                };
            }
            return buildToolResponseContent(res, `Feedback '${args.feedback}' actualizado correctamente.`);
        }

        case 'scores_configure_particles': {
            const res = await enqueueBrowserCommand('configure_particles', args);
            if (!res || !res.ok) {
                return {
                    isError: true,
                    content: [{ type: 'text', text: `Error configurando partículas: ${res && res.error ? res.error : 'Fallo'}` }]
                };
            }
            return buildToolResponseContent(res, `Partículas para '${args.feedback}' configuradas con éxito.`);
        }

        case 'scores_export_unity_bundle': {
            const res = await enqueueBrowserCommand('export_unity_bundle', args);
            if (!res || !res.ok) {
                return {
                    isError: true,
                    content: [{ type: 'text', text: `Error exportando paquete Unity: ${res && res.error ? res.error : 'Fallo'}` }]
                };
            }

            // Si se indicó un directorio en disco, guardar el paquete Spine 4.0.64 JDNext (y opcionalmente LiamFX)
            if (args.outputDir && res.bundle) {
                try {
                    fs.mkdirSync(args.outputDir, { recursive: true });
                    const folderName = res.bundle.fullName || res.bundle.name || 'ScoringFX_Custom';
                    const targetDir = path.join(args.outputDir, folderName);
                    fs.mkdirSync(targetDir, { recursive: true });

                    if (Array.isArray(res.bundle.spineFiles) && res.bundle.spineFiles.length > 0) {
                        for (const sf of res.bundle.spineFiles) {
                            fs.writeFileSync(path.join(targetDir, sf.fileName), Buffer.from(sf.base64, 'base64'));
                        }
                    }

                    if (args.includeLiamFX) {
                        const lfxDir = path.join(targetDir, 'LiamFX_Standalone');
                        fs.mkdirSync(lfxDir, { recursive: true });
                        fs.writeFileSync(path.join(lfxDir, `${folderName}.lfx.json`), JSON.stringify(res.bundle.lfx, null, 2), 'utf8');
                        if (res.bundle.pages) {
                            for (const page of res.bundle.pages) {
                                const b64 = page.dataUrl.replace(/^data:image\/png;base64,/, '');
                                fs.writeFileSync(path.join(lfxDir, page.file), Buffer.from(b64, 'base64'));
                            }
                        }
                        const unitySrc = path.join(ROOT_DIR, 'Unity');
                        if (fs.existsSync(unitySrc)) {
                            copyRecursiveSync(unitySrc, path.join(lfxDir, 'LiamFX_Runtime'));
                        }
                    }

                    return {
                        content: [{ type: 'text', text: `¡Paquete Spine 4.0.64 para Just Dance Next exportado exitosamente a:\n${targetDir}` }]
                    };
                } catch (saveErr) {
                    return {
                        isError: true,
                        content: [{ type: 'text', text: `Fallo al escribir en disco (${args.outputDir}): ${saveErr.message}` }]
                    };
                }
            }

            return {
                content: [{ type: 'text', text: `Paquete generado en memoria listo para descarga en el navegador (${res.bundle ? res.bundle.name : 'ScoringFX'}).` }]
            };
        }

        default:
            return {
                isError: true,
                content: [{ type: 'text', text: `Herramienta desconocida: ${name}` }]
            };
    }
}

function copyRecursiveSync(src, dest) {
    const exists = fs.existsSync(src);
    const stats = exists && fs.statSync(src);
    const isDirectory = exists && stats.isDirectory();
    if (isDirectory) {
        fs.mkdirSync(dest, { recursive: true });
        fs.readdirSync(src).forEach(childItemName => {
            copyRecursiveSync(path.join(src, childItemName), path.join(dest, childItemName));
        });
    } else {
        fs.copyFileSync(src, dest);
    }
}

async function processJsonRpcMessage(msg) {
    if (!msg || typeof msg !== 'object') return null;

    if (msg.method === 'initialize') {
        return {
            jsonrpc: '2.0',
            id: msg.id,
            result: {
                protocolVersion: '2024-11-05',
                capabilities: { tools: {} },
                serverInfo: {
                    name: 'liam-scores2unity',
                    version: '3.0.0'
                }
            }
        };
    }

    if (msg.method === 'notifications/initialized') {
        return null;
    }

    if (msg.method === 'ping') {
        return { jsonrpc: '2.0', id: msg.id, result: {} };
    }

    if (msg.method === 'tools/list') {
        return {
            jsonrpc: '2.0',
            id: msg.id,
            result: { tools: MCP_TOOLS }
        };
    }

    if (msg.method === 'tools/call') {
        try {
            const p = msg.params || {};
            const toolResult = await handleMcpToolCall(p.name, p.arguments || {});
            return {
                jsonrpc: '2.0',
                id: msg.id,
                result: toolResult
            };
        } catch (err) {
            return {
                jsonrpc: '2.0',
                id: msg.id,
                result: {
                    isError: true,
                    content: [{ type: 'text', text: String(err && err.message ? err.message : err) }]
                }
            };
        }
    }

    if (msg.id !== undefined) {
        return {
            jsonrpc: '2.0',
            id: msg.id,
            error: { code: -32601, message: 'Method not found: ' + msg.method }
        };
    }

    return null;
}

const server = http.createServer((req, res) => {
    if (req.method === 'OPTIONS') {
        res.writeHead(204, {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Private-Network': 'true'
        });
        return res.end();
    }

    const urlObj = new URL(req.url, `http://127.0.0.1:${PORT}`);

    // Servidor de archivos estáticos (index.html, Library, Unity, etc.)
    if (req.method === 'GET') {
        let filePath = path.join(ROOT_DIR, decodeURIComponent(urlObj.pathname));
        if (urlObj.pathname === '/' || urlObj.pathname === '') {
            filePath = HTML_PATH;
        }

        if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
            const ext = path.extname(filePath).toLowerCase();
            const mimeTypes = {
                '.html': 'text/html; charset=utf-8',
                '.js': 'application/javascript; charset=utf-8',
                '.json': 'application/json; charset=utf-8',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.ttf': 'font/ttf',
                '.otf': 'font/otf',
                '.css': 'text/css; charset=utf-8'
            };
            const contentType = mimeTypes[ext] || 'application/octet-stream';
            res.writeHead(200, {
                'Content-Type': contentType,
                'Access-Control-Allow-Origin': '*'
            });
            return res.end(fs.readFileSync(filePath));
        }
    }

    // Long-polling desde el navegador
    if (req.method === 'GET' && urlObj.pathname === '/bridge/poll') {
        lastBrowserSeen = Date.now();
        if (commandQueue.length > 0) {
            const nextCmd = commandQueue.shift();
            return sendJson(res, 200, nextCmd);
        }
        const pollTimer = setTimeout(() => {
            const idx = waitingPolls.indexOf(res);
            if (idx !== -1) waitingPolls.splice(idx, 1);
            sendJson(res, 200, { id: null });
        }, 8000);

        req.on('close', () => {
            clearTimeout(pollTimer);
            const idx = waitingPolls.indexOf(res);
            if (idx !== -1) waitingPolls.splice(idx, 1);
        });

        waitingPolls.push(res);
        return;
    }

    // Resultado devuelto por el navegador
    if (req.method === 'POST' && urlObj.pathname === '/bridge/result') {
        lastBrowserSeen = Date.now();
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', () => {
            try {
                const parsed = JSON.parse(body);
                if (parsed && parsed.id && pendingResolvers.has(parsed.id)) {
                    const resolve = pendingResolvers.get(parsed.id);
                    pendingResolvers.delete(parsed.id);
                    resolve(parsed.result);
                }
                sendJson(res, 200, { ok: true });
            } catch (e) {
                sendJson(res, 400, { ok: false });
            }
        });
        return;
    }

    // Endpoint HTTP directo para llamadas MCP JSON-RPC
    if (req.method === 'POST' && urlObj.pathname === '/mcp') {
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', async () => {
            try {
                const msg = JSON.parse(body);
                const reply = await processJsonRpcMessage(msg);
                if (reply) sendJson(res, 200, reply);
                else {
                    res.writeHead(202, { 'Access-Control-Allow-Origin': '*' });
                    res.end();
                }
            } catch (e) {
                sendJson(res, 400, { jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Parse error' } });
            }
        });
        return;
    }

    sendJson(res, 404, { error: 'Not found: ' + urlObj.pathname });
});

server.on('error', (err) => {
    // Si el puerto está en uso, se silencia para no interrumpir stdio
});
server.listen(PORT, '127.0.0.1');

// Comunicación por STDIO para cliente MCP (Antigravity / Claude / Cursor)
let stdioBuffer = Buffer.alloc(0);
let useHeaderFraming = false;

function writeStdioResponse(obj) {
    if (!obj) return;
    const json = JSON.stringify(obj);
    if (useHeaderFraming) {
        const byteLen = Buffer.byteLength(json, 'utf8');
        process.stdout.write(`Content-Length: ${byteLen}\r\n\r\n${json}`);
    } else {
        process.stdout.write(json + '\n');
    }
}

process.stdin.on('data', async (chunk) => {
    stdioBuffer = Buffer.concat([stdioBuffer, chunk]);

    while (stdioBuffer.length > 0) {
        const str = stdioBuffer.toString('utf8');
        if (str.startsWith('Content-Length:')) {
            useHeaderFraming = true;
            const headerEnd = stdioBuffer.indexOf('\r\n\r\n');
            if (headerEnd === -1) break;
            const headerStr = stdioBuffer.slice(0, headerEnd).toString('utf8');
            const m = headerStr.match(/Content-Length:\s*(\d+)/i);
            const len = m ? parseInt(m[1], 10) : 0;
            const totalNeeded = headerEnd + 4 + len;
            if (stdioBuffer.length < totalNeeded) break;
            const bodyBuf = stdioBuffer.slice(headerEnd + 4, totalNeeded);
            stdioBuffer = stdioBuffer.slice(totalNeeded);
            try {
                const msg = JSON.parse(bodyBuf.toString('utf8'));
                const reply = await processJsonRpcMessage(msg);
                writeStdioResponse(reply);
            } catch (e) {}
        } else {
            const nlIdx = stdioBuffer.indexOf('\n');
            if (nlIdx === -1) break;
            const line = stdioBuffer.slice(0, nlIdx).toString('utf8').trim();
            stdioBuffer = stdioBuffer.slice(nlIdx + 1);
            if (!line) continue;
            try {
                const msg = JSON.parse(line);
                const reply = await processJsonRpcMessage(msg);
                writeStdioResponse(reply);
            } catch (e) {}
        }
    }
});
