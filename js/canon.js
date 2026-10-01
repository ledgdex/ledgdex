// Canonical JSON (spec 1.2): the exact bytes that are hashed and signed.
import { sha256, hex } from './sha.js';

export const KEY = /^[a-z][a-z0-9_]*$/;
export const ID_KEY = /^[\x21-\x7e]+$/;  // the state object (spec 6.3) is keyed by ids
const MAX_INT = 2 ** 53 - 1;
export const MAX_DEPTH = 32;  // spec 1.2 rule 9: arrays and objects nest at most this deep
const LONE = /[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]/;
const enc = new TextEncoder();

export class CanonError extends Error {}

export function check(v, keys = KEY, depth = 1) {
  if (v === null || typeof v === 'boolean') return;
  if (typeof v === 'number') {
    if (!Number.isInteger(v)) throw new CanonError('floats are not allowed');
    if (v > MAX_INT || v < -MAX_INT) throw new CanonError('integer out of range');
    return;
  }
  if (typeof v === 'string') {
    if (LONE.test(v)) throw new CanonError('string is not valid Unicode');
    return;
  }
  if (typeof v === 'object' && depth > MAX_DEPTH) throw new CanonError('too deeply nested');
  if (Array.isArray(v)) { for (const x of v) check(x, keys, depth + 1); return; }
  if (typeof v === 'object') {
    for (const k of Object.keys(v)) {
      if (!keys.test(k)) throw new CanonError('bad key: ' + k);
      check(v[k], keys, depth + 1);
    }
    return;
  }
  throw new CanonError('value of type ' + typeof v + ' is not allowed');
}

function write(v) {
  if (v === null || typeof v === 'boolean' || typeof v === 'number') return String(v);
  if (typeof v === 'string') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(write).join(',') + ']';
  const keys = Object.keys(v).sort();  // ASCII keys: UTF-16 order is byte order
  return '{' + keys.map((k) => JSON.stringify(k) + ':' + write(v[k])).join(',') + '}';
}

/** canon(x): canonical JSON as a string (its UTF-8 bytes are what is hashed and signed). */
export function canonString(v, keys = KEY) {
  check(v, keys);
  return write(v);
}

export function canon(v, keys = KEY) {
  return enc.encode(canonString(v, keys));
}

export function sha256id(bytes) {
  return 'sha256:' + hex(sha256(bytes));
}

/** hash(x) = "sha256:" + hex(SHA-256(canon(x))) */
export function hash(v) {
  return sha256id(canon(v));
}

// ignoreBOM: keep a leading U+FEFF in the text (the default drops it silently), so it is rejected like any byte
const dec = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });

/** Parse bytes that MUST already be canonical JSON. */
export function parse(bytes) {
  let text, v;
  try {
    text = dec.decode(bytes);
    v = JSON.parse(text);
  } catch (e) {
    throw new CanonError(e instanceof RangeError ? 'too deeply nested' : 'not JSON: ' + e.message);
  }
  if (canonString(v) !== text) throw new CanonError('not canonical JSON');
  return v;
}
