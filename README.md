# ~/.hermes — Hermes Agent configuration

Version-controlled configuration for a **Hermes Agent** (Nous Research) deployment
running in Docker on a headless Ubuntu box, with two interchangeable LLM backends:
the online DeepSeek API, and a local Strata server on a Tesla V100.

This repository deliberately tracks **only** hand-authored configuration. Everything
else in `~/.hermes` is runtime state, secrets, or an installed bundle — see
*What is not tracked* below.

---

## Backends

| Alias | Provider | Endpoint | Notes |
|---|---|---|---|
| `ds` (default) | `deepseek` | DeepSeek cloud API | fast (~1.7 s), billed per token |
| `strata` | `custom` | `http://127.0.0.1:8080/v1` | local Qwen3.8-Flash-Next, 128K ctx, free |

`model.default` is `deepseek/deepseek-flash`. Switch with the in-session command or
the CLI flag — both resolve the alias:

```bash
hermes chat --model strata          # alias form
hermes chat --provider strata --model qwen3.8-flash-next
```

Backends are declared in two places in `config.yaml`:

- `providers.strata` — a *named custom provider*. Address it as
  `custom:strata:<model>`, e.g. `/model custom:strata:qwen3.8-flash-next`.
- `model_aliases` — short names (`ds`, `strata`) for `/model` and `--model`.

## Secrets

No secret is inlined in `config.yaml`. Keys are referenced by name and live only in
`~/.hermes/.env` (mode `600`, gitignored):

| Variable | Used by |
|---|---|
| `DEEPSEEK_API_KEY` | `model.provider=deepseek`, `ds` alias |
| `API_SERVER_KEY` | gateway API on `127.0.0.1:8642` (auto-generated) |
| `STRATA_API_KEY` | `providers.strata.key_env`, `model_aliases.strata.key_env` |

`strata` requires its key because it binds beyond loopback. Copy
`.env.example` to `.env` on a fresh machine.

`auth.json` (OAuth credential pool) is also present on a live host and is
gitignored — never commit it.

## Container

Defined in `~/hermes/docker-compose.yml` (image `nousresearch/hermes-agent:stable`).
Two settings there are load-bearing:

- `network_mode: host` — required so the container can reach Strata, which binds
  to the host. A bridged container cannot reach a loopback-bound service.
- `HERMES_UID` / `HERMES_GID` — must match the host user, or the container's
  stage2 hook chowns `/opt/data` to uid 10000 and locks the host out.

Loopback-only listeners: `8642` (gateway API), `9119` (dashboard).

## Operating notes

- **Never run the native installer** (`install.sh`) on a Docker deployment — it
  writes a source tree into `~/.hermes`. Upgrade with `docker compose pull`.
- **Never run `hermes setup --reset`**, and avoid the `model` setup section and
  `--portal`; all three can overwrite `model.provider` / `providers.*` / aliases.
  Prefer `hermes setup --quick` or a single named section.
- Back up `config.yaml` before any wizard run — the container rewrites it.
- `config.yaml` is a large generated file (mostly comments) and will show as
  modified after `hermes config set`. That is expected.

## What is not tracked

Ignored by `/*` and re-included selectively (see `.gitignore`):

- `.env`, `auth.json`, `install_id` — credentials
- `sessions/`, `logs/`, `memories/`, `pairing/` — personal content
- `state.db*`, `kanban.db*`, `cache/`, `runtime/`, `sandboxes/`, `backups/` — state
- `scripts/whatsapp-bridge/`, `skills/` — installed/synced bundles, churn on upgrade

Tracked: `config.yaml`, `SOUL.md`, `README.md`, `.env.example`, `.gitignore`.
