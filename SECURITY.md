# Security

Ledgdex v1.0.1. The rules every implementation must keep are the security invariants in
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
  keys, for which one signature would verify for every message. (1.0.0 accepted them; upgrade to 1.0.1.)
- **A signed message counts once.** Recording the same message twice is ignored (`duplicate_message`), so a claim
  cannot be counted twice and a revoked device cannot be brought back by replaying its old `device` message.
- **Hostile ledgers are only data.** A ledger cannot crash a verifier (nesting is limited to 32 levels), cannot put
  a script or `javascript:` link on a page (only http(s) addresses become links), and cannot make `check` read local
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

- **The root.** Its owner admits who is in The Matrix, names new keys for lost ones, and is the default arbiter.
  Keep its owner key offline and run `ledgdex check` on it. A root that misbehaves does so in signed entries
  everyone can see, but it is trusted to admit and recover honestly.
- **The viewer's origin.** Pages on one web origin can read each other's browser storage. `matrixdex.github.io` is
  shared by every matrixdex repository's pages, so a sealed key there is safe only as long as the passphrase is
  strong. For production, serve the viewer from an address of its own (a custom domain). The viewer's pages carry
  a Content-Security-Policy that allows scripts only from the viewer.
- **Clocks.** Entry times are their owners' clocks, within 5 minutes of each other (SPEC 9.2).
- **What is not protected by design** is listed in the spec, Part I: a seller who never records a claim, the order
  of claims that arrive together, delivery and payment outside the ledger, and fake identities (admission handles
  those).

## Supply chain

Ledgdex depends only on dexweb (pinned below version 5) and optionally `cryptography`. The browser code has no
dependencies and loads nothing from elsewhere. Workflows install ledgdex from a release tag and pin every action to a
commit.
