// node js/test.mjs: JavaScript must reproduce the shared vectors (made by py/tests/make_vectors.py) byte for byte.
import { existsSync, readFileSync, readdirSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { canonString, parse, hash, ID_KEY } from './canon.js';
import { Ledger, publicKey, sign, verify, message, newLedger, Invalid } from './core.js';
import { state } from './state.js';
import { pages } from './render.js';
import { buildGen, makeDex } from './dexweb.js';
import * as ed from './ed25519.js';
import { unhex, hex } from './sha.js';

const V = join(dirname(fileURLToPath(import.meta.url)), '..', 'vectors');
const json = (p) => JSON.parse(readFileSync(join(V, p), 'utf8'));
let passed = 0, failed = 0;
function ok(cond, name) {
  if (cond) passed++; else { failed++; console.log('FAIL ' + name); }
}

for (const r of json('ed25519.json').vectors) {
  const sk = unhex(r.secret), m = unhex(r.message), s = unhex(r.signature);
  ok(hex(ed.publicKey(sk)) === r.public && hex(ed.sign(sk, m)) === r.signature && ed.verify(unhex(r.public), m, s) &&
     !ed.verify(unhex(r.public), new Uint8Array([...m, 1]), s), 'ed25519 ' + r.public.slice(0, 8));
}

const enc = new TextEncoder();
for (const c of json('canon.json')) {
  let accepted;
  try { parse(enc.encode(c.input)); accepted = true; } catch (e) { accepted = false; }
  ok(accepted === c.ok, 'canon ' + c.input);
}

for (const s of json('signatures.json')) {
  const secret = unhex(s.secret);
  ok(publicKey(secret) === s.public && canonString(s.value) === s.canon && hash(s.value) === s.hash &&
     sign(secret, s.value) === s.sig && verify(s.public, s.value, s.sig), 'signature ' + s.canon);
}

const ledgers = {};
for (const f of readdirSync(join(V, 'ledgers')).filter((f) => f.endsWith('.jsonl')).sort()) {
  ledgers[f.slice(0, -6)] = new Uint8Array(readFileSync(join(V, 'ledgers', f)));
}
for (const f of readdirSync(join(V, 'ledgers')).filter((f) => f.endsWith('.json')).sort()) {
  const x = json(join('ledgers', f));
  const root = x.root ? new Ledger(ledgers[x.root]) : null;
  const led = new Ledger(ledgers[x.ledger], root);
  ok(led.whole === x.whole && led.broken_at === x.broken_at && led.entries.length === x.entries,
     'verify ' + f + ' (' + led.whole + ', ' + led.broken_at + ', ' + led.entries.length + ': ' + led.error + ')');
  if (x.state !== undefined) {
    const got = canonString(state(led, root, x.now), ID_KEY);
    ok(got === x.state, 'state ' + f);
    if (got !== x.state) {
      for (let i = 0; i < got.length; i++) if (got[i] !== x.state[i]) {
        console.log('  first difference at ' + i + ':\n  js: ' + got.slice(i - 80, i + 80) + '\n  py: ' + x.state.slice(i - 80, i + 80));
        break;
      }
    }
  }
}

// the dex pages: render.js must give exactly what Python's render.py gives
const rendered = json('pages.json');
for (const name of Object.keys(rendered)) {
  const x = existsSync(join(V, 'ledgers', name + '.json')) ? json(join('ledgers', name + '.json')) : {};
  const led = new Ledger(ledgers[x.ledger || name], x.root ? new Ledger(ledgers[x.root]) : null);
  const got = JSON.stringify(pages(led, ['Mangoes', 'About', 'Farm ledger']));
  ok(got === JSON.stringify(rendered[name]), 'pages ' + name);
  if (got !== JSON.stringify(rendered[name])) {
    const want = JSON.stringify(rendered[name]);
    for (let i = 0; i < got.length; i++) if (got[i] !== want[i]) {
      console.log('  js: ' + got.slice(i - 60, i + 80) + '\n  py: ' + want.slice(i - 60, i + 80)); break;
    }
  }
}

// whole dexs: dexweb.js must build every file dexweb built (vectors/dex/)
const template = JSON.parse(readFileSync(join(V, '..', 'js', 'dexweb-template.json'), 'utf8'));
const walk = (dir, base = dir) => readdirSync(dir, { withFileTypes: true }).flatMap((d) =>
  d.isDirectory() ? walk(join(dir, d.name), base) : [join(dir, d.name).slice(base.length + 1)]);
for (const name of readdirSync(join(V, 'dex'))) {
  const dir = join(V, 'dex', name), want = walk(dir).sort();
  let got;
  if (name.endsWith('-variant')) {
    const base = name.slice(0, -8), cfg = JSON.parse(readFileSync(join(V, 'dex', base, 'config.json'), 'utf8'));
    Object.assign(cfg, { index_list_type_para: false, page_javascript: '<script src="p.js"></script>',
      index_javascript: '<script src="i.js"></script>' });
    const data = JSON.parse(readFileSync(join(V, 'dex', base, 'data.json'), 'utf8'));
    got = Object.fromEntries(Object.entries(buildGen(data, cfg)).map(([p, h]) => ['gen/' + p, new TextEncoder().encode(h)]));
    for (const f of ['gen/ledgdex.jsonl', 'gen/styles.css']) got[f] = new Uint8Array(readFileSync(join(dir, f)));
  } else {
    const cfg = JSON.parse(readFileSync(join(dir, 'config.json'), 'utf8'));
    got = makeDex(new Uint8Array(readFileSync(join(dir, 'ledgdex.jsonl'))), cfg.dexname, template).files;
  }
  ok(JSON.stringify(Object.keys(got).sort()) === JSON.stringify(want), 'dex ' + name + ' file list: ' + Object.keys(got).sort().join(' '));
  for (const f of want) {
    const a = got[f] ? Buffer.from(got[f]) : null, b = readFileSync(join(dir, f));
    ok(a && a.equals(b), 'dex ' + name + '/' + f);
    if (a && !a.equals(b)) {
      const x = a.toString(), y = b.toString();
      for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) { console.log('  js: ' + JSON.stringify(x.slice(i - 50, i + 60)) + '\n  py: ' + JSON.stringify(y.slice(i - 50, i + 60))); break; }
    }
  }
}

// a ledger made in JavaScript verifies, and refuses what it should
const secret = new Uint8Array(32).map((_, i) => i);
const led = newLedger(secret, 'JS', 'made in js', '', '2026-10-01T09:00:00Z');
led.append(led.nextEntry(secret, message(secret, 'note', { ref: led.ids[0], text: 'hi' }, '2026-10-01T09:01:00Z'),
  '2026-10-01T09:01:00Z'));
ok(new Ledger(led.data).whole && new Ledger(led.data).entries.length === 2, 'js-made ledger');
let refused = false;
try { message(secret, 'note', { ref: led.ids[0], text: 'x', constructor: 1 }); } catch (e) { refused = e instanceof Invalid; }
ok(refused, 'unexpected field named like an Object property');

console.log(passed + ' passed, ' + failed + ' failed');
process.exit(failed ? 1 : 0);
