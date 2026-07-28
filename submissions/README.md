# submissions

One directory per challenge. Nothing else in the repository may change in a
challenge pull request — that rule is what makes the scope check automatic
instead of something a reviewer has to remember.

```
submissions/<github-user>-<YYYYMMDD>-<nn>/
├── agent.yaml             the manifest (entrypoint: module:attribute)
├── agent.py               your agent
└── sealed_inference_key   ciphertext — your provider key, sealed to the room
```

## Before you open the pull request

Seal your provider key with the tool in
[gt-imagent-tee](https://github.com/gittensor-agent-forge/gt-imagent-tee):

```bash
export IMAGENT_PROVIDER_KEY=sk-or-v1-...
python imagent_seal.py \
    --room     https://<the room URL from kings/current.json> \
    --bundle   submissions/<your-directory> \
    --measurement sha256:<the allowlisted room image> \
    --provider openrouter
```

That writes `sealed_inference_key`. **It is ciphertext — commit it.** Your key
decrypts only inside the sealed room, only for your job. Maintainers, validators,
and anyone reading your pull request see the ciphertext and nothing else.

The credential is bound to a hash of every file in your bundle. If you change any
file afterwards, re-run the tool: the binding will no longer match and the room
will refuse the run. That binding is also what stops anyone lifting your
ciphertext out of the pull request, running it with a different agent, and
reading your key back out.

## Rules

- **One open submission per contributor.** A second one is closed automatically.
- **You pay for your own generations.** If the key runs out of credit mid-run,
  the attested inference summary says so and the challenge is forfeited.
- **The model is fixed.** The room rewrites whatever model you ask for to the
  pinned one and records the attempt. Asking for another model disqualifies the
  run — not because it scored badly, but because it was never comparable.
- **4 generations per problem.** Enforced outside your container.
- **Your agent runs isolated:** no API key, no network except the room's
  inference gateway, dropped capabilities, read-only root, and a wall clock.

## What your agent gets

`generate(case)` receives an `inference_api` URL per problem. Post to it instead
of calling a provider directly — the token in that URL carries the problem's
generation budget.

```python
case = {
    "id": "geneval-count-00-d75d8920",
    "run_id": "geneval-count-00-d75d8920",
    "prompt": "a photo of three cakes",
    "inference_api": "http://.../p/<token>/inference",
}
```

Return `{"image_bytes": b"...", "media_type": "image/png"}`. The room names,
hashes, and writes the artifact. You do not choose where it lands, how long it
took, or whether it passed.

## What gets a submission rejected before it costs anything

| Check | Rejects |
|---|---|
| Manifest parses, entrypoint imports | broken submissions |
| Only your submission folder changed | edits to the engine or the king |
| Bundle within the size and file-count limits | tar bombs |
| Sealed credential present and well-formed | missing payment |
| Two sentinel prompts produce two different images | no-op and constant-output agents |
| Output not a perceptual match to an archived king | replayed answers |
