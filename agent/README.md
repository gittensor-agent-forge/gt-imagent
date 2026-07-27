# agent

The image agent under competition. This is the only surface a challenger
changes.

```
agent/
├── agent.yaml     manifest the engine reads (entrypoint)
├── agent.py       the implementation
└── tests/
```

## The contract

`imagent-bench` puts the repository root on `sys.path`, reads `agent/agent.yaml`,
and imports the declared entrypoint:

```yaml
entrypoint: agent.agent:ImageAgent
```

The resolved class must expose:

```python
def setup(self, config: dict, workdir: Path) -> None: ...
def generate(self, case: dict) -> dict: ...
```

`generate` returns image bytes and a trace:

```python
{"image_bytes": b"...", "media_type": "image/png", "trace": {...}, "metadata": {...}}
```

**The agent never writes to disk.** The engine owns persistence, naming, timing,
and pass/fail. A candidate cannot choose where its artifacts land or claim its
own score.

`agent/agent.yaml` is a protocol path, hardcoded in the engine's loader — see
[`docs/submission-contract.md`](../docs/submission-contract.md).

## What an agent may rely on

- The Python standard library. Nothing else is installed.
- One image model, fixed for every competitor, reached through OpenRouter.

The model is fixed on purpose: the competition measures agent design, not model
selection.

## What will get a submission rejected

Hardcoding answers for known prompts. The reference agent used to special-case
literals from the benchmark suite and pre-compute arithmetic found in prompts;
that was removed because it measures suite familiarity, not agent quality.

## Try it

```bash
python -m pip install -e ./bench
export OPENROUTER_API_KEY=your-openrouter-api-key
imagent-bench try "Create a polished benchmark badge titled CLI PASS."
```

Writes `results/<UTC datetime>/` with the image and trace. Development only —
not a scored run.

## Tests

```bash
python -m pytest agent/tests
```
