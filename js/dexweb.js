// A complete dex in the browser (spec 7.1), the same files "ledgdex init" makes with dexweb: py/ledgdex/render.py
// create_dex() and dexweb's dexgen. Checked file for file against dexs dexweb built (vectors/dex/).
import { Ledger } from './core.js';
import { pages, htmlTitle, LEDGER } from './render.js';

const enc = new TextEncoder();
export const RUN_PY = 'from dexweb import dexgen\ndex = dexgen.Dexgen()\n';

/** Python's json.dumps(v, indent=indent, ensure_ascii=ascii). */
export function pyJson(v, indent = null, ascii = true, depth = 0) {
  const nl = indent === null ? '' : '\n' + ' '.repeat(indent * (depth + 1));
  const end = indent === null ? '' : '\n' + ' '.repeat(indent * depth);
  const sep = indent === null ? ', ' : ',';
  if (v === null) return 'null';
  if (typeof v === 'boolean' || typeof v === 'number') return String(v);
  if (typeof v === 'string') {
    const s = JSON.stringify(v);
    return ascii ? s.replace(/[\x7f-\uffff]/g, (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0')) : s;
  }
  if (Array.isArray(v)) {
    return v.length ? '[' + v.map((x) => nl + pyJson(x, indent, ascii, depth + 1)).join(sep) + end + ']' : '[]';
  }
  const keys = Object.keys(v);
  return keys.length ? '{' + keys.map((k) => nl + pyJson(k, indent, ascii) + ': ' + pyJson(v[k], indent, ascii, depth + 1))
    .join(sep) + end + '}' : '{}';
}

/** Python's str.format for "{}", "{0}" and "{{ }}". */
function pyFormat(t, args) {
  let auto = 0;
  return t.replace(/\{\{|\}\}|\{(\d*)\}/g, (m, n) => m === '{{' ? '{' : m === '}}' ? '}' : String(args[n === '' ? auto++ : +n]));
}

// Python compares strings by code point; JavaScript's default sort by UTF-16 unit
function byCodePoint(a, b) {
  const x = [...a], y = [...b];
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    if (x[i] !== y[i]) return x[i].codePointAt(0) - y[i].codePointAt(0);
  }
  return x.length - y.length;
}

function withScript(template, js) {  // dexweb puts page_javascript / index_javascript just before </head>
  if (!js || js.length <= 2) return template;
  const parts = template.split('</head>');
  return parts[0] + js + '</head>' + parts[1];
}

/** The gen/ files dexweb's dexgen makes from data.json pages and config.json. */
export function buildGen(data, config) {
  const name = config.dexname, out = {};
  let list = data.filter((p) => p.body.length).map((p) => ({ title: p.title, html: htmlTitle(p.title), body: p.body,
    page: withScript(pyFormat(config.page_template, [p.title, name, p.title.toUpperCase(),
      p.body.map((i) => '<p>' + i + '</p>').join(''), name.toUpperCase()]), config.page_javascript) }));
  list = list.sort((a, b) => byCodePoint(a.title, b.title));
  let k = '';
  for (const p of list) {
    const only = config.index_list_no_page_link_only && p.body.length === 1 && p.body[0].startsWith('<a') && p.body[0].endsWith('</a>');
    const q = p.body[0], href = only ? q.slice(q.indexOf('=') + 2, q.indexOf('>') - 1) : p.html + '.html';
    if (!config.index_list_type_para) {
      k += only ? "<div class='indexlink'><a href='" + href + "'>" + p.title + '</a><br></div>'
        : "<div class='indexlink'><a href=" + href + '>' + p.title + '</a><br></div>';
    } else if (only) {
      k += "<div class='indexlink'><a href='" + href + "'>" + p.title + '</a> (' + q.slice(q.indexOf('>') + 1, q.indexOf('</a>')) + ')</div>';
    } else if (config.index_list_no_page_link_only) {
      k += "<div class='indexlink'><a href=" + href + '>' + p.title + '</a> (' + q + ')</div>';
    } else {
      k += "<div class='indexlink'><p><a href=" + href + '>' + p.title + '</a> (' + q + ')</p></div>';
    }
  }
  for (const p of list) out[p.html + '.html'] = p.page;
  out['index.html'] = withScript(pyFormat(config.index_template, [name, name.toUpperCase(), k, name.toUpperCase()]),
    config.index_javascript);
  return out;
}

/** Every file of a new dex around the ledger bytes `data`, as {path: Uint8Array}; dirs lists the empty folders. */
export function makeDex(data, dexname, template, publish = {}) {
  const led = new Ledger(data);
  if (!led.whole) throw new Error('the ledger is broken: ' + led.error);
  const config = { ...template.config, dexname, publish: { append_only: [LEDGER], ...publish } };
  const dataJson = pyJson(pages(led), 4, false);
  const files = {
    [LEDGER]: data, 'config.json': pyJson(config, 4), 'data.json': dataJson, 'run.py': RUN_PY,
    'styles.css': template.styles, 'backup/data.json': dataJson, ['gen/' + LEDGER]: data, 'gen/styles.css': template.styles,
  };
  for (const [path, html] of Object.entries(buildGen(pages(led), config))) files['gen/' + path] = html;
  for (const p of Object.keys(files)) if (typeof files[p] === 'string') files[p] = enc.encode(files[p]);
  files['gen/assets/favicon.ico'] = Uint8Array.from(atob(template.favicon), (c) => c.charCodeAt(0));  // dexweb's icon
  return { files, dirs: ['to_add/'] };
}
