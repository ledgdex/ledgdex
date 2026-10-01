// A ZIP file (stored, no compression) from {path: Uint8Array} and empty folders, for downloading a whole dex.
const CRC = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c;
});
const crc32 = (b) => { let c = ~0; for (const x of b) c = CRC[(c ^ x) & 0xff] ^ (c >>> 8); return ~c >>> 0; };

export function zip(files, dirs = [], prefix = '') {
  const enc = new TextEncoder(), parts = [], central = [];
  let offset = 0;
  const entries = dirs.map((d) => [prefix + d, new Uint8Array(0)]).concat(Object.entries(files).map(([p, b]) => [prefix + p, b]));
  for (const [path, data] of entries) {
    const name = enc.encode(path), crc = crc32(data);
    const head = (sig, extra) => {
      const h = new DataView(new ArrayBuffer(extra ? 46 : 30));
      let i = 0;
      const u32 = (v) => { h.setUint32(i, v, true); i += 4; }, u16 = (v) => { h.setUint16(i, v, true); i += 2; };
      u32(sig);
      if (extra) u16(20);
      [20, 0x0800, 0, 0, 0x5c21].forEach(u16);  // version, UTF-8 names, stored, time, date (2026-01-01)
      u32(crc); u32(data.length); u32(data.length); u16(name.length); u16(0);
      if (extra) { [0, 0, 0].forEach(u16); u32(path.endsWith('/') ? 0x10 : 0); u32(offset); }
      return new Uint8Array(h.buffer);
    };
    const local = head(0x04034b50, false);
    parts.push(local, name, data);
    central.push(head(0x02014b50, true), name);
    offset += local.length + name.length + data.length;
  }
  const size = central.reduce((s, x) => s + x.length, 0), end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true);
  end.setUint16(8, entries.length, true); end.setUint16(10, entries.length, true);
  end.setUint32(12, size, true); end.setUint32(16, offset, true);
  return new Blob([...parts, ...central, new Uint8Array(end.buffer)], { type: 'application/zip' });
}
