// Keeping secrets in the browser, encrypted (Web Crypto). A secret key is stored only sealed with a passphrase:
// PBKDF2-SHA-256 (600,000 rounds, 16-byte salt) makes an AES-256-GCM key that encrypts it. Bid secrets (amount and
// nonce, until the reveal) are sealed with a key made from the secret key itself, so they need no passphrase and
// cannot be read without the key that bid. Nothing secret is stored in the clear.
import { hex, unhex } from './sha.js';

export const ROUNDS = 600000;
export const MIN_PASSPHRASE = 12;
const enc = new TextEncoder(), dec = new TextDecoder();
const subtle = () => {
  if (!globalThis.crypto || !globalThis.crypto.subtle) throw new Error('this page needs Web Crypto (an https address)');
  return globalThis.crypto.subtle;
};
const random = (n) => globalThis.crypto.getRandomValues(new Uint8Array(n));

async function passKey(pass, salt, rounds) {
  const base = await subtle().importKey('raw', enc.encode(pass), 'PBKDF2', false, ['deriveKey']);
  return subtle().deriveKey({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations: rounds }, base,
    { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
}

async function seal(key, bytes, extra) {
  const iv = random(12);
  const ct = await subtle().encrypt({ name: 'AES-GCM', iv }, key, bytes);
  return { ...extra, iv: hex(iv), ct: hex(new Uint8Array(ct)) };
}

async function unseal(key, box) {
  return new Uint8Array(await subtle().decrypt({ name: 'AES-GCM', iv: unhex(box.iv) }, key, unhex(box.ct)));
}

/** Seal a 32-byte secret key with a passphrase. The public key is kept beside it, in the clear, to show. */
export async function sealKey(secret, pass, pub, rounds = ROUNDS) {
  if (pass.length < MIN_PASSPHRASE) throw new Error('a passphrase has at least ' + MIN_PASSPHRASE + ' characters');
  const salt = random(16);
  return seal(await passKey(pass, salt, rounds), secret,
    { v: 1, kdf: 'PBKDF2-SHA-256', rounds, salt: hex(salt), pub });
}

/** The secret key in a sealed box; throws on a wrong passphrase or a changed box. */
export async function openKey(box, pass) {
  if (!box || box.v !== 1 || !(box.rounds >= 100000)) throw new Error('not a sealed key');
  try {
    const s = await unseal(await passKey(pass, unhex(box.salt), box.rounds), box);
    if (s.length !== 32) throw new Error();
    return s;
  } catch (e) {
    throw new Error('wrong passphrase');
  }
}

async function secretKey(secret, purpose) {
  const k = await subtle().digest('SHA-256', new Uint8Array([...enc.encode('ledgdex ' + purpose + '\n'), ...secret]));
  return subtle().importKey('raw', k, 'AES-GCM', false, ['encrypt', 'decrypt']);
}

/** Seal a JSON value with a key made from the secret key (for bids). */
export async function sealWith(secret, value) {
  return seal(await secretKey(secret, 'bid'), enc.encode(JSON.stringify(value)), { v: 1 });
}

export async function openWith(secret, box) {
  return JSON.parse(dec.decode(await unseal(await secretKey(secret, 'bid'), box)));
}
