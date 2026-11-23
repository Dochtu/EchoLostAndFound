// Run against a fresh build served by Tools/Build/serve-webgl.mjs.
// node browser-smoke.mjs http://127.0.0.1:8080 <new-evidence-directory>
import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { setTimeout as delay } from 'node:timers/promises';

const [url, output] = process.argv.slice(2);
if (!url || new URL(url).hostname !== '127.0.0.1' || !output) {
  throw new Error('Provide a loopback HTTP URL and a new evidence directory.');
}
const out = resolve(output);
await mkdir(out);
const profile = await mkdtemp(join(tmpdir(), 'echo-m3a-chrome-'));
const chrome = spawn(process.env.M3A_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', '--remote-debugging-pipe', '--no-first-run', '--disable-default-apps',
  '--window-size=1200,850', '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
  '--user-data-dir=' + profile, 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'], windowsHide: true });
let stderr = '';
chrome.stderr.on('data', d => { stderr = (stderr + d).slice(-12000); });
let seq = 0, sessionId;
const pending = new Map(), consoles = [], resources = [], exceptions = [], dialogs = [];
function rpc(method, params = {}, session = sessionId) {
  return new Promise((done, fail) => {
    const id = ++seq;
    const timer = setTimeout(() => { pending.delete(id); fail(Error('Timeout: ' + method)); }, 30000);
    pending.set(id, m => {
      clearTimeout(timer);
      if (m.error) fail(Error(method + ': ' + m.error.message));
      else done(m.result);
    });
    chrome.stdio[3].write(JSON.stringify({ id, method, params, sessionId: session }) + '\0');
  });
}
let buffer = '';
chrome.stdio[4].setEncoding('utf8').on('data', data => {
  buffer += data;
  for (let cut; (cut = buffer.indexOf('\0')) >= 0;) {
    const msg = JSON.parse(buffer.slice(0, cut));
    buffer = buffer.slice(cut + 1);
    if (pending.has(msg.id)) {
      pending.get(msg.id)(msg); pending.delete(msg.id);
    } else if (msg.method === 'Runtime.consoleAPICalled') {
      consoles.push({ type: msg.params.type, message: msg.params.args.map(a => a.value ?? a.description).join(' ') });
    } else if (msg.method === 'Runtime.exceptionThrown') {
      exceptions.push(msg.params.exceptionDetails);
    } else if (msg.method === 'Page.javascriptDialogOpening') {
      dialogs.push(msg.params.message);
      rpc('Page.handleJavaScriptDialog', { accept: true }).catch(() => {});
    } else if (msg.method === 'Network.responseReceived') {
      const { url, status, mimeType, headers } = msg.params.response;
      resources.push({ url, status, mimeType, encoding: headers['Content-Encoding'] });
    }
  }
});
const evaluate = async expression => (await rpc('Runtime.evaluate', { expression, returnByValue: true })).result.value;
async function until(read, seconds) {
  const start = Date.now();
  do { const value = await read(); if (value) return value; await delay(200); } while (Date.now() - start < seconds * 1000);
  throw Error('Timeout waiting for ' + read);
}
const screenshot = async name => {
  const { data } = await rpc('Page.captureScreenshot', { format: 'png' });
  await writeFile(join(out, name + '.png'), Buffer.from(data, 'base64'));
};
async function key(letter, ms = 130) {
  const params = { key: letter, code: 'Key' + letter.toUpperCase(), windowsVirtualKeyCode: letter.toUpperCase().charCodeAt(0) };
  await rpc('Input.dispatchKeyEvent', { type: 'rawKeyDown', ...params });
  await delay(ms);
  await rpc('Input.dispatchKeyEvent', { type: 'keyUp', ...params });
  await delay(350);
}
const results = { url, profile, renderer: 'Chromium headless SwiftShader', resources, consoles, exceptions, dialogs };
try {
  results.browser = (await rpc('Browser.getVersion')).product;
  const target = (await rpc('Target.createTarget', { url: 'about:blank' })).targetId;
  sessionId = (await rpc('Target.attachToTarget', { targetId: target, flatten: true })).sessionId;
  for (const api of ['Page', 'Network', 'Runtime']) await rpc(api + '.enable');
  await rpc('Network.setCacheDisabled', { cacheDisabled: true });
  await rpc('Page.addScriptToEvaluateOnNewDocument', { source: `
    new MutationObserver(() => {
      const bar = document.querySelector('#unity-loading-bar');
      if (bar?.style.display === 'none' && !window.m3aLoaderHidden) window.m3aLoaderHidden = performance.now();
    }).observe(document, { subtree:true, attributes:true, childList:true });
  ` });
  await rpc('Page.navigate', { url });
  results.coldLoadMs = await until(() => evaluate('window.m3aLoaderHidden'), 180);
  results.webgl = await evaluate("(()=>{const g=document.querySelector('#unity-canvas').getContext('webgl2');if(!g)return null;const info=g.getExtension('WEBGL_debug_renderer_info');return {api:g.getParameter(g.VERSION),renderer:info?g.getParameter(info.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER)}})()");
  results.performance = await evaluate("performance.getEntriesByType('resource').map(({name,duration,transferSize,decodedBodySize})=>({name,duration,transferSize,decodedBodySize}))");
  // The default loader resolves before Unity's splash screen hands input to the scene.
  await delay(5000);
  await screenshot('01-station');
  const point = await evaluate("(()=>{let r=document.querySelector('#unity-canvas').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()");
  const mouse = (type, props = {}) => rpc('Input.dispatchMouseEvent', { type, ...point, ...props });
  await mouse('mouseMoved');
  await mouse('mousePressed', { button: 'left', buttons: 1, clickCount: 1 });
  await delay(100);
  await mouse('mouseReleased', { button: 'left', clickCount: 1 });
  results.pointerLocked = await until(() => evaluate("document.pointerLockElement?.id === 'unity-canvas'"), 8);
  await delay(500);
  await key('e');
  await screenshot('02-dialogue');
  if (!consoles.some(c => /Station interaction:/i.test(c.message))) throw Error('Opening NPC did not emit an interaction');
  await key('e');
  await screenshot('03-explore');
  await key('d', 360);
  await screenshot('04-movement');
  await mouse('mouseMoved', { x: point.x + 10, y: point.y + 90 });
  await delay(700);
  await screenshot('05-look');
  await key('e');
  await screenshot('06-clue');
  results.interactions = consoles.filter(c => /Station interaction:/i.test(c.message)).map(c => c.message);
  if (new Set(results.interactions).size < 2) throw Error('Two distinct target interactions were not observed; inspect screenshots');
  if (dialogs.length || exceptions.length || consoles.some(c => c.type === 'error') || resources.some(r => r.status >= 400)) {
    throw Error('Browser errors or HTTP failures; see browser.json');
  }
  results.completed = true;
} catch (error) {
  results.failure = String(error);
  if (sessionId) await screenshot('failure').catch(() => {});
  process.exitCode = 1;
} finally {
  results.stderr = stderr;
  await writeFile(join(out, 'browser.json'), JSON.stringify(results, null, 2));
  if (chrome.exitCode === null) chrome.kill();
}
