# Ledgdex

Ledgdex: an agent-centric ledger with triple-entry accounting, for The Matrix.
Specification v0.1. CC0. Repository: https://github.com/matrixdex/ledgdex

This file is for two readers. Part I explains the idea to a person. Part II is the exact specification a coding agent
implements. Part III is the build plan. Where the two parts seem to disagree, Part II wins.

---

# Part I: the idea

## In one paragraph

Every self (a person, a company, a bot, a government) keeps its own ledger: a file that only grows, in its own dex.
Every line in it is signed by the ledger's owner. When two selves trade, the buyer signs a claim, the seller records
that claim in the seller's ledger (the seller's signed entry is the buyer's receipt), and the buyer keeps that receipt
in the buyer's own ledger. So every trade exists three times: the buyer's signed claim, the seller's signed record, and
the buyer's copy of that record. That is triple-entry accounting. Nobody else is needed to keep the books.

## Principles

1. **Sovereign.** Only hashes (SHA-256), signatures (Ed25519) and plain files. No blockchain, no server, no outside
   service. Every dependency is vendored. It works offline.
2. **Agent-centric.** There is no shared ledger. Each self owns its ledger and orders its own entries.
3. **Append-only.** Nothing is ever edited or deleted. Corrections are new entries.
4. **Trust is explicit.** You buy from people you trust. Admission (controlled access) decides who is in. The ledger
   does not replace trust; it makes trust checkable.
5. **What you write about yourself is a claim; what others hold about you is evidence.** Every check moves evidence
   into other people's ledgers.
6. **Humans and bots are equal participants.** Same files, same keys, same rules.
7. **Every ledgdex is a dex.** The ledger lives next to `data.json` in a dex, and its state is always rendered by
   dexweb as ordinary dex pages, readable by people and bots. One core, many flavors.

## The parts

| Part | What it is |
|---|---|
| Self | anyone with a key pair: person, company, bot, government |
| Ledger | `ledgdex.jsonl` in the self's dex: a header line, then one signed entry per line |
| Message | something a self signs and sends: an offer, a claim, a payment notice, a bid |
| Entry | a ledger owner's signed record of a message, with its position and time. An entry is a receipt |
| Offer | something for sale, at a fixed price set by the seller |
| Claim | a buyer's signed request to take an offer |
| Index | a ledger that lists other ledgers (Dexnet flavor). ASS is an index |
| Root | the ledger that admits selves to The Matrix (Matrixnet flavor). Today: the founder's |
| Arbiter | the self an offer names to settle disputes about it |
| Owner key | the self's main key. Used only to open the ledger, rotate keys and add or remove devices |
| Device key | a key on one device (laptop, phone), authorised by the owner key to append and sign for the self |

## A trade, in plain words

1. The seller signs an offer and records it in the seller's ledger.
2. The buyer reads the seller's ledger, signs a claim for the offer at its price, and sends it by any channel.
3. The seller records the claim. The recording entry carries the seller's time and signature. That entry is the receipt.
   Whether the claim is accepted is decided by fixed rules (enough quantity left, the price matches the offer, buyer allowed and not the seller),
   not by the seller's mood.
4. The buyer saves the receipt in the buyer's own ledger.
5. The buyer pays by whatever method the offer names (outside the ledger) and sends a signed payment notice.
6. The seller records the payment, records delivery, and the buyer records confirmation.
7. If something goes wrong, either side opens a dispute, and the offer's arbiter records a ruling.

## Bots: robots paid per clean in a mall (draft, section 10)

Selves include machines. Vacuum robots clean the floor of a mall, and the shops on that floor pay per clean, settled
every day. Robots can belong to different operators: when one robot is busy, broken or away, another operator's robot
takes the clean. Every shop and every robot has a dex and a ledgdex; the mall runs the index, the root and the
clearing ledger, and arbitrates.

1. The mall admits robots and shops in the root, and lists their ledgers in its index.
2. Each robot's owner key stays with its operator; the robot holds a device key. A stolen robot is a `device_revoke`.
3. Each morning, each robot offers the cleans it can do that day: "floor clean, MALL 50 per clean, 40 cleans, until
   the end of the day", for admitted selves. A robot that is unavailable offers none, or withdraws its offer.
4. When a shop needs its frontage cleaned, its system claims one clean from a robot with cleans left, by its own
   rule (cheapest, nearest, the one it used last), with a deadline to clean by.
5. The robot cleans and records the delivery with evidence (its log or photos, linked by address and hash). The
   shop's system checks the evidence and confirms. If the deadline passes with no delivery, the claim lapses: nothing
   is owed, the clean goes back to the robot's offer, and the shop claims it from another robot.
6. At the end of the day the mall settles in mall credits: for each shop and robot, it moves credits for the cleans
   confirmed that day from the shop's balance to the robot's, in its clearing ledger. Each robot records what it
   received. Shops buy credits from the mall and operators cash them out, outside the ledger.
7. A shop that disputes a clean opens a dispute; the mall, as arbiter, rules.

No step needs a person, no robot is locked in, and every clean is evidence in two ledgers.

## What it protects against, and what it does not

