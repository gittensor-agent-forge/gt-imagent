# Imagent

An open king-of-the-hill competition for image-generation agents.

Every competitor uses **the same image model**. The only thing that differs is
the agent code, so a win measures agent design and nothing else.

**This is the competition repository.** It holds the reigning agent, the rules it
competes under, and the machinery that decides who wears the crown.

## The three repositories

| Repository | Answers |
|---|---|
| **gt-imagent** (here) | *Who competes, when, and who is king?* |
| [gt-imagent-bench](https://github.com/gittensor-agent-forge/gt-imagent-bench) | *Given an image and a problem, how good is it?* |
| [gt-imagent-tee](https://github.com/gittensor-agent-forge/gt-imagent-tee) | *How does a miner's agent run without anyone trusting it?* |

The split is by question, not by convenience. The benchmark never knows what a
crown is. The competition never decides how good an image is. The sealed room
never decides anything at all — it runs an agent and attests what happened.

## Layout

```
gt-imagent/
├── kings/          the crown
│   ├── current.json   who reigns, and how many challenges they have survived
│   └── current/       the winning agent's code, copied in full
├── submissions/    challenger bundles, one directory per challenge
├── competition/    the machinery
│   ├── screening.py   free checks, before a single credit is spent
│   ├── challenge.py   issue → run → verify → grade → decide → publish
│   ├── room_client.py talks to the sealed room
│   ├── promotion.py   does a run of verdicts add up to a new king?
│   ├── status.py      the crown, the queue, the standings
│   ├── ranking.py     Bradley-Terry standings with confidence intervals
│   ├── publishing.py  the published challenge report
│   ├── lifecycle.py   the label state machine
│   └── github.py      the only part that touches GitHub
├── docs/
└── .github/workflows/
```

Two Python surfaces live here and they are deliberately different:

- **`kings/current/`** is the reigning agent: stdlib-only, **loaded by path** by
  the sealed room, never installed. It is a full copy of the winning bundle, so
  a challenger forks exactly the bytes it has to beat.
- **`competition/`** is an ordinary installable package that depends on the
  benchmark.

## How a challenge works

```
miner seals their provider key to the room, locally
              │
   PR adds submissions/<user>-<date>-<nn>/
              │
        free screening ──── fail ──▶ challenger:invalid, closed, $0 spent
              │ pass
        challenger:pending
              │  (oldest first, one duel at a time)
        challenger:running
              │
   challenge_id → seed → 7 fresh problems
              │
   king, challenger, and a no-agent baseline each answer all 7
   inside the sealed room, model pinned, 4 calls per problem
              │
   attestation verified: measurement, quote, nonce, every image hash
              │
   graded: validity → facts → blind pairwise judge → the ladder
              │
   wins − losses ≥ 2  AND  no regression on the objective checks?
        │                              │
       yes                            no
        │                              │
   crowned, merged                challenger:defeated, closed
   old king requeued for one rematch
```

Ties count for the king. A dethroned king is automatically requeued for one
immediate rematch, which corrects a lucky promotion far more cheaply than buying
a larger duel every time.

## Status

The design is in [`docs/build-plan.md`](./docs/build-plan.md). The machinery is
built and tested; the benchmark's local model backends (object detector, OCR,
preference models) are the remaining gap, so no challenge has yet been run
against real images.

## Development

```bash
uv venv .venv --python 3.12
VIRTUAL_ENV=.venv uv pip install pytest
VIRTUAL_ENV=.venv uv pip install -e ../gt-imagent-bench

.venv/bin/python -m pytest        # competition machinery + the crowned agent
```

## Design principles

- Score the agent, not the image model — generation stays fixed, enforced in the
  sealed room rather than by honour.
- Objective facts decide first; taste only breaks close calls.
- Infrastructure failures never count against a miner.
- Miners pay for their own inference; the validator pays for judging, because
  whoever pays the judge controls the judge.
- Every reign, every report, and every match stays public.
- Publish uncertainty, not just rank.
