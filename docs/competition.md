# King of the Hill

Design for the Imagent competition. **Proposal — not implemented.** Open
decisions are marked ▸ and need a call before the phase that depends on them.

## What a competition has to guarantee

1. A challenger wins only by being **better**, not by knowing the test.
2. The comparison is **fair**: same problems, same model, same conditions,
   scored at the same moment.
3. A challenger cannot **cheat**: not by calling a stronger model, not by
   hardcoding answers, not by tampering with its own result.
4. Every promotion is **reproducible** from published artifacts.

The current pipeline fails all four.

## Why the current pipeline cannot support it

Five gaps were already recorded in [`submission-contract.md`](./submission-contract.md).
Auditing for this design surfaced two more, and they are the serious ones.

### The fixed-model rule is unenforced

The project's central claim is that generation is pinned to one model, so results
measure the agent rather than model choice. Nothing enforces this.

A candidate agent is arbitrary Python handed `OPENROUTER_API_KEY`. It can call any
model, any provider, as many times as it likes. Worse, the model recorded in the
report comes from the agent's own returned metadata — it is self-declared and
trivially falsifiable. An agent that calls a frontier model and reports
`gemini-3.1-flash-image` would be indistinguishable from an honest one.

So the fairness guarantee is currently honour-system, and the audit trail that
would catch a violation is written by the party with the incentive to lie.

### A secret suite would leak on first publish

The dashboard's `app/reports/[runId]/page.tsx` renders every case prompt, and the
report JSON carries `prompt` per case. The moment a report is published, the suite is
public. Any design with held-out problems has to change the report contract, not
just the suite.

## Design

### 1. Submissions live beside the king, not on top of it

```
kings/
├── current.json          reigning agent: sha, crowned_at, defense record
└── archive/<id>/         every former king, kept forever
submissions/
└── <github-user>-<YYYYMMDD>-<nn>/
    ├── agent.yaml
    └── agent.py
```

`agent/` stays as the reference implementation contributors fork. A challenge PR
adds one directory under `submissions/`; it never edits `agent/` or anything else.
That makes the file-scope rule trivial to enforce and lets several challengers
queue without conflicting.

The engine gains a bundle root: `agent_loader` currently hardcodes
`agent/agent.yaml`, and would take the directory to load instead. The manifest
contract inside a bundle is unchanged.

### 2. A generation proxy, not an API key

This is the load-bearing change. The agent never receives `OPENROUTER_API_KEY`.
It receives:

```
IMAGENT_PROXY_URL     http://127.0.0.1:<port>/v1/images
IMAGENT_PROXY_TOKEN   scoped to one challenge, one case
```

The proxy holds the real credential and enforces:

- **model** — rewritten to the fixed model, whatever the agent asked for;
- **call budget** — N generations per case, hard stop;
- **spend cap** — per case and per challenge;
- **provider** — no other host is reachable.

Everything the fixed-model rule claims becomes true by construction, and the
recorded model comes from the proxy rather than the agent. The trace stops being
self-reported testimony and becomes an observation.

> **Phase 1 is enforcement, not security.** Run in-process, the proxy stops
> accidents and honest mistakes, not a determined attacker who can read the
> parent process's environment. It becomes a real boundary only in Phase 3 when
> the agent runs in a container with no credentials and no egress. Do not
> describe Phase 1 as sandboxed.

### 3. Held-out problems, sampled per challenge

▸ **Decision: where the pool lives.** Recommended: a private repository, fetched
by the workflow with a read-only token. The alternative is generating problems
per challenge with an LLM, which removes the leak risk entirely but makes
difficulty hard to calibrate and adds a new failure mode to debug.

Each challenge samples K cases (default 5) from a pool of ~50. The sample seed is
derived from the challenge id and published *after* the challenge resolves, so
the draw is reproducible but not predictable.

Report contract changes so publishing does not leak the pool:

| Field | Public report |
|---|---|
| `prompt` | replaced by `prompt_sha256` |
| `capability`, scores, dimensions, artifacts | unchanged |

The generated images stay public — they are the evidence. Only the prompts are
withheld, and the hash lets anyone verify after the pool is eventually rotated
out and published.

### 4. Head to head, judged blind

Both the reigning agent and the challenger run **the same K cases in the same
challenge**. Never compare a fresh score against a stored one: with an LLM judge,
the difference between two runs weeks apart is mostly drift.

Per case, the judge sees the prompt and both images and picks the better one.
Position is decided by `sha256(challenge_id + case_id)` so the judge cannot learn
a positional habit, and neither side knows which slot it occupies.

