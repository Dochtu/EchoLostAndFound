// 诊断探针：WebGL 构建里 TMP_InputField 的键盘/IME 输入路径。
// node probe-typing.mjs <url> <outDir>
import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { setTimeout as delay } from 'node:timers/promises';

const [url, output] = process.argv.slice(2);
const out = resolve(output);
await mkdir(out, { recursive: true });
const profile = await mkdtemp(join(tmpdir(), 'echo-probe-chrome-'));
const chrome = spawn(process.env.M4C_CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', '--remote-debugging-pipe', '--no-first-run', '--window-size=1200,850',
  '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--mute-audio',
  '--user-data-dir=' + profile, 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'], windowsHide: true });
let seq = 0, sessionId;
const pending = new Map(), consoles = [];
function rpc(method, params = {}, session = sessionId) {
  return new Promise((done, fail) => {
    const id = ++seq;
    const timer = setTimeout(() => { pending.delete(id); fail(Error('Timeout: ' + method)); }, 30000);
    pending.set(id, m => { clearTimeout(timer); m.error ? fail(Error(method + ': ' + m.error.message)) : done(m.result); });
    chrome.stdio[3].write(JSON.stringify({ id, method, params, sessionId: session }) + '\0');
  });
}
let buffer = '';
chrome.stdio[4].setEncoding('utf8').on('data', data => {
  buffer += data;
  for (let cut; (cut = buffer.indexOf('\0')) >= 0;) {
    const msg = JSON.parse(buffer.slice(0, cut));
    buffer = buffer.slice(cut + 1);
    if (pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
    else if (msg.method === 'Runtime.consoleAPICalled') consoles.push(msg.params.args.map(a => a.value ?? a.description).join(' '));
  }
});
const evaluate = async expression => (await rpc('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })).result.value;
async function until(read, seconds) {
  const start = Date.now();
  do { const v = await read(); if (v) return v; await delay(200); } while (Date.now() - start < seconds * 1000);
  return null;
}
const shot = async name => {
  const { data } = await rpc('Page.captureScreenshot', { format: 'png' });
  await writeFile(join(out, name + '.png'), Buffer.from(data, 'base64'));
};
const pages = () => consoles.filter(m => /^M4A page /.test(m));
const report = { url, strategies: [], dom: null, consoles: [] };
try {
  const target = (await rpc('Target.createTarget', { url: 'about:blank' })).targetId;
  sessionId = (await rpc('Target.attachToTarget', { targetId: target, flatten: true })).sessionId;
  for (const api of ['Page', 'Runtime']) await rpc(api + '.enable');
  await rpc('Page.addScriptToEvaluateOnNewDocument', { source: `
    new MutationObserver(() => {
      const bar = document.querySelector('#unity-loading-bar');
      if (bar && bar.style.display === 'none' && !window.m4cLoaderHidden) window.m4cLoaderHidden = performance.now();
    }).observe(document, { subtree: true, attributes: true, childList: true });
  ` });
  await rpc('Page.navigate', { url });
  await until(() => evaluate('window.m4cLoaderHidden'), 240);
  await delay(5000);
  const point = await evaluate("(()=>{const r=document.querySelector('#unity-canvas').getBoundingClientRect();return {x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)}})()");
  const click = async p => {
    await rpc('Input.dispatchMouseEvent', { type: 'mouseMoved', ...p });
    await rpc('Input.dispatchMouseEvent', { type: 'mousePressed', ...p, button: 'left', buttons: 1, clickCount: 1 });
    await delay(100);
    await rpc('Input.dispatchMouseEvent', { type: 'mouseReleased', ...p, button: 'left', clickCount: 1 });
    await delay(500);
  };
  for (let i = 0; i < 3; i += 1) {
    if (await evaluate("document.pointerLockElement?.id === 'unity-canvas'")) break;
    await click(point);
  }
  await rpc('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'e', code: 'KeyE', windowsVirtualKeyCode: 69, nativeVirtualKeyCode: 69 });
  await delay(120);
  await rpc('Input.dispatchKeyEvent', { type: 'keyUp', key: 'e', code: 'KeyE', windowsVirtualKeyCode: 69, nativeVirtualKeyCode: 69 });
  await until(() => pages().some(p => p.includes('老周')), 20);
  const hud = await evaluate(`(()=>{const r=document.querySelector('#unity-canvas').getBoundingClientRect();
    const s=Math.sqrt((r.width/960)*(r.height/600));
    return {x:Math.round(r.x+r.width/2+(-55)*s), y:Math.round(r.y+r.height/2-(78)*s)};})()`);
  await click(hud);
  await delay(400);
  report.dom = await evaluate(`(()=>{const els=[...document.querySelectorAll('input,textarea')];
    return {active:document.activeElement?document.activeElement.tagName+':'+(document.activeElement.id||document.activeElement.className):'none',
      count:els.length, items:els.map(e=>({tag:e.tagName,id:e.id,type:e.type,cls:e.className,display:getComputedStyle(e).display,focus:e===document.activeElement,value:e.value}))};})()`);
  await shot('01-focused');
  const key = async (params, ms = 40) => {
    await rpc('Input.dispatchKeyEvent', { type: 'rawKeyDown', ...params });
    await delay(ms);
    await rpc('Input.dispatchKeyEvent', { type: 'keyUp', ...params });
    await delay(150);
  };
  const enter = async () => {
    await rpc('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
    await delay(80);
    await rpc('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  };
  const waitSubmit = async seconds => {
    const before = consoles.length;
    for (let i = 0; i < seconds * 5; i += 1) {
      const hit = consoles.slice(before).find(m => /^M4C free text submit /.test(m));
      if (hit) return hit;
      await delay(200);
    }
    return null;
  };
  const attempt = async (name, type) => {
    const before = consoles.length;
    await type();
    await shot('02-' + name);
    await enter();
    const submit = await waitSubmit(8);
    const status = consoles.slice(before).filter(m => /M4C free text|M4A page/.test(m));
    report.strategies.push({ name, submit, status });
    if (!submit) {
      // 清空输入框，避免污染下一策略
      await rpc('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'a', code: 'KeyA', modifiers: 2, windowsVirtualKeyCode: 65, nativeVirtualKeyCode: 65 });
      await rpc('Input.dispatchKeyEvent', { type: 'keyUp', key: 'a', code: 'KeyA', modifiers: 2, windowsVirtualKeyCode: 65, nativeVirtualKeyCode: 65 });
      await rpc('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Backspace', code: 'Backspace', windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8 });
      await rpc('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Backspace', code: 'Backspace', windowsVirtualKeyCode: 8, nativeVirtualKeyCode: 8 });
      await delay(300);
    }
    return submit;
  };
  // S1：ASCII keydown 带 text
  await attempt('S1-ascii-keydown', async () => {
    for (const ch of 'ab') {
      await rpc('Input.dispatchKeyEvent', { type: 'keyDown', key: ch, code: 'Key' + ch.toUpperCase(), text: ch, unmodifiedText: ch, windowsVirtualKeyCode: ch.charCodeAt(0), nativeVirtualKeyCode: ch.charCodeAt(0) });
      await delay(60);
      await rpc('Input.dispatchKeyEvent', { type: 'keyUp', key: ch, code: 'Key' + ch.toUpperCase(), windowsVirtualKeyCode: ch.charCodeAt(0), nativeVirtualKeyCode: ch.charCodeAt(0) });
      await delay(80);
    }
  });
  // S2：ASCII char 事件
  await attempt('S2-ascii-char', async () => {
    for (const ch of 'cd') await rpc('Input.dispatchKeyEvent', { type: 'char', text: ch, unmodifiedText: ch, key: ch });
    await delay(200);
  });
  // S3：中文 char 事件
  await attempt('S3-chinese-char', async () => {
    for (const ch of '中文') await rpc('Input.dispatchKeyEvent', { type: 'char', text: ch, unmodifiedText: ch, key: ch });
    await delay(200);
  });
  // S4：IME 组合 + insertText
  await attempt('S4-ime-composition', async () => {
    await rpc('Input.imeSetComposition', { text: '灯', selectionStart: 1, selectionEnd: 1 });
    await delay(200);
    await rpc('Input.insertText', { text: '灯亮' });
    await delay(300);
  });
  // S5：直接写入隐藏输入框并派发 input 事件（若 Unity 建了 IME 文本框）
  await attempt('S5-hidden-input', async () => {
    await evaluate(`(()=>{const el=[...document.querySelectorAll('input,textarea')].find(e=>e!==document.activeElement && (e.type==='text'||e.tagName==='TEXTAREA'));
      if(!el) return 'none';
      el.focus(); el.value='灯'; el.dispatchEvent(new Event('input',{bubbles:true})); return 'ok';})()`);
    await delay(400);
  });
  await shot('03-final');
  report.pages = pages().map(c => c.message);
  report.completed = true;
} catch (error) {
  report.failure = String(error);
  await shot('failure').catch(() => {});
  process.exitCode = 1;
} finally {
  report.consoles = consoles.slice(-60);
  await writeFile(join(out, 'probe.json'), JSON.stringify(report, null, 2));
  if (chrome.exitCode === null) chrome.kill();
}