Protected (detectable by anyone, with signed proof):
- changing an offer after it is claimed (claims sign the offer's hash);
- inventing or altering someone's claim (claims are signed by the buyer);
- dropping or reordering a claim the seller already recorded (the buyer holds the seller's signed receipt);
- rewriting history (every entry chains to the previous one; others hold copies and receipts);
- showing different histories to different people (two signed versions of one position are proof);
- the seller's page showing a wrong price (the price is in the signed offer, and the claim must match it).

Not protected (by design; these need trust, admission or arbiters):
- a seller who never records a claim at all (the buyer can only prove the claim existed by a time);
- the order in which a seller records claims that arrive close together;
- a seller who takes payment and does not deliver (provable, but recovery is off-ledger);
- fake identities (handled by admission, not by the ledger);
- a perfectly trustworthy clock (each ledger's time is its owner's time).

---

# Part II: specification

Keywords MUST, MUST NOT and MAY are used as in RFC 2119.

## 1. Encodings

### 1.1 Identifiers

| Thing | Format | Example |
|---|---|---|
| Public key | `ed25519:` + 64 lowercase hex chars (32 bytes) | `ed25519:d75a9801...511a` |
| Signature | 128 lowercase hex chars (64 bytes) | |
| Hash / id | `sha256:` + 64 lowercase hex chars | `sha256:9f86d081...0f00a08` |
| Time | UTC, ISO 8601, whole seconds, `Z` suffix | `2026-10-01T09:30:00Z` |
| Amount | integer, in the currency's smallest unit | `150000` (= INR 1500.00) |
| Currency | uppercase string | `INR`, `USD`, `BTC`, `ASS` |

### 1.2 Canonical JSON

Everything that is hashed or signed is first serialized as canonical JSON. Both implementations MUST produce
byte-identical output.

Rules:
1. Allowed values: object, array, string, integer, `true`, `false`, `null`. Floats are forbidden. Integers MUST be
   within -(2^53 - 1) .. 2^53 - 1. (Python: reject `float`; remember `bool` is a subclass of `int` and must stay a
   boolean.)
2. Object keys MUST match `^[a-z][a-z0-9_]*$` (ASCII only, so key sorting is identical in every language).
3. Strings MUST be valid Unicode (no lone surrogates).
4. Objects: keys sorted ascending by byte value; no duplicate keys.
5. No whitespace anywhere outside strings.
6. String escaping: `"` → `\"`, `\` → `\\`, U+0008 → `\b`, U+000C → `\f`, U+000A → `\n`, U+000D → `\r`,
   U+0009 → `\t`, other U+0000..U+001F → `\u00xx` (lowercase hex). Every other character is written as itself.
7. Output is UTF-8 bytes. Parsing accepts exactly these bytes: no byte-order mark, no whitespace, no other spelling
   of the same value.
8. `true` and `false` are never numbers: where a field MUST be the integer 1 (`v`, the header's `ledger`) or a
   position (`seq`), the JSON value `true` does not count.
9. Arrays and objects nest at most 32 deep (the top-level value is depth 1). A deeper text is not canonical JSON, so
   a hostile ledger cannot exhaust a verifier's stack.

Reference behaviour:
- Python: `json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")` after
  validating rules 1–3.
- JavaScript: a small serializer that sorts keys and uses `JSON.stringify` for each string (its escaping matches
  rule 6) after validating rules 1–3.

`canon(x)` below means these bytes. `hash(x)` means `"sha256:" + hex(SHA-256(canon(x)))`.

### 1.3 Cryptography

- Hash: SHA-256 (FIPS 180-4).
- Signature: Ed25519 (RFC 8032), pure Ed25519, no context, no prehash.
- `sign(key, x)` signs `canon(x)`. `verify(pub, x, sig)` verifies a signature over `canon(x)`.
- `verify` is strict: the public key and `R` MUST be canonical point encodings (y below p), `S` MUST be below the
  group order, and the public key MUST NOT be of small order (`[8]A` is the identity; there are eight such keys).
  For a small-order key one signature verifies for every message, so anyone could sign as it; no ledger, entry or
  message may be signed by one. (Before 1.0.1 such keys were accepted: vector `broken-small-order-key`.)
- Private keys MUST NOT be written into a dex or a repository.

## 2. Messages

A message is anything a self signs. Messages are portable: they can travel by HTTP, email, git, file or USB.

```json
{
  "v": 1,
  "type": "claim",
  "by": "ed25519:<author key>",
  "at": "2026-10-01T09:30:00Z",
  "body": { ... },
  "sig": "<author signature>"
}
```

- `v`: format version, MUST be `1`.
- `type`: one of the types in section 5.
- `by`: the author's public key.
- `at`: the author's own clock when signing. Informational; never used for ordering or price.
- `body`: type-specific object (section 5).
- `sig`: `sign(author_private_key, message_without_sig)`, where `message_without_sig` is the message object with the
  `sig` key removed.
- Message id: `hash(message)` (including `sig`).

A message is valid when: all fields are present and well formed, `v == 1`, `type` is known, `body` matches its type,
and `sig` verifies against `by`.

## 3. Ledgers

### 3.1 File

A ledger is a file named `ledgdex.jsonl` in the self's dex. Line 1 is the header. Every following line is one entry.
Each line is canonical JSON followed by a single `\n`. Lines are never edited or removed; new lines are only appended.
The format is JSON Lines (one JSON value per line) so that appending an entry adds bytes at the end and never touches
what is already written.

Header:

```json
{"ledger":1,"name":"Noorul Ali","owner":"ed25519:<initial owner key>"}
```

- `ledger`: format version, MUST be `1`.
- `owner`: the owner's initial public key.
- `name`: display name, informational.
- Ledger id: `hash(header)`.

### 3.2 Entry

```json
{
  "seq": 0,
  "prev": "sha256:<id of the previous entry, or the ledger id for seq 0>",
  "time": "2026-10-01T09:31:12Z",
  "msg": { ...message... },
  "sig": "<owner signature>"
}
```

- `seq`: position, starting at 0, increasing by exactly 1.
- `prev`: the id of the previous entry; for `seq` 0, the ledger id (`hash(header)`).
- `time`: the owner's clock when recording.
- `msg`: a complete, valid message (section 2), authored by the owner or by someone else.
- `sig`: `sign(owner_private_key, {seq, prev, time, msg})`, signed by the owner key current at this `seq`
  (see `rotate`, section 5.1).
- Entry id: `hash(entry)` (including `sig`).

An entry is a receipt: it proves that the owner recorded `msg` at position `seq` at `time`.

### 3.3 Structural validity

A verifier processes entries in order. Entry `n` is structurally valid when:
1. it is canonical JSON with exactly the keys `seq, prev, time, msg, sig`;
2. `seq == n`;
3. `prev` equals the id of entry `n-1` (or the ledger id for `n == 0`);
4. `time` is well formed and `time >= time of entry n-1`;
5. `msg` is a valid message;
6. `sig` verifies with one of the current signing keys: the owner key or an active device key (5.1). Exception: a
   `recovered` entry (5.7) is signed by the recovered key;
7. `time >= msg.at - 300 seconds` (a message cannot be recorded more than 5 minutes before it was signed);
8. `msg.type` may be recorded in this ledger by this author (section 5, "recorded by").

The first structurally invalid entry ends verification: the ledger is reported as broken at that `seq`, and the state
is the state after the last valid entry. Structural errors mean tampering or a bug, never a business decision.

Business rules (section 6) never break a ledger. A claim that fails them is still a valid entry; the state marks it
rejected with a reason.

### 3.4 Equivocation

If anyone holds two structurally valid entries with the same ledger id and the same `seq` but different entry ids,
that pair is proof that the owner showed different histories. Verifiers SHOULD report it.

### 3.5 One writer at a time (several devices)

An owner may append from several devices (a laptop and a phone), each with its own device key (5.1). Two devices
appending at the same time would
produce two different entries at the same `seq`, which is equivocation (3.4). Secure Scuttlebutt broke feeds this way.
To prevent it, appending works like a compare-and-swap on the published ledger:

1. **Append only on top of the published head.** Before appending, the tool fetches the published `ledgdex.jsonl`
   (dexweb's `published()`, 7.4). If the local copy is behind, it takes the published entries first. New entries
   always extend the published head.
2. **Publish atomically.** The dex is published through git with dexweb (7.4), to any git remote: a self-hosted one
   or a hosting service. A push that is not a fast-forward is rejected, so if two devices race, only the first push
   wins. dexweb also refuses to publish a `ledgdex.jsonl` that does not extend the published one (`append_only`).
3. **Re-sequence unpublished entries.** The device whose push was rejected fetches again, re-signs its new entries
   with the next `seq`, `prev` and `time` on top of the new head, and pushes again. Re-signing is safe because an
   entry no one has seen yet has never been a receipt.
4. **Never hand out an unpublished entry.** An entry becomes a receipt only once it is published. Tools MUST NOT send
   or show an entry to anyone before the push that contains it has succeeded. When receipts travel only by
   publishing, this happens naturally.

Rule 4 is what makes rule 3 safe. Together they guarantee that every entry anyone has ever seen is part of one history.
If an owner bypasses the tools and publishes two histories anyway, 3.4 applies: the pair of entries is proof, and the
offer's arbiter decides which one stands.

## 4. Roles inside one ledger

For a ledger owned by O:
- **O-authored** types: `msg.by` MUST be O's owner key or one of O's active device keys, except the owner-only types
  (`open`, `rotate`, `device`, `device_revoke`, and `recover` in the root, which hands a ledger to a new key), which
  MUST be authored by the owner key itself.
- **Counterparty** types (`claim`, `paid`, `confirmed`, `dispute`, `ruling`, `bid`, `reveal`): `msg.by` is any key;
  O records them, and the state function (6.2) decides whether they count.
- **Arbiter** types: `msg.by` MUST be the arbiter named by the offer concerned.
- `recovered` is authored and signed by the new owner key a root `recover` entry names (5.7).

A self's identity in other ledgers is its owner key: messages a self sends to other ledgers (claims, payments, bids,
reveals, disputes, rulings) are signed with the owner key, so the seller sees one buyer however many devices it has.
Device keys sign the self's own entries and the O-authored messages in them.

## 5. Message types (v1)

All amounts are integers in minor units. All references (`offer`, `claim`, `auction`, `dispute`) are entry ids in the
same ledger unless stated otherwise.

### 5.1 Ledger management (O-authored)

| type | body | meaning |
|---|---|---|
| `open` | `{"about": str, "dex": str}` | first entry of a ledger; `dex` is the dex URL. MUST be `seq` 0 |
| `rotate` | `{"key": key}` | from the next entry on, the owner key is `key`. Signed (message and entry) by the old key |
| `device` | `{"key": key, "name": str}` | from the next entry on, `key` is an active device key: it may sign entries and author every O-authored type except the owner-only ones. Owner key only |
| `device_revoke` | `{"key": key, "reason": str}` | from the next entry on, `key` is no longer a device key. Earlier entries it signed stay valid. Owner key only |
| `admit` | `{"key": key, "name": str, "note": str}` | `key` may take offers marked `"allow": "admitted"` |
| `revoke` | `{"key": key, "reason": str}` | undoes an earlier `admit` from this point on |
| `note` | `{"ref": id, "text": str}` | a correction or remark about an earlier entry. Never changes state |
| `sent` | `{"to": key, "msg": message}` | O keeps a copy of a message O sent elsewhere (proof it existed by now) |
| `receipt` | `{"ledger": ledger_id, "url": str, "header": header, "entry": entry, "keys": [entry, ...]}` | O keeps a copy of another ledger's entry about O's message. `header` is that ledger's header line, so `ledger` MUST equal `hash(header)` and the receipt verifies on its own. The embedded `entry` MUST verify against the header's owner key, or against the key the entries in `keys` lead to: that ledger's `rotate`, `device`, `device_revoke` and `recovered` entries before `entry`, in order, each signed by a key current at that point (a `recovered` entry by its own author and checked against the root, with the same rules as in the ledger, 5.7: a receipt holding a `recovered` key entry needs the root to verify, and is refused without it). `keys` is omitted when the header key signed |

### 5.2 Selling (offers)

| type | author | body |
|---|---|---|
| `offer` | O | see below |
| `withdraw` | O | `{"offer": id}` |

Offer body:

```json
{
  "item": {"title": str, "text": str, "media": [{"url": str, "hash": id}]},
  "quantity": int,
  "unit": str,
  "currency": str,
  "price": int,
  "expires": time,
  "allow": "any" | "admitted" | [key, ...],
  "pay": [{"method": str, "to": str}],
  "arbiter": {"key": key, "url": str},
  "terms": str
}
```

- `quantity >= 1`; `price >= 0` (the price per unit, in minor units).
- Media are linked, never embedded. The ledger holds only each file's address (`url`) and hash (`hash` =
  `"sha256:" + hex(SHA-256(file bytes))`). No `data:` URLs, no base64, no file contents in any entry. A verifier fetches
  the file and checks it against the hash, so pictures cannot change after a claim. If a file is later taken down, the
  record stays valid and verifiable: the page says the media is unavailable, and anyone who kept a copy can still prove
  it is the original. This keeps ledgers small and lets harmful or unwanted media be removed without breaking the
  append-only history.
- `pay` lists how to pay outside the ledger (for example `{"method": "upi", "to": "name@bank"}`). Informational.
- `expires` MAY be omitted (no expiry).

### 5.3 Price

Every offer has one fixed price per unit, set by the seller in the signed offer. It never changes. To change a price,
the seller withdraws the offer and records a new one, so every price a seller has asked stays in the ledger.

Falling prices were considered and left out on purpose; see Appendix A.

### 5.4 Buying (claims)

| type | author | recorded by | body |
|---|---|---|---|
| `claim` | buyer | seller | `{"offer": id, "offer_hash": id, "quantity": int, "price": int}` |
| `paid` | buyer | seller | `{"claim": id, "method": str, "ref": str}` |
| `received` | seller | seller | `{"claim": id, "amount": int}` |
| `delivered` | seller | seller | `{"claim": id, "note": str}` |
| `confirmed` | buyer | seller | `{"claim": id}` |

- `claim.offer_hash` MUST equal `hash(offer_entry.msg)`: the buyer signs exactly the offer they saw.
- `claim.price` is the per-unit price the buyer agrees to pay. It MUST equal the offer's `price`, so the agreed price
  is signed by both sides: the seller in the offer, the buyer in the claim.
- The buyer's copies of these messages and receipts live in the buyer's own ledger as `sent` and `receipt` entries.

### 5.5 Disputes

| type | author | recorded by | body |
|---|---|---|---|
| `dispute` | buyer or seller of the claim | seller (and MAY also be recorded by the buyer as `sent`) | `{"claim": id, "text": str, "evidence": [id or url]}` |
| `ruling` | the offer's arbiter | seller | `{"dispute": id, "outcome": "release" or "refund" or "split", "text": str}` |

- A dispute is about an accepted (or closed) claim, or an awarded auction; it comes from the buyer (or winning bidder)
  or from one of the seller's keys. While it is open, the claim takes no payment or delivery entries. A dispute takes
  one ruling; later rulings are ignored.

- `release`: the seller keeps the payment; the claim closes.
- `refund`: the seller is to return the payment (off-ledger); the claim closes as refunded.
- `split`: as described in `text`; the claim closes.
- If a seller refuses to record a ruling, the arbiter publishes it in the arbiter's own ledger (`sent`), where anyone
  can see it. Enforcement is exclusion (delisting by indexes, revocation by the root), not seizure.

### 5.6 Sealed-bid auctions

| type | author | recorded by | body |
|---|---|---|---|
| `auction` | O | O | `{"item": {...}, "currency": str, "close": time, "reveal_until": time, "best": "highest" or "lowest", "reserve": int, "allow": ..., "arbiter": {...}, "terms": str}` |
| `bid` | bidder | O | `{"auction": id, "commit": id}` |
| `reveal` | bidder | O | `{"auction": id, "amount": int, "nonce": str}` |

- `close` MUST be before `reveal_until`; `reserve >= 0`.
- `commit = hash({"amount": amount, "nonce": nonce})`. `nonce` MUST be at least 32 random lowercase hex chars. The
  bidder keeps `amount` and `nonce` private until the reveal.
- A `bid` counts only if its entry `time < close`, it is not from one of O's keys, the bidder is allowed by `allow`,
  and it is that key's first bid. Otherwise it is ignored (`late_bid`, `self_bid`, `not_allowed`, `duplicate_bid`).
- A `reveal` counts only if `close <= entry time < reveal_until`, that key bid, it is that key's first reveal, and it
  matches the commit (otherwise `early_reveal`, `late_reveal`, `no_bid`, `duplicate_reveal`, `bad_reveal`).
- The winner is the best revealed amount (`highest` for sales, `lowest` for procurement) that meets `reserve`
  (`>= reserve` for highest, `<= reserve` for lowest). Ties go to the earlier bid entry. Unrevealed bids are ignored.
- The award is computed by the state function. After `reveal_until`, O SHOULD record a `note` naming the winner.
  Payment and delivery then follow 5.4 using the auction id in place of the claim id (with the winner as buyer and
  quantity 1); before the award such entries are ignored (`not_awarded`). Disputes follow 5.5 the same way.
- Auction status: `open` before `close`, `revealing` until `reveal_until`, then `awarded` or `no_winner`, and after
  payment and delivery the claim statuses (`closed`, `disputed`, `released`, `refunded`, `split`). Statuses are judged
  at `now` (6), by default the time of the ledger's last entry.

### 5.7 Indexes and the root

An index is a ledger whose owner lists other ledgers:

| type | author | body |
|---|---|---|
| `list` | O | `{"ledger": ledger_id, "url": str, "owner": key, "note": str}` |
| `delist` | O | `{"ledger": ledger_id, "reason": str}` |

Delisting a ledger that is not listed is ignored (`not_listed`). The state lists what is listed now (6.3).

The root is a ledger whose `admit` and `revoke` entries define who is in The Matrix. A verifier MAY be given a root
ledger; then `"allow": "admitted"` (offers and auctions) means admitted in the seller's ledger AND in the root's
current state. A dex names its root in `config.json` as `"ledgdex": {"root": "<dex, file or URL>"}`.

Key recovery (lost key): the root records `{"type": "recover", "body": {"ledger": ledger_id, "key": new_key}}`
(authored by the root's owner key, never a device). The owner then appends an entry signed by `new_key` whose message is
`{"type": "recovered", "body": {"root": root_ledger_id, "entry": root_entry_id}}`, authored by `new_key`. A verifier
accepts the switch only if it can verify that root entry: given the root, the entry must be a `recover` naming this
ledger and `new_key`. Without the root, the ledger reads as broken at the `recovered` entry. A `recover` entry is
spent by the first `recovered` that cites it (`recovered: that recover entry was already used`), and is void once
the ledger has a `rotate` or `recovered` entry timed after the root's `recover` entry (`recovered: the ledger changed
its keys after the root named this key`): so a key the root once named cannot take the ledger back later. A recovery replaces
every key: from the next entry on, `new_key` is the owner and there are no device keys (the lost key may have
authorised them).

## 6. State function

`state(ledger, root=None, now=None)` replays the ledger and returns a JSON object. It is deterministic: the same input
MUST give byte-identical `canon(state)` in every implementation.

### 6.1 Replay

```
owner_key = header.owner
devices = set()
admitted = set()
offers, claims, auctions, disputes = {}, {}, {}, {}
for n, entry in enumerate(entries):
    signing_keys = {owner_key} | devices
    check structural validity (3.3) with signing_keys; on failure: broken_at = n; stop
    m = entry.msg
    if hash(m) was recorded at an earlier entry: ignore as duplicate_message; continue   # (6.2)
    apply(m, entry) by m.type (6.2)
    # key changes take effect for entry n+1
    if m.type == "rotate": owner_key = m.body.key
    if m.type == "device": devices.add(m.body.key)
    if m.type == "device_revoke": devices.discard(m.body.key)
    if m.type == "recovered": owner_key = m.by; devices = set()
return state
```

### 6.2 Rules per type

- `offer`: add `offers[id] = {remaining: quantity, status: "open"}`.
- `withdraw`: if the offer exists and is open, set `status = "withdrawn"`.
- `admit` / `revoke`: add / remove the key from `admitted`.
- `claim`: look up the offer. Reject (keep the claim, set `status = "rejected"`, set `reason`) on the first rule that
  fails, in this order:
  1. `unknown_offer`: no such offer in this ledger;
  2. `offer_changed`: `offer_hash` does not match;
  3. `withdrawn`: offer withdrawn (a sold offer falls through to `bad_quantity`);
  4. `expired`: `entry.time >= expires`;
  5. `self_claim`: the buyer is the ledger owner (a self never buys from itself);
  6. `not_allowed`: buyer not permitted by `allow`;
  7. `bad_quantity`: `quantity < 1` or `quantity > remaining`;
  8. `price_mismatch`: `price` is not the offer's `price`.
  Otherwise `status = "accepted"`, `remaining -= quantity`, and if `remaining == 0` the offer's status becomes
  `"sold"`.
- `paid`: valid only if `msg.by` is the claim's buyer and the claim is accepted; record `paid = {method, ref}`.
- In `paid`, `received`, `delivered`, `confirmed` and `dispute`, an unknown claim id is ignored as `unknown_claim`, and
  a claim that is not accepted (or closed) as `claim_not_accepted`. Wrong authors: `not_buyer`, `not_party`,
  `not_arbiter`; a confirmation before delivery: `not_delivered`; a ruling on an unknown or ruled dispute:
  `unknown_dispute`, `already_ruled`; a withdraw of an offer that is not open: `offer_not_open`.
- `received`: valid only on an accepted claim; record `received = amount`.
- `delivered`: valid only on an accepted claim; record `delivered = true`.
- `confirmed`: valid only if `msg.by` is the claim's buyer and the claim is delivered; record `confirmed = true`.
- A claim is `"closed"` when `received`, `delivered` and `confirmed` are all set.
- `dispute`: valid only from the claim's buyer or the seller, on an accepted claim; the claim's status becomes
  `"disputed"`.
- `ruling`: valid only if `msg.by` is the offer's arbiter key and the dispute exists; the claim's status becomes
  `"released"`, `"refunded"` or `"split"`.
- `bid` / `reveal`: as in 5.6.
- `list` / `delist`: add / remove `listings[ledger] = {url, owner, note}`.
- `recover`: `recoveries[ledger] = {key, entry}` (in the root).
- `sent` / `receipt`: ignored as `not_my_message` unless the message inside was authored by one of O's keys.
- A message recorded again (the same `hash(msg)` as an earlier entry's) is ignored as `duplicate_message`, whatever
  its type, and changes no keys: a signed message counts once. Without this a seller could record one signed claim
  twice, or replay an old `device` message after its `device_revoke`. Messages that should repeat differ in `at`.
- Messages that are structurally valid but fail a rule here (wrong author, wrong state) are kept and listed in
  `state.ignored` with a reason. They never break the ledger.

### 6.3 Output

```json
{
  "ledger": "sha256:...",
  "owner": "ed25519:<current owner key>",
  "devices": ["ed25519:<active device key>", "..."],
  "head": {"seq": 41, "id": "sha256:..."},
  "broken_at": null,
  "admitted": ["ed25519:...", "..."],
  "offers": {"<id>": {"title": str, "remaining": int, "status": str}},
  "claims": {"<id>": {"offer": id, "buyer": key, "quantity": int, "price": int, "status": str,
                       "reason": str, "paid": {...}, "received": int, "delivered": bool, "confirmed": bool}},
  "auctions": {"<id>": {"status": str, "bids": int, "winner": key, "amount": int,
                         "paid": {...}, "received": int, "delivered": bool, "confirmed": bool}},
  "disputes": {"<id>": {"claim": id, "ruling": id}},
  "listings": {"<ledger id>": {"url": str, "owner": key, "note": str}},
  "recoveries": {"<ledger id>": {"key": key, "entry": id}},
  "ignored": [{"seq": int, "reason": str}]
}
```

Keys that do not apply are omitted (not `null`), except `broken_at`, which is `null` when the ledger is whole.

The state is keyed by ids, which do not match rule 2 of 1.2. For `canon(state)` only, object keys MAY be any
printable ASCII string (U+0021..U+007E); they still sort by byte value, so every implementation gives the same bytes.

## 7. Every ledgdex is a dex

### 7.1 Layout

```
my-dex/
  data.json        dex pages: the author's own pages plus the pages ledgdex generates (7.2)
  config.json      dexweb template, and "publish" with "append_only" (7.4)
  styles.css       dexweb styles
  run.py           dexweb build script, as in every dex
  gen/             the website, built by dexweb
  gen/ledgdex.jsonl  a byte-for-byte copy of the ledger, written by render (7.3), so the site serves it
  ledgdex.jsonl    this self's ledger (the source of truth)
  key.pub          this self's current public key (one line), for convenience
```

- A ledgdex MUST be a complete dex: `ledgdex init` creates all of the files above, and every change to the ledger is
  followed by a render (7.3), so the built website always shows the current state. Publishing it (7.4) is a separate,
  manual step.
- The ledger is read at `<dex url>/ledgdex.jsonl`, next to `index.html`.
- A ledger lives in exactly one dex. A dex holds at most one ledger.
- The website is a view. Where the website and `ledgdex.jsonl` disagree, `ledgdex.jsonl` is right.
- Private keys live outside the dex. Every device that appends has its own device key, for example
  `~/.ledgdex/<name>-<device>.key` (mode 600), or in the browser's key store. Everyday commands (offers, recording
  claims, payments, delivery) sign with the device key.
- The owner key is usually kept on one of the owner's devices too, as its own file, `~/.ledgdex/<name>-owner.key`.
  Tools load it only for owner-only actions (`device`, `device_revoke`, `rotate`) and never for everyday commands.
  Keeping it offline (paper, a USB stick) is safer and optional.
- A lost device that held only a device key is handled with `device_revoke`. A lost device that held the owner key
  needs `rotate` from another copy of the owner key, or root recovery (5.7) if there is none. Keep a backup of the
  owner key.

### 7.2 Generated pages

ledgdex writes pages into `data.json` in the ordinary dex format (`{"title": str, "body": [str, ...]}`). A generated
page is marked by its first body string starting with `<!-- ledgdex -->`, followed by a one-line summary of the page
(dexweb shows a page's first paragraph on the index, and the comment is invisible). On every render,
ledgdex removes all marked pages and writes them again; pages without the marker are the author's own and are never
touched. Generated pages follow the plain-HTML rules of the dex: no classes, no inline styles, no scripts.

Pages, in this order:

1. **Ledger** (title: the header's `name` + ` ledger`). The `open` text; the owner key and device keys; the ledger id; the head
   (`seq` and id); the verification result (`whole` or `broken at seq n`); a link to download `ledgdex.jsonl`; links to
   every offer and auction page; then every entry in order, one line each: `seq`, `time`, `type`, author key, a short
   summary, and the entry id.
2. **One page per offer** (title: `item.title`). The item text and media links (with their hashes); status and
   quantity remaining; the price; payment methods; the
   arbiter; terms; who may buy; and how to buy: the offer id and `offer_hash` a claim must carry, and where to send it.
   Below that, the claims on this offer: claim id, buyer key, quantity, price, status.
3. **One page per auction** (title: `item.title`). Item, close and reveal times, the rule (`highest` / `lowest`),
   reserve, number of bids, status; after `reveal_until`, the winner and amount; how to bid and reveal.
4. **Purchases** (title: the header's `name` + ` purchases`), only if the ledger has `sent` claims. Every claim this
   self sent, and the receipt held for it, with the seller's claim id.
5. **Listings** (title: the header's `name` + ` listings`), only in index ledgers. Every listed ledger with its
   owner key and a link to its dex.
6. **Admissions** (title: the header's `name` + ` admissions`), only if the ledger has `admit` entries. Admitted
   keys, with names and the entries that admitted or revoked them.

Titles are HTML-escaped. dexweb names a page's file after the letters and digits of its title, so collisions are by
file name: a generated title that collides with an author page gets ` (ledgdex)` appended, and a generated title that
collides with an earlier generated one gets the first 8 hex characters of its entry id. Dates are written as in 1.1. Amounts are
written in the currency's major unit with the exact integer in brackets, for example `INR 20,000.00 (2000000)`.

Rendering is deterministic: the same ledger and the same author pages always produce the same `data.json`.

### 7.3 Render

`render(dex)`:
1. read `ledgdex.jsonl` and compute the state (section 6);
2. rewrite the generated pages in `data.json` (7.2);
3. copy `ledgdex.jsonl` to `gen/ledgdex.jsonl`, byte for byte;
4. build the site with dexweb (`dexgen.Dexgen()`, as in `run.py`).

`ledgdex offer`, `ledgdex record` and every other command that appends to the ledger render automatically. Rendering
never publishes.

### 7.4 Publish

A ledgdex is published with dexweb (4.2.5 or later), like any other dex. `ledgdex init` writes `publish` in
`config.json` with `append_only`:

```json
"publish": {"dest": "git@github.com:username/username.github.io.git", "branch": "main", "append_only": ["ledgdex.jsonl"]}
```

- `dest` is the repository address, as in every dex. All dexweb publish options apply (`branch`, `site_path`,
  `remote`, `message`).
- `"append_only": ["ledgdex.jsonl"]` makes dexweb refuse any publish in which the published `ledgdex.jsonl` is not
  the exact start of the new one. A rewritten, shortened or deleted ledger is never published, whoever runs
  `run.py`. `ledgdex publish` refuses to run if `append_only` does not list `ledgdex.jsonl`.
- `Dexweb().published("ledgdex.jsonl")` returns the published ledger as text, or `None` if nothing is published yet.
  It fetches from the remote and never changes the dex.

`ledgdex publish DEX` implements 3.5:
1. **Catch up.** `old = Dexweb().published("ledgdex.jsonl")`. If `old` is `None` or the local ledger starts with
   `old`, go to step 2. Otherwise verify `old` (3.3); it MUST be whole and have the same ledger id, or publishing
   stops with an error. Keep the longest run of whole lines the two ledgers share. Local entries after it are
   unpublished: re-sign them in order on top of the published head (new `seq`, `prev` and `time`), write the result
   to `ledgdex.jsonl`, and render (7.3). If the shared run is shorter than `old`, the published entries after it win:
   they are receipts already.
2. **Publish.** `Dexweb().publish()`. `True`: every entry in the file is now published, and only now may it be shown
   or sent (3.5 rule 4).
3. **Retry.** `False`: call `published()` again. If it changed since step 1, another device published first: go back
   to step 1, at most 3 times. If it did not change, publish once more (another dex may share the repository and
   have pushed at the same moment); if that fails too, stop and report dexweb's message (no network, no git, push
   rights).

Two devices that both publish to one dest are safe: git rejects the second push, and step 1 re-sequences its
entries. Method `"folder"` also honours `append_only`, but has no atomic step, so it is for a single device only.
## 8. Transport

Reading: fetch `<dex url>/ledgdex.jsonl` over HTTP (7.1), or clone the dex's git repository, or copy the file. Verification
needs only the file (and, for `"admitted"` offers and recovery, the root ledger).

Sending a message to a ledger owner: any channel that carries a JSON file: email attachment, git pull request, form
upload, USB. The owner's tool validates the message and records it. The sender records a `sent` entry in their own
ledger and, once the owner's entry is published, a `receipt` entry.

## 10. Bots and pay per clean (draft, not built)

This section extends sections 5 and 6 for selves that are machines, selling a service one unit at a time to many
buyers, from several competing sellers. It is a draft: until it is built (milestone 11), the rules above apply.

### 10.1 One claim per unit, with a deadline

Each unit of service (one clean) is one claim of `quantity` 1 on the offer of the seller (robot) that takes it. The
flow of 5.4 is unchanged: claim, `delivered`, `confirmed`, `received`. Two additions:

| type | change | body |
|---|---|---|
| `claim` | adds optional `deliver_by` | `{"offer": id, "offer_hash": id, "quantity": int, "price": int, "deliver_by": time}` |
| `delivered` | adds optional `evidence` | `{"claim": id, "note": str, "evidence": [{"url": str, "hash": id}]}` |
| `received` | adds optional `ref` | `{"claim": id, "amount": int, "ref": str}` |

- `deliver_by` (default for a buyer's agent: 30 minutes after the claim): if no `delivered` for the claim is recorded at an entry time `< deliver_by`, the claim **lapses**: at
  the first entry at or after `deliver_by`, or at `now` (6) when judging state, its status becomes `lapsed`, its
  quantity returns to the offer's `remaining` (an offer `sold` becomes `open` again if it has not expired), and later
  `paid`, `received`, `delivered` and `confirmed` for it are ignored (`claim_lapsed`). Nothing is owed for a lapsed
  claim. The buyer then claims the unit from another seller.
- `evidence` follows the media rule of 5.2: linked by address and hash, never embedded. Proof of a clean is a photo:
  the evidence MUST hold at least one image, and the buyer's agent confirms only after fetching it and checking its
  hash.
- `received.ref` names how the payment arrived, for example the clearing ledger's `settle` entry id (10.3).

### 10.2 Daily offers and availability

A seller states its availability through ordinary offers (5.2): each day it offers the units it can deliver that day
(`quantity`), at its price, with `expires` at the end of the day. A seller that becomes unavailable withdraws its
offer, so its unclaimed units can no longer be claimed; units already claimed lapse at their deadline if it does not
deliver them. Buyers choose among the open offers of every seller listed in the place's index (5.7), by their own
rule. Nothing ties a buyer to one seller.

### 10.3 Credits and daily clearing

A clearing ledger keeps credits: amounts in a currency it names (for example `MALL`), which are promises of its owner
(the mall), not money on the ledger. Real money moves outside, when a self buys credits or cashes them out.

| type | author | body |
|---|---|---|
| `credit` | clearing owner | `{"to": key, "amount": int, "currency": str, "ref": str}`: credits bought (`ref`: the outside payment) |
| `settle` | clearing owner | `{"period": str, "from": key, "to": key, "amount": int, "currency": str, "claims": [{"ledger": ledger_id, "claim": id}]}` |
| `payout` | clearing owner | `{"to": key, "amount": int, "currency": str, "ref": str}`: credits cashed out (`ref`: the outside payment) |

- State of a clearing ledger: `balances[key][currency]`, starting at 0. `credit` adds; `payout` and the `from` side of
  `settle` subtract; the `to` side of `settle` adds. An entry that would take a balance below 0 is ignored as
  `insufficient_credit`: credits never go negative. `amount >= 1`.
- `period` is the day settled (`2026-10-01`), a local date of the place: the day closes at midnight there. After each
  day closes the clearing owner records one `settle` per buyer
  and seller that traded that day: the confirmed claims (in the seller's ledger) not yet settled, and `amount` = the
  sum of their prices. Anyone can recompute it from the seller's ledger and the buyer's receipts; a `settle` that
  lists a claim that is not confirmed, already settled, or of another buyer, or whose amount is not the sum, is
  evidence of a wrong settlement, reported by `check` (9.1) as `bad_settlement`.
- After a settlement, the seller records `received` for each claim it covers, with `ref` = the `settle` entry id. A
  claim is `closed` as in 6.2.
- Refunds: when the arbiter rules `refund` on a clean already settled, the next day's settlement pays it back as a
  `settle` from the seller to the buyer listing that claim.

### 10.4 Machines as selves

- A machine's owner key stays with its operator, off the machine; the machine appends with a device key (5.1). A lost
  or stolen machine is revoked with `device_revoke`.
- Messages to other ledgers are signed with the owner key (4). A robot only sells and delivers, so it needs only its
  device key; a shop's system that claims needs the shop's owner key, or the shop's operator signs for it.
- A place (the mall) runs the index (5.7) that lists the selves there, the root (5.7) that admits them, and the
  clearing ledger (10.3), as three ledgers or one ledger in all three roles. It is also the arbiter named in offers.

### 10.5 Transport between machines

Sending is publishing (8). On a local network, every self serves its dex over plain HTTP (its own device, or a folder
the place hosts), and each self's agent (10.6) polls the ledgers it trades with. No git, no outside service.

### 10.6 Agents

An agent is a program that acts for one self by rules, without a person:

- **seller** (a robot): each morning, offer the day's units; withdraw when unavailable; record new `sent` claims from
  selves listed in the index; when a unit is done, record `delivered` with evidence; after each `settle`, record
  `received`; keep receipts.
- **buyer** (a shop): when a unit is needed, claim it from an open offer chosen by its rule, with a deadline; confirm
  delivered units whose evidence checks out, and dispute those that do not; when a claim lapses, claim from another
  seller; keep receipts.
- **clearing** (the place): after midnight, record one `settle` per buyer and seller for the day's confirmed claims
  not yet settled, and one `settle` back for each refund ruled since.

Agents poll; how often is theirs to choose. Every action is an ordinary message or entry under sections 2 to 6, so a
person can audit it, and `check` (9.1) catches an agent that misbehaves.

## 9. Security invariants

An implementation is correct only if all of these hold, and the test suite checks each:

1. Changing any byte of any line breaks verification at that line or a later one.
2. A message signed by key A never verifies as authored by key B.
3. An entry signed by anyone other than a current signing key (owner key or active device key) breaks the ledger at
   that entry, including a device key after its `device_revoke`.
4. A claim whose `offer_hash` does not match the offer is rejected.
5. Quantity never goes below zero; two claims cannot both take the last unit.
6. A claim is accepted only at the price in the signed offer, never at a value supplied by a page.
7. A bid cannot be read before `close` (only its commit is visible) and cannot be changed after it is made.
8. `canon(state)` is byte-identical in the Python and JavaScript implementations for every test ledger.
9. Two valid entries at the same `seq` with different ids are reported as equivocation.
10. A receipt in a buyer's ledger verifies on its own, without fetching the seller's ledger: the entry's signature,
    and, for a device key, the owner-signed `device` entry that authorised it. (Whether that device was revoked before
    the entry is checked only against the full ledger.)
11. Rendering never changes `ledgdex.jsonl` and never changes a page without the `<!-- ledgdex -->` marker.
12. A published `ledgdex.jsonl` is only ever extended: no publish removes or changes a line that was published (7.4).
13. A message recorded twice counts once (`duplicate_message`, 6.2), and canonical JSON deeper than 32 levels is
    refused (1.2 rule 9).
14. Pages never make a link of an address that is not `http://` or `https://` with no space or control character:
    anything else a ledger names (`javascript:`, `data:`) is shown as text.
15. Secret keys never leave the self's machine, and are never written where others can read them: key files are
    mode 600 and refused otherwise; in the browser a key is stored only sealed with a passphrase (PBKDF2-SHA-256,
    600,000 rounds, AES-256-GCM), and a bid's secret only sealed with a key derived from the secret key.
16. Two appends to one ledger at once cannot both take the same `seq` (a lock), and an append is on disk (fsync)
    before the command reports it.
17. No signature by a small-order public key verifies (1.3), so no one can sign for a key no one holds.
18. A receipt's `recovered` key entry is checked against the root (5.1, 5.7); a root `recover` is owner-only, spent
    once, and void after a later key change; so no one but the root's owner can hand a ledger to a new key.
19. `check` blames a ledger only with that ledger's own signatures: a receipt entry signed by a key the ledger did
    not have at that seq (a revoked device, a made-up key chain) is a warning (`receipt_bad_signer`), and a receipt
    address that never served the ledger is a warning (`receipt_url_mismatch`), not `ledger_changed`.

### 9.1 Checks over time

Verification (3.3) proves a ledger is consistent and signed by its owner, not that it is the history shown before:
an owner can re-sign every entry from some point on. `check` closes that gap with the copies other selves hold.
A checker keeps the last copy it saw of every ledger it checks, outside every dex's `gen/`, and reports:

- **error `equivocation`**: a ledger differs from the copy seen before at some `seq`. The two entries, both signed by
  the owner key, are saved as proof (3.4).
- **error `receipt_mismatch`**: a copy of a ledger has an entry other than the one a receipt holds at that `seq`. The
  receipt is the proof.
- **error `ledger_changed`**: an address serves a different ledger (another ledger id) than it served before, or than
  the receipts naming it say.
- **error `broken`**, **error `media_changed`** (an offer's media no longer matches its hash), **error
  `published_differs`** (a dex's published ledger is not the start of its own).
- **warnings** `stale` (a copy is an exact start of the copy seen before: a cache, an old snapshot or withheld
  entries; nothing signed changed), `receipt_not_visible`, `unreachable`, `media_unavailable`, `behind`.

Receipts are checked against every copy of their ledger the checker has: the receipt's address, the ledger's own dex
address (from its `open` entry), copies checked in the same run, and the copy seen before. A checker runs by hand,
from cron, as a worker, or as a GitHub workflow; its exit code is 1 only on errors.

A checker reads every ledger in full (never from the verification cache). An address it finds inside a ledger (a
receipt's `url`, a listing) is read only over http(s), or, for ledgers kept on one machine, as a dex folder or a
`.jsonl` file: never any other local file. Redirects are followed only to http(s), and no read takes more than
`LEDGDEX_MAX_BYTES` (64 MiB by default). Offer media are fetched only over http(s).

### 9.2 Clock skew (300 seconds)

An entry's `time` is its owner's clock; a message's `at` is its author's. Rule 7 of 3.3 lets an entry be recorded up to
300 seconds before the message it records says it was signed, so that two selves whose clocks differ a little can
still trade. What that allows:

- **Back-dating by up to 5 minutes.** An owner can record a message with an entry `time` up to 5 minutes earlier than
  the message's own `at`. Where a rule turns on time (an offer's `expires`, an auction's `close` and `reveal_until`,
  a claim's `deliver_by`), a seller can let in a claim, bid or delivery up to 5 minutes late, or turn one away up to
  5 minutes early by recording a later time. Both are signed and visible; neither can be hidden from a check.
- **Ordering among close claims.** Within the skew, the seller orders claims that arrive together as it likes (Part I
  already lists this as not protected).
- **No bound on the other side.** Rule 7 bounds how early an entry can be; it does not bound how late. An owner can
  hold a message for hours before recording it (also listed as not protected): the buyer's `sent` entry shows when it
  existed.
- **A wrong clock breaks nothing silently.** A device whose clock runs more than 5 minutes behind its counterparties
  cannot record their fresh messages until it catches up (the tool refuses); a clock running ahead makes its entries
  look late. Devices SHOULD keep time by NTP.

Deadlines that matter more than 5 minutes (a day's settlement, a 30-minute clean) are not at risk. A sealed-bid
auction should close more than 5 minutes after the last bid it must accept.

---

# Part III: build plan (for a coding agent)

## Constraints

- No third-party packages. Python: standard library only, plus dexweb (first-party, the dex builder, 4.2.5 or
  later) for rendering and publishing. JavaScript: no npm; plain browser JS (ES2020).
- Vendor a pure Ed25519 implementation in both languages, written from RFC 8032 (section 5.1 and the Python reference
  code in section 6). In the browser, use Web Crypto's Ed25519 when available and fall back to the vendored code.
  Python's `hashlib` provides SHA-256; browsers provide it through Web Crypto (and the vendored code MAY include its own).
- A platform Ed25519 MAY be used instead of the vendored code when it is available (Python: the optional
  `cryptography` package; browsers: Web Crypto), only after it passes a known-answer test, and only behind the same
  strictness as the vendored code (non-canonical `s` and point encodings are rejected first), so a ledger verifies the
  same either way.
- Verification MAY be cached by the exact bytes already verified (ledger id, length and SHA-256 of that prefix):
  a ledger that only grew is verified from where it was verified before, and any changed byte misses the cache.
- Every function has one Python and one JavaScript implementation with the same name and behaviour.
- All tests run offline.

## Files to produce

The repository root is https://github.com/matrixdex/ledgdex.

```
ledgdex/
  LICENSE                 CC0 1.0
  README.md               how to sell and buy
  architecture/SPEC.md    this file
  py/
    pyproject.toml        installs the ledgdex command
    ledgdex/canon.py      canonical JSON (1.2)
    ledgdex/ed25519.py    vendored Ed25519 (RFC 8032)
    ledgdex/sig.py        Ed25519 backend: cryptography when installed and passing its self-test, else vendored
    ledgdex/core.py       messages, entries, verification (2, 3)
    ledgdex/state.py      state (6)
    ledgdex/dex.py        the ledger file in a dex, keys in ~/.ledgdex, reading other ledgers (7.1, 8)
    ledgdex/render.py     generated dex pages and the dexweb build (7.2, 7.3)
    ledgdex/publish.py    catch-up, re-sequencing and dexweb publish (7.4)
    ledgdex/check.py      tamper checks over time and the GitHub workflow template (9.1)
    ledgdex/cli.py        command-line tool
    tests/                unittest suite
    tests/make_vectors.py writes the shared vectors; test_vectors.py checks they are current
  js/
    sha.js                SHA-256 and SHA-512, synchronous
    canon.js  ed25519.js  core.js  state.js     the same functions as the Python modules
    render.js             the dex pages (7.2), byte for byte as render.py
    dexweb.js  zip.js     a complete dex as dexweb builds it, downloaded as a zip
    sig.js                signing with Web Crypto's Ed25519 when the browser has it, else the vendored code
    viewer.js             the viewer page's script
  viewer/                 the viewer, a dex: data.json config.json styles.css run.py (dexweb, published to docs/)
  docs/                   the published viewer dex (GitHub Pages)
    test.mjs              node js/test.mjs: JavaScript against the shared vectors
  vectors/                shared test vectors used by both test suites: ed25519.json, canon.json, signatures.json,
                          ledgers/ (test ledgers with their expected verification and canon(state)), pages.json
                          (their dex pages) and dex/ (whole dexs built by dexweb)
```

## Command-line tool

```
ledgdex keygen NAME                              write ~/.ledgdex/NAME.key and print the public key
ledgdex init DEX --name N --key K [--about A] [--url U] [--dest D] [--branch B] [--site-path P]
                                                 create a complete dex (7.1) with its ledger and "open" entry, then render
seller
ledgdex offer DEX offer.json                     sign and record an offer (body from file; unit, allow, pay, terms,
                                                 arbiter, item.text and item.media get defaults)
ledgdex withdraw DEX OFFER_ID
ledgdex record DEX [FILE...] [--from BUYER]      record claims, payments and confirmations: from message files, or
                                                 collected from a buyer's ledger ("sent" messages addressed to DEX)
ledgdex received DEX CLAIM_ID AMOUNT
ledgdex delivered DEX CLAIM_ID [--note N]
ledgdex admit DEX KEY [--name N] [--note N]
ledgdex revoke DEX KEY [--reason R]
ledgdex note DEX REF TEXT
buyer
ledgdex claim DEX SELLER OFFER_ID [--quantity Q] sign a claim at the offer's price, keep it as "sent", write the file
ledgdex pay DEX SELLER CLAIM_ID --method M [--ref R]
ledgdex confirm DEX SELLER CLAIM_ID
ledgdex receipt DEX SELLER [--entry ID]          keep the seller's entries that record this self's messages
disputes
ledgdex dispute DEX CLAIM_ID [--seller SELLER] [--text T] [--evidence E]...
                                                 buyer: with --seller, in the seller's ledger; seller: in its own
ledgdex ruling DEX SELLER DISPUTE_ID --outcome release|refund|split [--text T]      arbiter
auctions
ledgdex auction DEX auction.json                 start a sealed-bid auction (allow, terms, best, reserve, arbiter
                                                 get defaults)
ledgdex bid DEX SELLER AUCTION_ID --amount N     the amount and nonce stay in ~/.ledgdex/bids until the reveal
ledgdex reveal DEX SELLER AUCTION_ID
keys
ledgdex device add DEX KEY [--name N]            record a "device" entry (needs the owner key); KEY is a public key
ledgdex device revoke DEX KEY [--reason R]       or the name of a key in ~/.ledgdex
ledgdex rotate DEX --key NAME                    replace the owner key (made if missing)
ledgdex recover ROOT_DEX LEDGER KEY              root: name a new key for a ledger whose owner lost theirs
ledgdex recovered DEX --root ROOT --key NAME     owner: take the ledger back; saves the root in config.json
indexes
ledgdex list DEX LEDGER [--url U] [--note N]
ledgdex delist DEX LEDGER_ID [--reason R]
ledgdex discover INDEX [--offers] [--json]       the ledgers an index lists, and what they sell
anyone
ledgdex sign TYPE body.json --key NAME           print a signed message
ledgdex verify DEX_OR_URL [--full] [--root R]    structural check; exit code 0 only if whole
ledgdex state DEX_OR_URL [--root R]              print canon(state)
ledgdex check [SOURCE...] [--every S] [--media] [--published] [--json F] [--state D] [--root R]
                                                 tamper checks over time (9.1); exit code 1 on errors
ledgdex workflow SOURCE... [--cron C] [--media]  print a GitHub Actions workflow that runs check
ledgdex render DEX                               rewrite the generated pages and rebuild the site (7.3)
ledgdex publish DEX                              catch up, re-sequence and publish with dexweb (7.4)
```

SELLER is the seller's dex URL, dex folder or ledger file. Sending is publishing: a buyer's messages are kept in the
buyer's ledger as `sent`, so a seller can collect them from the buyer's published dex with `record --from`.

With a device key on a machine, everyday commands there sign with it; owner-only types and messages to other ledgers
use the owner key (4).

The viewer is itself a dex (`viewer/`, built with dexweb and published to `docs/`), and does the reading and signing
in the browser: it loads a ledger from an address or a file, verifies it, shows it as the pages its dex has (7.2),
and signs `claim`, `paid`, `confirmed`, `dispute`, `bid` and `reveal` messages as downloadable files. It also keeps
the viewer's own ledger (new, or opened from a file or address): each message it signs is appended as `sent`,
"collect receipts" appends `receipt` entries for the loaded ledger's records of them, and "download your dex" gives
the ledger as a complete dex (7.1), file for file what `ledgdex init` and dexweb make. So a browser-only self is a
ledgdex too, with full triple entry. It never needs a server of its own, and its key is generated or imported in the browser
and never uploaded. It is kept in the browser only sealed with a passphrase (invariant 15), and can be downloaded as
a backup. A bid's amount and nonce are kept until the reveal, sealed with a key derived from the secret key. The
viewer's pages carry a Content-Security-Policy: scripts only from the viewer itself.

## Build status

All ten milestones are built, plus indexes (5.7), the root, checks over time (9.1), the fast Ed25519 backend and the
verification cache. Python has everything; JavaScript has the core (canonical JSON, SHA-256/512, Ed25519, messages,
verification, state) and the viewer, and reproduces every shared vector byte for byte. Ed25519 vectors come from
djb's `sign.input` (as shipped in `cryptography_vectors`), whose first three rows are RFC 8032 section 7.1 TEST 1 to 3.

Differential fuzzing (`py/tests/fuzz.py`) runs random ledgers of every type, byte and line corruptions, field
changes re-signed so they reach the deeper rules, and tricky JSON texts through both languages, and fails on any
difference in a verdict, a breaking point, a reason or `canon(state)`. It found a Python crash on a non-string `type`,
Python reading `true` as 1, and JavaScript dropping a leading byte-order mark; all three are fixed and kept as vectors.
CI fuzzes a new seed on every push.

Section 10 (bots, pay per clean) is a draft and not built; milestone 11 builds it.

**v1.0.0** followed a security audit, which added: `duplicate_message` (6.2), the nesting limit (1.2 rule 9),
http(s)-only links (invariant 14), safe reading of addresses found in ledgers (9.1), private key files and sealed
browser keys (invariant 15), locked appends (invariant 16), a trusted-only verification cache, checked command-line
ids, and a check workflow pinned to a release and to action commits. The threat model is in `SECURITY.md`.

**v1.0.1** fixes a forgery found by a second audit: Ed25519 verification accepted small-order public keys, for which
one signature verifies for every message, so anyone could write a whole valid-looking ledger owned by such a key
(1.3, invariant 17). A shared vector now holds every free text a ledger can carry as markup, and a test checks that
every page of every vector carries only text, `<code>`, `<br>` and safe links. The viewer reads only http(s)
addresses, at most 64 MiB, without credentials.

**v1.0.2** fixes what a third audit found in receipts and recovery: a receipt could carry a `recovered` key entry
signed by anyone, so a buyer could forge a receipt and `check` would report the honest seller as tampering
(invariant 18; vector `broken-forged-receipt`); a root device key could hand any ledger to a new key; and a root
`recover` entry could be used again later by a key it once named (vector `broken-recovery-replay`). `check` now
blames a ledger only with signatures valid in that ledger's own history (invariant 19).

In the browser, signing uses Web Crypto's Ed25519 when the browser has it and it gives the RFC 8032 answers
(`js/sig.js`), and the vendored code otherwise; the tests check both give the same keys, signatures, messages and
ledgers, which closes milestone 2. Verification stays with the vendored code in every browser.

## Milestones and acceptance tests

1. **Encoding.** Canonical JSON and hashing. Vectors: nested objects, key order, every escape case, Unicode
   (Devanagari, emoji), integer limits, rejection of floats and bad keys. Python and JS outputs byte-identical.
2. **Signatures.** Vendored Ed25519 passes every RFC 8032 section 7.1 test vector in both languages (copy them from the
   RFC; do not retype from memory). Web Crypto and vendored JS agree.
3. **Ledger.** Header, entries, chaining, structural verification (3.3). Tests: tamper each field of each line;
   reorder lines; drop a line; wrong signer; time going backwards; message recorded too early. Two devices racing
   to append (3.5, 7.4), each with its own clone of one bare test repository: the second push is rejected, its
   entries are re-sequenced, and the published ledger never holds two entries at one `seq`. Media rule (5.2): an offer with embedded media is rejected.
4. **Offers and claims.** Every rejection reason in 6.2, in order, including `price_mismatch`. Last-unit race: two claims for one remaining unit → first accepted, second
   `bad_quantity`.
5. **Triple entry.** `sent` and `receipt` in the buyer's ledger; receipt verifies standalone (invariant 10).
   End-to-end test: seller and buyer ledgers, full trade to `closed`.
6. **Dex.** `ledgdex init` creates a complete dex; `render` writes the generated pages (7.2) and builds with dexweb.
   Tests: author pages are never changed; rendering twice gives identical `data.json`; every offer, claim and listing
   appears on its page; generated pages contain no classes,
   styles or scripts; a collision with an author page title gets ` (ledgdex)`; `gen/ledgdex.jsonl` equals
   `ledgdex.jsonl`. Publish (7.4), against a local bare repository: the first publish; an append publishes; a
   rewritten or shortened ledger is refused (invariant 12); `ledgdex publish` refuses a `config.json` without
   `append_only`.
7. **Disputes.** Dispute and ruling, wrong-arbiter ruling ignored.
8. **Auctions.** Commit-reveal, late bid, late reveal, wrong nonce, tie, reserve, lowest-wins procurement.
9. **Keys.** `rotate`; `device` and `device_revoke` (a device signs offers and records claims; a device cannot author
   owner-only types; an entry signed by a revoked device breaks the ledger; entries it signed before revocation stay
   valid); root `admit`/`revoke`; `recover`/`recovered`; equivocation detection.
10. **Viewer.** Loads a ledger from a URL or file, shows verification result and state, and produces signed `claim`, `paid`, `bid` and `reveal` messages as downloadable JSON.

A milestone is done when its tests pass in both languages and the shared vectors produce identical state.

## Milestone 11: robots paid per clean (draft)

Build 10 and run it as a simulation:

- **Spec and state.** `claim.deliver_by` and lapsing (`lapsed`, `claim_lapsed`, units back to the offer),
  `delivered.evidence`, `received.ref`; `credit`, `settle`, `payout` and balances; `insufficient_credit` and
  `bad_settlement`. Python and JavaScript, with shared vectors and fuzzing as for every other type.
- **Python API.** `ledgdex.Self(dex)`: offer, claim, record, deliver, confirm, receipt, settle and the rest as calls,
  without rebuilding the site after every step (render once per cycle).
- **Agent.** `ledgdex agent DEX --role seller|buyer|clearing --rules rules.json`: the polling loops of 10.6.
- **Simulation.** `examples/mall/`: robots from two operators, several shops and the mall, each a dex served over
  local HTTP, running simulated days: daily offers, claims, cleans with evidence, confirmations, a robot going
  unavailable mid-day so its claims lapse and the shops claim from the other robot, one dispute ruled by the mall,
  daily settlement, receipts. Acceptance: every ledger whole; each day's settlement equals the cleans confirmed that
  day; nothing is owed for a lapsed claim; `check` passes on every ledger; and a robot whose device key is revoked
  cannot record cleans.

## Future improvements

Hardening that is not built yet:

1. **Keys at rest on disk.** Browser keys are sealed (invariant 15); key files in `~/.ledgdex` are private (mode
   600) but not encrypted. Encrypt them with a passphrase, or keep them in the operating system's key store (and a
   hardware key where there is one). This matters most for machines (10.4) and shared computers.
2. **Constant-time signing everywhere.** The vendored Ed25519 is not constant time. Python signs with the
   `cryptography` package and browsers with Web Crypto when present, and the command line warns when it falls back;
   make the constant-time backend required for production machines. Verifying is not affected.
3. **State at scale.** Every command replays the whole ledger for its state and rebuilds the pages. Cache the state
   with the verification cache (by the same verified prefix), and render only the pages that changed.
4. **An independent verifier.** Both implementations were written by one author, the JavaScript after the Python.
   Have a third verifier written from this specification alone, by someone else, and run it against the shared
   vectors and the fuzzer.
5. **Web Crypto for verifying, and locked keys.** Signing already uses Web Crypto (Build status). Verifying with it
   too would be faster on large ledgers but makes verification asynchronous, so it waits until ledgers need it. Web
   Crypto can also hold a key that pages can use but never read: offer that for browsers left unattended (a shop's
   screen, a robot's dashboard), with the trade-off that such a key cannot be backed up.
6. **Browser tests in CI.** Run the viewer's end-to-end tests (in Chromium) on every push, not only by hand.
7. **Packaging.** Publish ledgdex on PyPI so `pip install ledgdex` works, and so the check workflow installs a release.
8. **Delegated admission.** A `delegate` type, letting the root name other ledgers that may admit (Decision 4).

## Out of scope for v1

- Moving money on the ledger (payments stay outside; the ledger records them).
- Any consensus between several operators (k-of-n), networking daemons, or gossip.
- Encryption of ledger contents (everything is public).
- Multi-unit auctions and partial fills beyond `quantity` on claims.

## Decisions

1. **The Matrix's own unit is USD.** Amounts in USD are integer cents (`150000` is USD 1,500.00). Whether the 100K
   plan becomes a ledger flavor is still open.
2. **Default arbiter: the root.** An offer or auction that names no arbiter gets the root's owner as its arbiter (key
   and dex address); today that is Noorul Ali, founder of The Matrix (manonthemoon13131@gmail.com). `ledgdex offer`
   and `ledgdex auction` fill it in when the dex names its root (`config.json`: `"ledgdex": {"root": ...}`), and fall
   back to the seller itself when it names none. The arbiter is always signed into the offer, so a buyer sees it
   before claiming.
3. **Clock skew stays 300 seconds** (3.3 rule 7). Its risks are in 9.2.
4. **The root is run by the founder, Noorul Ali,** from a dex of its own (see "Running the root" in the README).
   Admission is not delegated yet; a `delegate` type, letting the root name other admitting ledgers, is future work.
5. **Section 10:** the day closes at midnight in the place's local time, and each day is settled after it closes
   (`settle.period` is that local date); a shop gives a robot 30 minutes to clean (`deliver_by` = claim time + 30
   minutes by default); credits cannot go negative; a `refund` ruling on a clean already settled is paid back in the
   next day's settlement, as a `settle` from the robot to the shop listing that claim; proof of cleaning is a photo:
   `delivered.evidence` MUST hold at least one image (linked by address and hash), and the buyer's agent confirms
   only after fetching it and checking its hash.

---

# Appendix A: falling prices (not in v1)

This appendix records a design that was proposed and left out, so a later reader does not add it back by accident.

## What it was

Instead of a fixed price, an offer carried a schedule: `{"start": int, "floor": int, "step": int, "every": int,
"from": time}`. The price fell on its own until someone claimed it:

```
if t < from: not available
k = (t - from) // every          # integer division, t in seconds
price(t) = max(floor, start - step * k)
```

A claim was accepted if the buyer's signed price was at least `price(entry.time)` at the moment the seller recorded it.

## Why it was proposed (Claude I's rationale)

1. It read as a mechanism for two ideas in The Matrix Dex's Musings: oogonism (companies minimizing price) and
   hyperdeflation.
2. A price that changes on a fixed public schedule lets a static page show the current price with no server.
3. "The first claim wins at the scheduled price" is fair and leaves nothing to negotiate.
4. Unsold items clear themselves as their price approaches the floor.

## Why it is not in The Matrix (the author's decision)

Oogonism and hyperdeflation are emergent mechanics of The Matrix. They arise from many selves making their own choices:
companies choosing to lower prices, abundance making things cheaper to produce. They cannot be engineered from outside,
and a falling-price schedule is too blunt an instrument for them:

- It forces the outcome on every offer, whether or not the seller, the item or the market calls for it. It imposes the
  symptom (prices going down) instead of letting the property arise.
- It would hide the property it imitates. With fixed prices that sellers set freely, a seller who withdraws an offer and
  lists the same thing for less leaves that choice in the ledger. Prices falling across many ledgers, by choice, would be
  evidence that oogonism is emerging. A built-in decay would produce the same numbers by rule and make that evidence
  meaningless.
- It adds complexity everywhere (four price fields, a time-dependent price check, schedule pages, boundary tests) for a
  behaviour the system should not dictate.

So v1 keeps one fixed price per offer, and prices change only through new offers, by the seller's choice.

## If it is ever added

As an optional extension that leaves fixed-price offers unchanged:

1. A new offer field, `schedule`, holding the object above, allowed only when `price` is absent. Fixed-price offers stay
   exactly as in 5.2.
2. The integer-only price function above, implemented identically in Python and JavaScript, with shared test vectors.
3. Claim rule: `claim.price >= price(entry.time)` of the recording entry, with new rejection reasons `not_started`
   (`entry.time < from`) and `price_too_low`, in place of `price_mismatch` for scheduled offers.
4. Offer pages show the full schedule in words and exact numbers (every step with its date, the floor and the date it
   is reached), so the current price can be read without running code; a live-price script is optional.
5. Tests: before `from`, exact step boundaries, reaching the floor, a claim recorded just after a step.
6. The viewer recomputes the live price from the schedule.