Absolute 0–100 scoring stays, but only as a descriptive statistic for the
leaderboard. **Promotion is decided by the duel, not the score.** Pairwise
comparison is far more stable than absolute scoring for images.

### 5. Promotion rule

```
challenger promoted  ⟺  wins > losses + MARGIN        (MARGIN default 1)
```

Ties count for neither side. Resolution stops early once the outcome is
mathematically settled — no need to judge the remaining cases.

▸ **Decision: single duel or two pools.** tau uses an entry round plus a title
round, which cuts false promotions at double the cost. With K=5 and MARGIN=1 a
single duel is probably enough at this project's scale; revisit if upsets look
noisy.

On promotion: the challenger's bundle is copied to `agent/`, the outgoing king is
archived under `kings/archive/`, `kings/current.json` is rewritten, and the PR is
merged. The defense record travels with the archive so a king's history survives
its reign.

### 6. Screening, before any credits are spent

Cheap checks first, because every challenge costs real money:

| Check | Rejects |
|---|---|
| Bundle shape, manifest parses, entrypoint imports | broken submissions |
| Two sentinel prompts produce **different** images | no-op and constant-output agents |
| Output is not byte-identical to any archived king output | replayed submissions |
| Static scan for network calls outside the proxy | egress attempts |
| One open submission per contributor | queue flooding |

### 7. Lifecycle

```
open PR → screen → queue → duel → promote or close
```

| Label | Meaning |
|---|---|
| `challenger:pending` | screened, waiting for a slot |
| `challenger:running` | duel in progress |
| `challenger:defeated` | lost the duel; PR closed |
| `challenger:invalid` | failed screening or scope rules; PR closed |
| `king` | reigning agent |
| `king:past` | former king, kept in history |

Oldest pending challenger goes first. One duel at a time — the king cannot be
fighting two challengers at once, or two promotions could race.

▸ **Decision: where the orchestrator runs.** Recommended: GitHub Actions, in this
repo, kata-style. It matches the project's scale and keeps everything auditable
in public. An external validator service (tau-style, workers on a database) is
more robust and better suited to continuous operation, but it is a large amount
of infrastructure for a project this size.

## What changes, by component

| Repository | File | Change |
|---|---|---|
| bench | `agent_loader.py` | load from a bundle root instead of hardcoded `agent/` |
| bench | `proxy.py` | **new** — credential holder, model pin, budget enforcement |
| bench | `duel.py` | **new** — pairwise judging, blinding, early stop |
| bench | `scoring.py` | add pairwise judge prompt alongside absolute scoring |
| bench | `suite.py` | fetch and sample from a held-out pool |
| bench | `reporting.py` | redact prompts to `prompt_sha256` |
| ui | `lib/reports.ts` | make `prompt` optional, accept `prompt_sha256` |
| ui | `app/reports/[runId]` | stop rendering raw prompts |
| gt-imagent | `.github/workflows/challenge.yml` | **new** — screen, duel, promote |
| gt-imagent | `agent/` | unchanged; it is the reference and the seed king |

Each engine change lands in `gt-imagent-bench` and is adopted here by bumping
`IMAGENT_BENCH_REF`. That bump is the moment the competition's rules change, and
it should be as visible as a rule change deserves to be.

The bytes-in/bytes-out agent interface from the last refactor is what makes the
proxy and the sandbox possible. No further interface change is needed.

## Phasing

Each phase is independently useful and independently reviewable.

**Phase 1 — make the contest honest.** Proxy with model pin and budget caps;
bundle-root loading; screening. After this, the fixed-model claim is true.

**Phase 2 — make the comparison fair.** Held-out pool with sampling; prompt
redaction; head-to-head duels with blinded pairwise judging; king state and the
promotion rule. After this, results mean something.

**Phase 3 — make it safe.** Container isolation: no credentials, no egress except
the proxy, read-only rootfs, resource and time limits. After this, running
untrusted submissions is defensible.

**Phase 4 — make it run itself.** `challenge.yml`, label automation, promotion
commits, report publishing.

Phase 1 before Phase 2 is deliberate: held-out problems are pointless while a
challenger can still call a better model.

## What this does not solve

- **Judge quality is the ceiling.** Every result is only as good as the judge
  model's taste. Blinding and pairwise comparison reduce variance; they do not
  make the judge correct. Periodic human spot-checks against judge verdicts are
  the only real control, and they should be published.
- **Cost scales with challengers.** Each duel is 2×K generations plus K judge
  calls. A busy queue is a real budget line, and the spend cap is the only thing
  standing between the project and a surprise invoice.
- **A determined attacker beats Phase 1 and 2.** Only Phase 3 changes that.
