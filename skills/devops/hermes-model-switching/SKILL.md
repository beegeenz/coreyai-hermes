---
name: hermes-model-switching
description: Change which LLM or provider Hermes uses, safely. Use when asked to switch models, use a local/self-hosted model, change provider, or when a turn fails with HTTP 400 about unsupported model names.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, model, provider, configuration, gateway, self-hosting]
    category: devops
---

# Switching Hermes' Model

Changing `model.*` is a live, gateway-wide change: it affects every platform
(Telegram, CLI, email) on the next turn, and a wrong pair fails **silently at
config level and loudly at call level**. Follow this exactly.

## The invariant

`model.provider` and `model.default` must describe the **same backend**:

| Goal | `model.provider` | `model.default` |
|---|---|---|
| Online DeepSeek | `deepseek` | `deepseek-flash` (or `deepseek-v4-pro`) |
| Local Strata (V100) | `strata` | `qwen3.8-flash-next` |

**Never put a bare alias name in `model.default`.** `model_aliases:` entries
are shortcuts for `/model` and `--model`; they are **not** valid as the
persisted default. Writing `model.default: strata` while `provider: deepseek`
makes Hermes ask DeepSeek for a model *named* `strata`:

```
HTTP 400: The supported API model names are deepseek-flash, deepseek-v4-pro,
          but you passed strata.
```

That is a `BadRequestError` — **not retried** — so every turn fails until fixed.

## Procedure

1. **Change both keys, never one.**

   ```bash
   hermes config set model.provider strata
   hermes config set model.default qwen3.8-flash-next
   ```

   For DeepSeek: `model.provider deepseek` + `model.default deepseek-flash`.

2. **Check the pair with the guard** (exits non-zero on a broken pair):

   ```bash
   sh "$HERMES_HOME/tools/check-model.sh"
   ```

3. **Verify with NO flags.** This is the step that matters:

   ```bash
   hermes chat -Q -q "Reply with exactly: OK"
   ```

   Flags like `--provider` / `--model` **override config**, so they exercise a
   different code path than the gateway. A test with flags can pass while the
   gateway stays broken — that is exactly how the 2026-10-19 outage survived
   its own "verification".

4. **Confirm the wire, not just the reply.** The turn must name the endpoint
   you intended:

   ```bash
   grep 'conversation turn' "$HERMES_HOME/logs/agent.log" | tail -1
   grep -o 'provider=[^ ]* base_url=[^ ]* model=[^ ]*' "$HERMES_HOME/logs/agent.log" | tail -1
   ```

   Expected for Strata:
   `provider=custom base_url=http://127.0.0.1:8080/v1 model=qwen3.8-flash-next`

5. **Record it** (the config dir is a git repo):

   ```bash
   git -C "$HERMES_HOME" add config.yaml && git -C "$HERMES_HOME" commit -m "model: <provider>/<model>"
   ```

## Prerequisites for a local backend

- The server must be **up**: `curl -s http://127.0.0.1:8080/health`
  (Strata: `systemctl --user start strata-128k`).
- Its key must be in `~/.hermes/.env` and referenced with `key_env:` — never
  inlined in `config.yaml` (that file is version-controlled).
- The named provider must exist under `providers:`; `provider: strata` resolves
  to it and surfaces as `provider=custom` at runtime.

## When it is already broken

1. Read the last turn record to get the actual `provider=` / `base_url=` / `model=`.
2. `sh "$HERMES_HOME/tools/check-model.sh"` — it names the specific mismatch.
3. Fix both keys, then re-verify per step 3.

## Do not

- Do not set only `model.default`, or only `model.provider`.
- Do not `--force` a config write to paper over a validation complaint.
- Do not restart the gateway as a substitute for fixing the pair; a restart
  reloads the same broken config.
- Do not assume a successful `--provider X --model Y` test means the persisted
  config works.
