// EchoLostAndFound · Unity WebGL 产物本地静态服务器（仅用于浏览器测试）
// 归属：DSH。不修改工程；不参与发布。
//
// 用法：node Tools/Build/serve-webgl.mjs <webgl输出目录> [端口]
// 说明：
//   - 对 .br / .gz 自动补 Content-Encoding（Unity Brotli/Gzip 产物按原扩展名存放）
//   - 正确 MIME：.wasm application/wasm，.data/.bundle application/octet-stream，.js text/javascript
//   - 默认禁用缓存，便于反复测试构建产物
//   - 仅当传入 --coep 时才发 COOP/COEP（只有开启多线程 WebGL 才需要；默认开启会拦截子资源）
//   - 关键：python -m http.server 不会补 Content-Encoding，用它测 Brotli 包会白屏

import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { join, extname, normalize, resolve, sep } from 'node:path';

const args = process.argv.slice(2).filter((arg) => arg !== '--coep');
const wantCoep = process.argv.includes('--coep');
const rootArg = args[0];
const port = Number(args[1] ?? 8080);

if (!rootArg) {
  console.error('用法: node Tools/Build/serve-webgl.mjs <webgl输出目录> [端口]');
  process.exit(1);
}

const root = resolve(rootArg);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.wasm': 'application/wasm',
  '.data': 'application/octet-stream',
  '.bundle': 'application/octet-stream',
  '.unityweb': 'application/octet-stream',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
};

const ENCODING = { '.br': 'br', '.gz': 'gzip' };

function resolvePath(urlPath) {
  const clean = decodeURIComponent(urlPath.split('?')[0].split('#')[0]);
  const candidate = resolve(join(root, normalize(clean)));
  if (candidate !== root && !candidate.startsWith(root + sep)) return null;
  return candidate;
}

async function tryFiles(filePath) {
  const candidates = [filePath];
  const ext = extname(filePath);
  if (ext) {
    candidates.push(filePath + '.br', filePath + '.gz');
  } else {
    candidates.push(join(filePath, 'index.html'), join(filePath, 'index.html.br'), join(filePath, 'index.html.gz'));
  }
  for (const c of candidates) {
    try {
      const s = await stat(c);
      if (s.isFile()) return { path: c, size: s.size };
    } catch {
      /* 继续尝试 */
    }
  }
  return null;
}

const server = createServer(async (req, res) => {
  const urlPath = req.url ?? '/';
  const target = resolvePath(urlPath === '/' ? '/index.html' : urlPath);
  if (!target) {
    res.writeHead(403).end('forbidden');
    return;
  }
  const found = await tryFiles(target);
  if (!found) {
    console.log(`404 ${urlPath}`);
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('404 not found');
    return;
  }

  const ext = extname(found.path).toLowerCase();
  const actualExt = ENCODING[ext] ? extname(found.path.slice(0, -ext.length)).toLowerCase() : ext;
  const headers = {
    'Content-Type': MIME[actualExt] ?? 'application/octet-stream',
    'Content-Length': String(found.size),
    'Cache-Control': 'no-store',
  };
  if (wantCoep) {
    headers['Cross-Origin-Opener-Policy'] = 'same-origin';
    headers['Cross-Origin-Embedder-Policy'] = 'require-corp';
    headers['Cross-Origin-Resource-Policy'] = 'cross-origin';
  }
  if (ENCODING[ext]) {
    headers['Content-Encoding'] = ENCODING[ext];
    headers['Vary'] = 'Accept-Encoding';
  }

  try {
    const body = await readFile(found.path);
    console.log(`200 ${urlPath} -> ${found.path.slice(root.length + 1)} (${found.size} B${ENCODING[ext] ? ', ' + ENCODING[ext] : ''})`);
    res.writeHead(200, headers).end(body);
  } catch (err) {
    console.error(`500 ${urlPath}: ${err.message}`);
    res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' }).end('500');
  }
});

server.listen(port, '127.0.0.1', () => {
  console.log(`WebGL 测试服务器: http://127.0.0.1:${port}/`);
  console.log(`静态根目录: ${root}`);
});

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    console.log('\n停止服务器');
    server.close(() => process.exit(0));
  });
}
