# Security

Ledgdex v1.0.16. The rules every implementation must keep are the security invariants in
[architecture/SPEC.md](architecture/SPEC.md), section 9; this file says what they mean for people running ledgdex.

## Reporting a problem

Write to Noorul Ali, founder of The Matrix, at manonthemoon13131@gmail.com, before you publish anything. Include a
ledger or steps that show the problem. Please do not open a public issue for a way to forge, rewrite or read a key.

## What ledgdex guarantees

- **Tampering is evident.** Every entry is hashed into the next and signed by the ledger's owner (or an active
  device key). Changing, dropping or reordering any byte breaks verification at that point, in Python and in the
  browser, which must agree byte for byte (shared vectors and differential fuzzing on every push).
- **Rewrites are caught.** An owner can re-sign a whole history, so `ledgdex check` keeps the copies it has seen and
  the receipts other selves hold, and reports any rewrite with two signed entries at one position as proof. Run it.
- **Only a key's holder can sign for it.** Verification is strict Ed25519 and refuses the eight small-order public
  keys, for which one signature would verify for every message. (1.0.0 accepted them.)
- **Only the root's owner can hand a ledger to a new key.** A `recover` must be signed by the root's owner key (not
  a device) and is used once; nothing a stolen key does can block it. Complete a recovery promptly: until it is used,
  the key the root named can take the ledger. A receipt that carries a recovery is
  checked against the root too. (1.0.1 and earlier let a buyer forge a receipt this way; upgrade to 1.0.2.)
- **The verification cache cannot be poisoned.** It only remembers entries whose validity depends on nothing but
  their bytes, never a recovery checked against some root. (1.0.2 and earlier remembered a recovery checked once
  against a hostile root; upgrade to 1.0.3, and delete `~/.cache/ledgdex` if you ever verified with a root you do
  not trust.)
- **`check` accuses only with the accused's own signatures.** A receipt signed by a revoked device, or naming an
  address that never served the ledger, is a warning, not an error. Every entry a receipt holds (its key chain
  too) is compared, so deleting an owner-signed entry that a receipt holds is caught. Receipts signed by a device key
  are weaker evidence than the owner's: if the ledger later shows that device revoked before the entry, `check` cannot
  tell a rewrite from a stolen device and warns; keep `check` running so its kept copies catch the rewrite itself.
- **Only the owner key changes a ledger's keys.** `device`, `device_revoke`, `rotate` (and the root's `recover`) must
  be authored *and* recorded by the owner key, so a device cannot copy in such a message its owner signed for
  another ledger. (1.0.5 and earlier allowed it.)
- **The root cannot be swapped at its address.** A dex pins its root by ledger id (`root_id` in `config.json`, set
  the first time it is read) and refuses another ledger or a broken one there, so taking over the root's hosting
  does not make you the default arbiter.
- **A signed message counts once.** Recording the same message twice is ignored (`duplicate_message`), so a claim
  cannot be counted twice and a revoked device cannot be brought back by replaying its old `device` message.
- **Hostile ledgers are only data.** A ledger cannot crash a verifier (nesting is limited to 32 levels), cannot put
  a script or `javascript:` link on a page (only http(s) addresses become links, and the dex name is stripped of
  markup characters), and cannot make `check` read local
  files (addresses inside ledgers are read only over http(s), or as dex folders and `.jsonl` files). Every read is
  capped (`LEDGDEX_MAX_BYTES`, 64 MiB by default).

## Keys

- **On disk**, keys are in `~/.ledgdex` with mode 600; ledgdex refuses a key file anyone else can read. They are not
  encrypted: protect the machine, use full-disk encryption, and keep the owner key offline (backed up), signing day to
  day with a device key you can revoke.
- **In the browser**, the viewer stores a key only sealed with a passphrase (PBKDF2-SHA-256, 600,000 rounds, into
  AES-256-GCM), and sealed-bid secrets only sealed with a key derived from your secret key. An older viewer's
  unsealed key is removed from storage when the new viewer opens. Use a long passphrase and download a backup.
- **Signing** uses a constant-time Ed25519 when there is one: the `cryptography` package in Python (install the
  `fast` extra), Web Crypto in the browser. The built-in code is a fallback, and the command line warns when it uses
  it. Verifying does not depend on it.

## Trust you still need

- **A device key's past.** Revoking a device stops it from signing *later* entries, but nothing can undo what it was
  able to sign while it was active: a thief who takes a device key can sign entries that conflict with the ledger at
  positions where that device was still active, and `check` reports them as `receipt_mismatch` or `equivocation`, as
  it must (two signed histories by keys the ledger authorised). Without a trusted clock no system can tell a thief's
  fork from the device's own; an arbiter weighs it with the date of the `device_revoke`. This stays an error by
  decision (spec, Decision 6), so that revoking a device afterwards never downgrades proof of equivocation. Give device keys only to
  devices you would trust with the ledger, and revoke a lost one at once.

- **The root.** Its owner admits who is in The Matrix, names new keys for lost ones, and is the default arbiter.
  Keep its owner key offline and run `ledgdex check` on it. A root that misbehaves does so in signed entries
  everyone can see, but it is trusted to admit and recover honestly.
- **The viewer's origin.** Pages on one web origin can read each other's browser storage. `matrixdex.github.io` is
  shared by every matrixdex repository's pages, so a sealed key there is safe only as long as the passphrase is
  strong. For production, serve the viewer from an address of its own (a custom domain). The viewer's pages carry
  a Content-Security-Policy that allows scripts only from the viewer, and the viewer refuses to run inside another
  page's frame (so no site can trick your clicks on it). Serving it with an `X-Frame-Options: DENY` or
  `frame-ancestors 'none'` header, where your host allows headers, adds a second guard.
- **Clocks.** Entry times are their owners' clocks, within 5 minutes of each other (SPEC 9.2).
- **What is not protected by design** is listed in the spec, Part I: a seller who never records a claim, the order
  of claims that arrive together, delivery and payment outside the ledger, and fake identities (admission handles
  those).

## Supply chain

Ledgdex depends only on dexweb (pinned below version 5) and optionally `cryptography`. The browser code has no
dependencies and loads nothing from elsewhere. Workflows install ledgdex from a release tag and pin every action to a
commit.
