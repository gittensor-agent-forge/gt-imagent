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
