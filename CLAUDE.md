# Ledgdex: handoff for a new Claude Code session

You are picking up work on **ledgdex**, in the repository `ledgdex/ledgdex` (transferred from `matrixdex/ledgdex`;
old URLs redirect). A previous session built it end to end: the specification, the Python package and command line,
the JavaScript core and browser viewer, 23 rounds of security audits, the docs, and the website. This file is
everything that session knew. Read it fully before changing anything, then read `architecture/SPEC.md`,
`SECURITY.md` and `README.md` in the repo; they are the sources of truth, and this file points into them.

This file is `CLAUDE.md` at the repository root, so every session gets it. Keep it up to date as things change.

---

## 1. What ledgdex is

A simple market on a dex. Every self (a person, a company, a bot) keeps its own **ledger**: `ledgdex.jsonl`, a file
that only grows, in its own **dex** (a website made by [dexweb](https://github.com/matrixdex/dexweb) from
`data.json`, `config.json`, `styles.css`). Every line is signed by the ledger's owner. When two selves trade, the
buyer signs a claim, the seller records it in the seller's ledger (that signed entry is the buyer's receipt), and the
buyer keeps the receipt in the buyer's own ledger: every trade exists three times (triple-entry accounting). No
blockchain, no server, no consensus, no shared ledger.

The phrase the author wants emphasised everywhere: **dex is the core; dex + ledger is a ledgdex.** A ledgdex is an
ordinary dex with one more file, and ledgdex renders the ledger's state as ordinary dex pages, next to the author's own
pages (ledgdex only rewrites pages whose body starts with `<!-- ledgdex -->`).

It belongs to The Matrix, whose founder is **Noorul Ali** (the user; GitHub `alinoorul`; security contact
manonthemoon13131@gmail.com). The root (admission) ledger is the founder's.

Principles (SPEC "Principles"): sovereign (only SHA-256, Ed25519 and plain files; dependencies vendored; works
offline), agent-centric, append-only, explicit trust, "what you write about yourself is a claim; what others hold
about you is evidence", humans and bots equal, every ledgdex is a dex.

## 2. Where things live

| What | Where |
|---|---|
| Code, spec, docs source, viewer source | `ledgdex/ledgdex` (this repo) |
| Website: home, Live Markets, About | https://ledgdex.github.io, repo `ledgdex/ledgdex.github.io` (root), source `home/` |
| Viewer and JavaScript modules | https://ledgdex.github.io/viewer/index.html (same repo, `viewer/`), source `viewer/` |
| Docs | https://ledgdex.github.io/docs/ (same repo, `docs/`) |
| Live test market | `matrixdex/ledgdex-live`, served at `matrixdex.github.io/ledgdex-live/seller` and `/buyer` |
| Unused | `ledgdex/ledgdex-live-demo` (README only). The user decided the live demo stays in the matrixdex org (`matrixdex/ledgdex-live`); never turn on Pages here (it would share the viewer's origin) |
| dexweb (the dex builder, separate project) | `matrixdex/dexweb`, docs at matrixdex.github.io/dexweb; ledgdex uses dexweb 4.2.5 |

The viewer moved off `matrixdex.github.io/ledgdex` because the viewer keeps sealed keys in browser storage and every
page on one origin can read it; `matrixdex.github.io` is shared by all matrixdex sites. **Only `ledgdex.github.io` may
have GitHub Pages in the `ledgdex` org**: any other repo with Pages would publish to `ledgdex.github.io/<repo>`, the
same origin. Keep Pages OFF on `ledgdex/ledgdex`.

### State at handoff (October 2026)

- Version **1.0.17** in code (`py/ledgdex/__init__.py`, `py/pyproject.toml`, `SECURITY.md` line 3, the install
  commands in `guide/dex/data.json`). The tag `v1.0.17` exists (at `8fcad48`); the user creates tags (sessions cannot
  push tags; pushes of tags return 403). Pages is off on `ledgdex/ledgdex` (confirmed by the user).
- Last commits: `535e8c1` (move to ledgdex.github.io and ledgdex/ledgdex, 1.0.17), `4f786ad` (old-site notices;
  CI passed), `8fcad48` (the user deleted `docs/`, the old matrixdex.github.io/ledgdex site), then this file.
- The site at ledgdex.github.io is published and was verified (viewer loads and verifies the docs ledger; all pages
  200; no browser errors), commits `fe16658`, `b600542`, `5af6959` in `ledgdex.github.io`.

### Open items, in order

1. Done: `docs/` (the old `matrixdex.github.io/ledgdex` site) is deleted (`8fcad48`); it must never be served from
   this repo again. Done: SECURITY.md "The viewer's origin" no longer mentions the old viewer.
2. Done: `ledgdex-live`'s check workflow installs `git+https://github.com/ledgdex/ledgdex@v1.0.17` (`1b33ec4` in
   `matrixdex/ledgdex-live`). On each release, update that line the same way, push, and confirm its run passes (it runs
   on push, daily at 06:17 UTC, and by hand). Commit message style there: "ledgdex check workflow: install ledgdex
   vX.Y.Z". Run locally, its check reports 3 warnings and 0 errors: two older seller snapshots that the buyer's
   receipts point to are only behind, and the sandbox can't reach matrixdex.github.io.
