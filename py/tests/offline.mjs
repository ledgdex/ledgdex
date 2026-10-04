// Loaded with "node --import" for the docs' JavaScript examples: tests have no network, so https://ledgdex.github.io/
// is served from this repository (docs/ from guide/dex/, everything else from js/), and any other address fails.
import { readFile } from 'fs/promises';

const ROOT = new URL('../../', import.meta.url);
const SITE = 'https://ledgdex.github.io/';
globalThis.fetch = async (input) => {
  const url = String(input instanceof Request ? input.url : input);
  if (!url.startsWith(SITE)) throw new Error('no network in tests: ' + url);
  const path = url.slice(SITE.length).split(/[?#]/)[0];
  const file = path.startsWith('docs/') ? new URL('guide/dex/' + path.slice(5), ROOT) : new URL('js/' + path, ROOT);
  try {
    return new Response(await readFile(file));
  } catch (e) {
    return new Response('not found', { status: 404 });
  }
};
