# imagent-ui

Product website for Imagent: home page, OpenRouter-backed generation
playground, benchmark leaderboard, whitepaper, and imported `imagent-bench`
reports.

The playground uses OpenRouter with the project-standard image model
`google/gemini-3.1-flash-image` (Gemini 3.1 Flash Image). The UI intentionally
shows only that model so contributors compare agent orchestration against a
fixed underlying image model.

## Gittensor Relationship

Imagent is being built through Gittensor. This website should make that visible
without requiring visitors to know Discord context or subnet shorthand: the
generation playground, benchmark leaderboard, and imported reports all represent
the open image-agent competition that Gittensor helps power.

The public site at `https://tryimagent.com` should clearly explain the
historical benchmark archive and the active, manually reviewed Leaderboard UI
competition.

## Development

```bash
npm install
npm run dev
```

The generation playground also expects:

- `python3` on your PATH, or `IMAGENT_PYTHON_BIN` pointing to a Python binary;
- a sibling `../imagent` checkout, or `IMAGENT_REPOSITORY_PATH` set to an
  `imagent` repository path;
- `IMAGENT_PUBLIC_SITE_URL=https://tryimagent.com` if the deployed public origin
  differs from the default and you want metadata plus OpenRouter attribution to
  match it;
- an OpenRouter API key entered in the browser settings modal, or both
  `OPENROUTER_API_KEY` and `IMAGENT_UI_ENABLE_SERVER_KEY_FALLBACK=true`
  configured on the UI server for trusted private shared use.

Generated playground images are stored under `data/agent-runs` and served back
through the UI as run artifacts. The browser no longer persists base64 image
payloads or API keys in `localStorage`, and the public runtime status endpoint
does not expose local filesystem paths.

Import a benchmark report:

```bash
npm run import-report -- ../imagent-bench/benchmark-output/benchmark-report.json
```

The UI reads benchmark reports from `data/reports`. `imagent-bench` remains
available for local research, but scheduled agent benchmark rounds are currently
paused.

## Deployment

For the public deployment on `https://tryimagent.com`, the repository includes
[`deploy/Caddyfile`](./deploy/Caddyfile). After updating DNS so both
`tryimagent.com` and `www.tryimagent.com` point at the server, validate and
reload Caddy from the server host:

```bash
cd ~/Documents/imagent-ai/imagent/imagent-ui
sudo caddy validate --config "$PWD/deploy/Caddyfile"
sudo caddy reload --config "$PWD/deploy/Caddyfile"
```

To avoid path mistakes and keep the service config in sync, prefer the bundled
deploy helper on the server host:

```bash
cd ~/Documents/imagent-ai/imagent/imagent-ui
npm run deploy:caddy
```

That command copies [`deploy/Caddyfile`](./deploy/Caddyfile) to
`/etc/caddy/Caddyfile`, validates it, reloads the `caddy` service, probes the
backend on `127.0.0.1:3002`, probes public HTTP/HTTPS for `tryimagent.com`, and
prints the recent TLS / ACME log lines.

If HTTPS still fails right after DNS changes, inspect the certificate issuance
logs and trigger a fresh retry:

```bash
sudo journalctl -u caddy -n 200 --no-pager
sudo systemctl reload caddy
```

The most common causes are:

- DNS not pointing both hostnames at the server yet;
- ports `80` and `443` not reachable from the public Internet;
- Caddy not being reloaded after the DNS cutover.