3. Done: the **"JavaScript Core" docs page** and three tested examples (`88f8b6b`, the user's patch):
   `13-js-verify.mjs` (Node: verify a published ledger, list open offers, one changed letter breaks it),
   `14-js-web-page.html` (a shop's offers on a web page, checked in the reader's browser, text via `textContent`),
   `15-js-sign.mjs` (sealed browser key, Web Crypto signer, a `sent` claim recorded by the CLI). The page says Node 20
   or later (tests use Node 22); other runtimes untested. JS examples run offline in tests: `py/tests/offline.mjs`
   (loaded with `node --import`) serves `https://ledgdex.github.io/` from this repo (`docs/` from `guide/dex/`, the
   rest from `js/`); `py/tests/page.mjs` runs a web page's module script in node with a stand-in DOM. In `.html`
   examples, `<!-- ... -->` lines (and `// ` lines in the script) become paragraphs. Published on the docs site
   (`b9cea5e` in `ledgdex.github.io`).
4. Done: the 25 hand-written docs pages follow ASD-STE100 (`712c3cb`, the user's patch). `ste-lint.py` finds 0
   problems in them. The generated pages and the ledger pages did not change. The user published the docs
   (`990b50d` in `ledgdex.github.io`). New text in hand-written pages must also pass `ste-lint.py`.

## 3. Repository layout

```
architecture/SPEC.md   the specification (format, state rules, invariants, CLI, release notes, decisions)
SECURITY.md            what the guarantees mean for users; version line; reporting
README.md              overview, install, running a root, viewer, checking, tests
py/ledgdex/            the Python package (pip install -e "py[fast]")
  canon.py             canonical JSON (parse/canon/hash_), limits
  core.py              keys, messages, entries, Ledger (verification, cache), BODIES (message schemas)
  ed25519.py           vendored pure-Python Ed25519 (strict; refuses small-order keys)
  sig.py               backends: "cryptography" (constant time, the `fast` extra) or pure; LEDGDEX_PURE=1 forces pure
  state.py             the state function: replay a ledger into offers, claims, auctions, disputes, admissions...
  dex.py               a ledgdex on disk: keys (~/.ledgdex, mode 600), load/write, root pinning, locks
  render.py            ledger state -> dex pages in data.json (MARKER '<!-- ledgdex -->'), dex name sanitising
  publish.py           catch up with the published ledger, re-sequence, publish with dexweb (append_only)
  check.py             tamper checks over time (kept copies + receipts), the GitHub workflow generator
  cli.py               the `ledgdex` command (argparse; `parser()`); `next_at` keeps one key's messages in distinct seconds
py/tests/              unittest suites (see section 6), helpers.py, make_vectors.py, fuzz.py
js/                    the same core in plain ES modules (no npm, no dependencies): canon, sha, ed25519, core,
                       state, render, sig (Web Crypto signer + vendored fallback), keystore (sealed keys), dexweb.js
                       (dexweb's build in JS), zip.js, viewer.js; test.mjs (vectors), fuzz.mjs (fuzz partner)
vectors/               shared test vectors, byte-exact for both languages: canon, ed25519, signatures, ledgers/,
                       pages, dexnames, dex/ (whole dexes dexweb built). Regenerate: python py/tests/make_vectors.py
home/                  the home dex (home page, Live Markets, About; no scripts) -> ledgdex.github.io root
viewer/                the viewer dex (data.json, config.json, styles.css, run.py) -> ledgdex.github.io/viewer/
guide/                 the docs: dex/ (the docs dex, a ledgdex), examples/ (15 tested examples), pages.py
                       (generated pages), build.py (optional refresher), make_demo_ledger.py
.github/workflows/tests.yml   CI
.claude/skills/asd-ste100/    project skill (user-added): ASD-STE100 Simplified Technical English rewrites, with a
                              stdlib-only linter (scripts/ste-lint.py). From github.com/danyuchn/asd-ste100-skill at
                              32511c6 (v0.4.0, MIT). To update, copy a newer release over it and rerun --selftest.
```

## 4. The design, in short (details in SPEC)

- **Encoding (SPEC 1):** canonical JSON: sorted keys, no spaces, integers only (|n| < 2^53), UTF-8, one spelling per
  value, nesting at most 32 levels. Ids are `sha256:` + 64 hex (of canonical bytes / the line). Keys `ed25519:` + 64
  hex. Times `YYYY-MM-DDTHH:MM:SSZ`, ASCII only. Ed25519 verification is strict and refuses the 8 small-order keys.
- **Messages (SPEC 2):** `{"v": 1, "type", "by", "at", "body", "sig"}` signed by `by`. 26 types (`BODIES` in core.py and
  core.js), validated strictly: unknown type, unexpected field or `v != 1` is `Invalid` (so any new type or field is a
  format change; see section 9).
  - O-authored (owner/devices): open, admit, revoke, note, sent, receipt, rotate, device, device_revoke, auction,
    list, delist, recover, recovered, offer, withdraw, received, delivered.
  - Counterparty: claim, paid, confirmed, dispute, ruling, bid, reveal.
  - Owner-key only (authored AND recorded by the owner key): open, rotate, device, device_revoke, recover.
- **Ledger (SPEC 3):** a header line `{"ledger":1,"name","owner"}` (ledger id = its hash), then entries
  `{"seq","prev","time","msg","sig"}` hash-chained and signed by a current signing key (owner or active device).
  Times non-decreasing; a message may be at most 300 s ahead of its entry (clock skew, SPEC 9.2). One writer at a
  time; several devices re-sequence on publish (3.5).
- **State (SPEC 6):** a deterministic replay. Rules are fixed (a claim is accepted if quantity left, price matches,
  buyer allowed, not the seller). Ignored messages are listed with a reason (`not_allowed`, `self_claim`,
  `duplicate_message`, `not_arbiter`, `claim_not_accepted`, ...). A claim closes when `received` + `delivered` +
  `confirmed`. Root admissions are judged at the later of the message's `at` and the entry time minus 300 s.
- **Every ledgdex is a dex (SPEC 7):** render writes the state as pages into data.json; publish catches up, re-sequences
  unpublished entries on top of the published ledger, then dexweb publishes with `append_only: ["ledgdex.jsonl"]` (the
  published ledger must be the exact start of the new one).
- **Root, index, admission, recovery (5.7):** the root admits keys; offers can be `"allow": "admitted"`; a dex pins
  its root by ledger id (`root_id`, trust on first use). The root's owner can `recover` a ledger to a new key (used
  once). Indexes `list` ledgers; `discover` reads them.
- **Disputes, auctions (5.5, 5.6):** the offer names an arbiter (default: the root's owner); sealed-bid auctions with
  commit/reveal, reserve, `best: highest|lowest`.
- **Checks over time (9.1):** `ledgdex check` keeps copies and follows receipts; a rewrite shows up as two signed
  entries at one position (`receipt_mismatch`, `equivocation`) with proof saved. `ledgdex workflow` prints a pinned
  GitHub Actions workflow that runs it daily.
- **Payments happen outside.** `offer.pay` is `[{"method","to"}]` (informational), `paid` is the buyer's notice
  `{claim, method, ref}`, `received` is the seller's statement of money in. There is no payment-request message.

## 5. Decisions you must keep (SPEC "Decisions", SECURITY.md, and the user's)

- USD amounts are integer cents; all prices are integers in minor units.
- Default arbiter: the root's owner. Clock skew stays 300 s. Admission is not delegated (a `delegate` type is future).
- **"Keep error"** (Decision 6, chosen by the user): a conflicting entry signed by a since-revoked device is still an
  error (`receipt_mismatch`/`equivocation`), never downgraded to a warning. Audit 21 surfaced the inherent limit
  behind it: a device key stolen and used after revocation can sign for the period it was active; without a trusted
  clock that is indistinguishable, so it is documented, not "fixed".
- Strict schemas are a security feature: never loosen validation to "accept unknown stuff" casually.
- Never change the meaning of an existing message type or an existing state rule: verifiers on different versions
  would disagree about the same ledger. New behaviour = new types (a format change), released deliberately.
- Python and JavaScript must agree byte for byte (vectors + differential fuzzing). Any change to core, canon, state
  or render is made in BOTH languages, with new vectors.
- Keys never leave the machine: `~/.ledgdex/*.key` mode 600 (refused otherwise), never in a dex, never committed.
  Browser keys only sealed (PBKDF2-SHA-256 600k rounds -> AES-256-GCM). The docs ledger was signed by a throwaway key
  that was never saved (`guide/make_demo_ledger.py`); if it must be remade, delete `guide/dex/ledgdex.jsonl` and rerun.
- The docs pages run **no scripts** (CSP `script-src 'none'`, no external loads), because they share an origin with
  the viewer. The viewer's CSP allows scripts only from itself; it refuses to run in a frame.
- `ledgdex.github.io` is the only Pages site in the `ledgdex` org.

## 6. Tests: what to run, every time

Setup: `pip install -e "py[fast]"` (Python 3.8+; `cryptography` for the fast backend; dexweb and git needed), node 22.

```
cd py && python -m unittest discover -s tests -v                       # cryptography backend (140 tests)
cd py && LEDGDEX_PURE=1 LEDGDEX_NO_CACHE=1 python -m unittest discover -s tests   # pure Ed25519, no cache (2 skips)
node js/test.mjs                                                       # JS against the shared vectors (289 checks)
cd py && python tests/fuzz.py --seed N --ledgers 200 --texts 3000 --keep fuzz-out  # differential fuzzing
python py/tests/make_vectors.py                                        # regenerate vectors (only for deliberate changes)
python guide/build.py --check --gen                                    # docs: generated pages current, site builds
cd viewer && python run.py --build-only                                # viewer builds
```

- **Differential fuzzing** (`py/tests/fuzz.py` + `js/fuzz.mjs`): builds random ledgers with every message type,
  corrupts them (bytes, lines, fields re-signed so the change reaches deeper rules), and makes tricky JSON texts;
  Python and node each report parse / whole / where it breaks / why / canon(state) / pages; any difference fails.
  CI runs a new seed every run (`--seed ${{ github.run_number }}`); for audits run many seeds and larger counts.
- `test_guide.py` runs all 15 docs examples in empty temp folders with their own `LEDGDEX_HOME`, asserts every
  `# expect:` / `// expect:` line is printed, checks every command and option is documented, every docs link and
  anchor resolves (in `guide/dex/gen/`), no page has `<script`, `<b>` or `<strong>`, generated pages are current and
  marked, and the install commands name `v` + `__version__`.
- `test_safety.py`: invariant 14 (pages carry only text, `<code>`, `<br>`, safe http(s) links) on every vector page.
- CI (`.github/workflows/tests.yml`), in order: install; docs build check (`build.py --check --gen`, then
  `git diff --exit-code guide`); viewer build; both Python suites; JS vectors; fuzzing (uploads disagreements on
  failure). Actions are pinned to commits.

Before every push: run the relevant suites locally on BOTH backends, re-read your diff adversarially, then push; check
CI after.

## 7. The security audits (how "production ready" was reached)

The user's standing instruction was: *keep doing complete security audits until 3 audits pass consecutively with 0
bugs; keys must not leak anywhere; ledgers cannot be tampered with, or tampering is easily evident; fix every bug and
loophole each audit finds.* 23 audits were run:

- Audits 1-20 found and fixed real bugs; audits 4-20 alone fixed 22 (three were bugs introduced by earlier fixes).
  Each fix is a release note in SPEC "Build status" (v1.0.0 ... v1.0.15) with a vector or test. Highlights:
  small-order Ed25519 keys accepted (1.0.1, forgery); forged receipts through `recovered` (1.0.2); verification cache
  poisoned by a hostile root (1.0.3); Unicode digits in times/ids (1.0.4); quadratic work (1.0.5); devices copying
  owner-only messages (1.0.6); root swapped at its address -> pinning (1.0.7); dex name injected unescaped into pages
  (1.0.8); availability of `record --from` and of the root (1.0.9, 1.0.10); `"allow": "admitted"` judged at the wrong
  time (1.0.11); clickjacking -> frame refusal (1.0.12); duplicate offer/auction messages (1.0.13); cross-ledger time
  (1.0.14); backdating around root revokes, replayed device messages in receipts, deleted owner-signed entries in
  check (1.0.15).
- **Audits 21, 22, 23 passed consecutively with 0 bugs**, which ended the loop:
  - 21: attacked the 1.0.15 changes and their interactions; no bugs; documented the stolen-after-revocation device
    limit (-> the "keep error" decision).
  - 22: full regression at scale on the final code: both Python backends; the 289 JS checks; 2,100 fuzzed ledgers
    with no Python/JS differences; 540 line edits and 202,344 single-bit flips across three ledgers, every one
    breaking verification; the browser checks; the framing refusal; a live `ledgdex check` with 0 errors.
  - 23: re-proved every guarantee in SECURITY.md with fresh attacks; all held.
- Areas each audit covered (use them for future audits): browser code and every external input; each spec invariant
  backed by an attack test; supply chain, deployment and keys at rest; fresh end-to-end red team; availability and
  agent robustness; differential and adversarial testing at scale; a full re-read of core/state/check against the
  spec; the viewer as an attacker would use it; cross-ledger time and ordering; consumers of state (render, viewer,
  CLI) against every state the state function can produce; adversarial passes over the fixes themselves; every
  SECURITY.md guarantee re-proven.
- If you change core, state, check, render, the viewer or keys, run at least a regression round like audit 22 and
  say so. A security bug fix = new patch version, a SPEC release note, a test or vector that fails before the fix.

## 8. Docs, viewer and site: how they are made and published

### Docs (`guide/`)
- `guide/dex/` is a dex AND a ledgdex (its `ledgdex.jsonl` is the frozen demo ledger, id `sha256:8a657c68...`, dex
  address `https://ledgdex.github.io/docs`). **`data.json` is the source**: the user edits it by hand like any dex.
- 19 pages are generated from code and examples by `guide/pages.py` (Command Line Options from argparse with
  COLUMNS=110, API Reference from `inspect` and the JS exports, Message Types validated with `check_body`, Examples
  and the 15 example pages). Each generated page's first body string starts with
  `<!-- generated by build.py. use build.py to generate page if there are changes -->` (the user asked for exactly
  that comment). `python guide/build.py` replaces only those pages (by title), `--check` fails if stale, `--gen` also
  builds `guide/dex/gen/`. build.py writes data.json the way ledgdex does (indent 4, ensure_ascii False, no trailing
  newline) and atomically (tmp + replace).
- Publish: `cd guide/dex && ledgdex publish .` -> dexweb git method to `ledgdex/ledgdex.github.io`, `site_path: docs`.
- Example files (`guide/examples/NN-name.sh|py|mjs|html`): at the top only the shebang/`set -eu` and `expect:` lines; each
  column-0 comment line (`# ` or `// `) becomes the paragraph shown above the code that follows it, and the code shown
  on the page has no comments (the user wants minimal comments in code; explanation in paragraphs). Backticks in those
  comments become inline code. Keep examples clear, concise and in simple language about what they achieve.
- Style the user asked for: no `<b>`/bold anywhere; code blocks (`<pre>`) dark with a green left rule, 15px, light
  text; inline code `rgb(203,203,203)`, 18px inside paragraphs, inheriting size elsewhere (`monospace, monospace`);
  the docs index is NOT sorted by us (dexweb 4.2.5 sorts it by title; the user said "do not sort index for now").
  Docs style mirrors the dexweb docs (config/templates "LEDGDEX DOCS", "BACK TO LEDGDEX DOCS").
- Hand-written pages carry the version in install commands (`@v1.0.17#subdirectory=py`); a test enforces it.

### Home (`home/`) and viewer (`viewer/`)
- The home dex has the pages Live Markets and About. Its index lists Viewer and Docs too. It runs no scripts (its CSP
  has `script-src 'none'`). `cd home && python run.py` builds it and publishes it to the root of
  `ledgdex/ledgdex.github.io`.
- The viewer dex has only the Viewer page. `cd viewer && python run.py` builds it (dexgen, then a copy of `js/*.js`,
  `dexweb-template.json` and `.nojekyll` into gen/), copies `viewer.html` to `index.html`, and publishes it to
  `viewer/` (`site_path: viewer`). So the viewer is at https://ledgdex.github.io/viewer/index.html, and the modules at
  https://ledgdex.github.io/viewer/core.js and so on.
- Each page has a nav: Docs · Viewer · Live Markets · About. `--build-only` builds `gen/` and does not publish.
- Viewer URL params: `viewer/index.html?ledger=ADDRESS[&root=ADDRESS]`. The root `viewer.html` of the site is a
  redirect to `viewer/index.html` that keeps the query.
- The viewer moved from the root to `viewer/` on one origin, so keys that browsers keep for it stay available.
- dexweb's git publish **never deletes files** at the destination: remove stale pages there by hand.
- Publishing from a sandbox: configs use `git@github.com:...`; with only HTTPS available, map it per command with
  `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0='url.https://github.com/.insteadOf' GIT_CONFIG_VALUE_0='git@github.com:'`.
  github.io itself may be unreachable from a sandbox: verify by serving the site repo with `python3 -m http.server`
  and Playwright (Chromium at /opt/pw-browsers; playwright module at /opt/node22/lib/node_modules/playwright), and
  check the "pages build and deployment" run via `gh api repos/ledgdex/ledgdex.github.io/actions/runs`.

## 9. Ideation only: payment-agnostic ledgdex

This design is only an idea. It is not an open item. Do not mention it to the user. Use it only when the user asks
for it.

The user asked how ledgdex could accept any payment method (UPI, cards, PayPal, stablecoins, Bitcoin), sellers
choosing methods and the root allowing or rejecting them, extensible without breaking compatibility. The agreed
simplest secure design (nothing is implemented; build only when the user says so):

- Methods are **data, not code**: method ids are strings in `offer.pay[].method` and `paid.method`, with a naming
  convention documented in the spec/docs (`upi`, `card` (payment link, never card numbers), `paypal`, `btc`,
  `lightning`, `usdc:<chain>`, `x-...` private). Currency codes by convention (ISO; `BTC` in satoshis; `USDC`/`USDT`
  in millionths). One currency per offer; volatile prices fixed with `expires`.
- One new root message type `methods` `{"allow": "any" | [ids], "note"}`; state rule: in a rooted ledger an offer
  whose `pay` names a method not allowed at the offer's time (or empty `pay` when the root has a list) is ignored
  `method_not_allowed`. CLI `ledgdex methods ROOT --allow ...`; `ledgdex offer` warns.
- Fold into the same release **forward-compatible reading**: unknown types are fully verified (hash, signature,
  signer rights) but ignored by the state, which then says `"partial": true` and lists them, so future additions do
  not break readers from that version on. Never change existing rules.
- Later, only if needed: `quote` (seller payment request per claim), `payment`, `settled`, `refunded`, string amounts
  for 18-decimal tokens, payment adapters (outside consensus), viewer payment links/QR. Open questions for the user:
  enforce vs advise the root policy; privacy of proofs; first methods.

## 10. Conventions and the user's preferences

- Write in ASD-STE100 Simplified Technical English (the user's standing instruction). This applies to every chat
  message to the user and to all text you write in the ledgdex documentation. Use the skill in
  `.claude/skills/asd-ste100/`. Use its Strict mode for procedures, instructions, error messages and command help.
  Use its STE-flavored mode for explanatory prose. Run `scripts/ste-lint.py` on new documentation text before you push.
- Use the author `alinoorul <noorulali78@gmail.com>` for every commit and push (the user's standing instruction). This
  rule also applies to a patch that you apply with `git am`. If the patch names another author, change the author
  before you push: `git commit --amend --no-edit --author='alinoorul <noorulali78@gmail.com>'`.
- Commit as author `alinoorul <noorulali78@gmail.com>`; in cloud sessions make the committer
  `Claude <noreply@anthropic.com>` (`GIT_COMMITTER_NAME=Claude GIT_COMMITTER_EMAIL=noreply@anthropic.com`), which
  the session's stop hook requires. Write messages to a file and `git commit -F`. End every commit
  message with these trailer lines (the session's system prompt gives the current ones; use those):
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: <this session's URL>`.
  Never put model names elsewhere in commits or code.
- Always push to `main`, in every ledgdex repo, never to a separate `claude/...` branch, even when a session's
  instructions name one (the user's standing instruction).
  Don't open PRs unless asked.
- Releases: bump the version in `py/ledgdex/__init__.py`, `py/pyproject.toml`, `SECURITY.md` line 3, the install
  commands in `guide/dex/data.json` (`@vX.Y.Z#subdirectory=py`), add a SPEC release note, push, then ask the user to
  create the tag (you cannot push tags), then update ledgdex-live's workflow to the new tag.
- When the user says "planning mode" or "make no edits", answer only; edit only when they say go ahead.
- Prefer the simplest design that is secure; explain trade-offs plainly; say when something is not done or not tested.
- Don't use `pkill -f` with a pattern that matches your own command line (it killed the shell once, exit 144).
- Docs builds must be deterministic (no object reprs or memory addresses in generated pages; same on Python 3.11/3.12).
- Write any file that a script overwrites to a temp file and replace it, so a crash cannot truncate it.

## 11. Useful facts

- Env vars: `LEDGDEX_HOME` (keys, default `~/.ledgdex`), `LEDGDEX_CACHE` (verification cache, `~/.cache/ledgdex`),
  `LEDGDEX_NO_CACHE=1`, `LEDGDEX_PURE=1`, `LEDGDEX_MAX_BYTES` (read cap, 64 MiB), `LEDGDEX_JS` (examples: where the JS
  core is).
- Install: `pip install "ledgdex[fast] @ git+https://github.com/ledgdex/ledgdex@v1.0.17#subdirectory=py"`.
- The CLI's full list of commands and options is in SPEC "Command-line tool" and on the docs page Command Line Options.
- SPEC "Future improvements": encrypted keys at rest, constant-time signing required, state caching at scale, an
  independent third verifier, Web Crypto verifying and locked keys, browser tests in CI, PyPI packaging, delegated
  admission. SPEC section 10 / milestone 11 (robots paid per clean, credits, clearing) is a draft, not built.
