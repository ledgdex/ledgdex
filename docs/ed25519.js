// Pure Ed25519 (RFC 8032 section 5.1), after the Python reference in section 6 and ledgdex's ed25519.py.
// BigInt arithmetic, synchronous. Not constant time: fine for public ledgers and signing in your own browser.
import { sha512 } from './sha.js';

export const p = 2n ** 255n - 19n;
export const q = 2n ** 252n + 27742317777372353535851937790883648493n;

const mod = (a) => { const r = a % p; return r < 0n ? r + p : r; };
function pow(b, e, m = p) {
  let r = 1n;
  b %= m;
  while (e > 0n) {
    if (e & 1n) r = (r * b) % m;
    b = (b * b) % m;
    e >>= 1n;
  }
  return r;
}
const inv = (x) => pow(x, p - 2n);
const d = mod(-121665n * inv(121666n));
const SQRT_M1 = pow(2n, (p - 1n) / 4n);

function le(bytes) {
  let n = 0n;
  for (let i = bytes.length - 1; i >= 0; i--) n = (n << 8n) | BigInt(bytes[i]);
  return n;
}
function toLE(n, len = 32) {
  const out = new Uint8Array(len);
  for (let i = 0; i < len; i++) { out[i] = Number(n & 0xffn); n >>= 8n; }
  return out;
}
const sha512modq = (bytes) => le(sha512(bytes)) % q;
function cat(...parts) {
  const out = new Uint8Array(parts.reduce((s, x) => s + x.length, 0));
  let o = 0;
  for (const x of parts) { out.set(x, o); o += x.length; }
  return out;
}

function add(P, Q) {
  const A = mod((P[1] - P[0]) * (Q[1] - Q[0])), B = mod((P[1] + P[0]) * (Q[1] + Q[0]));
  const C = mod(2n * P[3] * Q[3] * d), D = mod(2n * P[2] * Q[2]);
  const E = B - A, F = D - C, G = D + C, H = B + A;
  return [mod(E * F), mod(G * H), mod(F * G), mod(E * H)];
}
function mul(s, P) {
  let Q = [0n, 1n, 1n, 0n];
  while (s > 0n) {
    if (s & 1n) Q = add(Q, P);
    P = add(P, P);
    s >>= 1n;
  }
  return Q;
}
const equal = (P, Q) => mod(P[0] * Q[2] - Q[0] * P[2]) === 0n && mod(P[1] * Q[2] - Q[1] * P[2]) === 0n;

function recoverX(y, sign) {
  if (y >= p) return null;
  const x2 = mod((y * y - 1n) * inv(d * y * y + 1n));
  if (x2 === 0n) return sign ? null : 0n;
  let x = pow(x2, (p + 3n) / 8n);
  if (mod(x * x - x2) !== 0n) x = mod(x * SQRT_M1);
  if (mod(x * x - x2) !== 0n) return null;
  if (Number(x & 1n) !== sign) x = p - x;
  return x;
}
const gy = mod(4n * inv(5n)), gx = recoverX(gy, 0);
const G = [gx, gy, 1n, mod(gx * gy)];

function compress(P) {
  const zi = inv(P[2]), x = mod(P[0] * zi), y = mod(P[1] * zi);
  return toLE(y | ((x & 1n) << 255n));
}
function decompress(s) {
  if (s.length !== 32) return null;
  let y = le(s);
  const sign = Number(y >> 255n);
  y &= (1n << 255n) - 1n;
  const x = recoverX(y, sign);
  return x === null ? null : [x, y, 1n, mod(x * y)];
}
function expand(secret) {
  if (secret.length !== 32) throw new Error('an Ed25519 secret key is 32 bytes');
  const h = sha512(secret);
  let a = le(h.slice(0, 32));
  a &= (1n << 254n) - 8n;
  a |= 1n << 254n;
  return [a, h.slice(32)];
}

export function publicKey(secret) {
  return compress(mul(expand(secret)[0], G));
}

export function sign(secret, msg) {
  const [a, prefix] = expand(secret);
  const A = compress(mul(a, G));
  const r = sha512modq(cat(prefix, msg));
  const Rs = compress(mul(r, G));
  const h = sha512modq(cat(Rs, A, msg));
  return cat(Rs, toLE((r + h * a) % q));
}

// small-order public keys (eight of them): one signature verifies for every message, so they never verify
const IDENTITY = [0n, 1n, 1n, 0n];
export function verify(pub, msg, sig) {
  if (pub.length !== 32 || sig.length !== 64) return false;
  const A = decompress(pub);
  if (!A || equal(mul(8n, A), IDENTITY)) return false;
  const Rs = sig.slice(0, 32), R = decompress(Rs);
  if (!R) return false;
  const s = le(sig.slice(32));
  if (s >= q) return false;
  const h = sha512modq(cat(Rs, pub, msg));
  return equal(mul(s, G), add(R, mul(h, A)));
}
