# kings

The reigning agent, in full.

```
kings/
├── current.json    who reigns: agent id, source submission, commit, defences
└── current/        the winning agent's code, copied verbatim from its submission
    ├── agent.yaml
    └── agent.py
```

`current/` is a complete, runnable copy of the winning bundle — not a pointer to
it. A challenger forks this directory, and the room runs exactly these bytes when
the king defends.

There is no archive directory. Every past king is already preserved twice: its
pull request stays in `submissions/`, and git history holds every state this
directory has ever been in. A third copy would be a third thing to keep in sync.

`current.json` carries the defence record — how many challenges this agent has
survived. That is the number a reign is actually measured in, and it is the one
thing not recoverable from the code alone.

## The project's sealed credential

`kings/current/` and `kings/baseline/` each carry a `sealed_inference_key` — the
project's own provider key, sealed to the room exactly as a miner seals theirs.
The project funds the king's defences and the control; a miner pays only for
their own attempt.

A credential is bound to a hash of every file in its bundle, so these cannot be
shared between the two directories, and **crowning a new king invalidates the
king's**. The Challenge workflow re-seals against the new bundle immediately
after installing it. If that step is skipped, the next defence aborts before it
starts — loudly, and before any challenger's credit is spent.
