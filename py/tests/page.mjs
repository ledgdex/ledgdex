// node --import offline.mjs page.mjs PAGE.html: runs an example web page's module script in Node, with a small
// stand-in for the DOM and the core loaded from LEDGDEX_JS instead of the site, then prints the text the page shows.
import { readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { pathToFileURL } from 'url';

const html = readFileSync(process.argv[2], 'utf8');
const script = html.match(/<script type='module'>\n([\s\S]*?)<\/script>/);
if (!script) throw new Error('no <script type=\'module\'> in ' + process.argv[2]);
const core = pathToFileURL(process.env.LEDGDEX_JS).href.replace(/\/?$/, '/');
const code = script[1].replace(/^(import .* from ')https:\/\/ledgdex\.github\.io\//gm, '$1' + core);

const element = () => ({ textContent: '', children: [], append(child) { this.children.push(child); } });
const elements = {};
globalThis.document = { getElementById: (id) => (elements[id] ||= element()), createElement: element };
const file = join(process.cwd(), 'page-script.mjs');
writeFileSync(file, code);
await import(pathToFileURL(file).href);
for (const e of Object.values(elements)) {
  if (e.textContent) console.log(e.textContent);
  for (const child of e.children) console.log(child.textContent);
}
