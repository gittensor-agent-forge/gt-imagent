# web

Product website for Imagent: home page, benchmark leaderboard, whitepaper, and
imported `imagent-bench` reports.

Generation is fixed to the project-standard image model
`google/gemini-3.1-flash-image` (Gemini 3.1 Flash Image), so published results
compare agent orchestration against one shared underlying image model.

## Gittensor Relationship

Imagent is being built through Gittensor. This website should make that visible
without requiring visitors to know Discord context or subnet shorthand: the
leaderboard and imported reports represent the open image-agent competition that
Gittensor helps power.

The public site at `https://tryimagent.com` should clearly explain the benchmark
archive and, once the rebuild lands, the standing of the reigning agent.

## Development

```bash
npm install
npm run dev
npm run lint
npm run build
```

Optional environment:

- `IMAGENT_PUBLIC_SITE_URL=https://tryimagent.com` if the deployed public origin
  differs from the default and you want page metadata to match it.

Import a benchmark report:

```bash
npm run import-report -- ../bench/benchmark-output/benchmark-report.json
```

The UI reads benchmark reports from `data/reports`. `/leaderboard` is rendered
dynamically so an imported report appears without a rebuild.

## Deployment

For the public deployment on `https://tryimagent.com`, the repository includes
[`deploy/Caddyfile`](./deploy/Caddyfile). After updating DNS so both
`tryimagent.com` and `www.tryimagent.com` point at the server, validate and
reload Caddy from the server host:

```bash
sudo caddy validate --config "$PWD/deploy/Caddyfile"
sudo caddy reload --config "$PWD/deploy/Caddyfile"
```

To avoid path mistakes and keep the service config in sync, prefer the bundled
deploy helper on the server host:

```bash
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
