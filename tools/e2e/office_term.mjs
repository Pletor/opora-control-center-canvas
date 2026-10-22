// Types into an office worker's terminal over the office's own WebSocket, the way the browser does.
// Used by oporahub_e2e.py to accept Claude Code's one-time folder-trust prompt on a fresh temp floor.
//   node office_term.mjs <officeUrl> <password> <workerId> <json-encoded keys>
// Run it with the agent-office checkout as cwd so `ws` resolves from its node_modules.
import { createRequire } from 'node:module';
import path from 'node:path';

const [url, password, workerId, keysJson] = process.argv.slice(2);
const require = createRequire(path.join(process.cwd(), 'package.json'));
const WebSocket = require('ws');

const login = await fetch(new URL('/api/login', url), {
  method: 'POST',
  headers: { 'content-type': 'application/json', origin: url },
  body: JSON.stringify({ password }),
});
if (!login.ok) throw new Error(`login ${login.status}`);
const cookie = (login.headers.get('set-cookie') || '').split(';')[0];
const ws = new WebSocket(`${url.replace(/^http/, 'ws')}/ws?name=e2e`, { headers: { cookie, origin: url } });
const keys = JSON.parse(keysJson);
ws.on('open', () => {
  ws.send(JSON.stringify({ t: 'worker.attach', workerId }));
  let i = 0;
  const next = () => {
    if (i >= keys.length) return setTimeout(() => { ws.close(); process.exit(0); }, 500);
    ws.send(JSON.stringify({ t: 'term.input', workerId, data: keys[i++] }));
    setTimeout(next, 700);
  };
  setTimeout(next, 1500);
});
ws.on('error', (e) => { console.error(e.message); process.exit(1); });
setTimeout(() => process.exit(2), 20000);
