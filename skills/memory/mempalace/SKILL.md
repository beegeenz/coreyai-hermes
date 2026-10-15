---
name: mempalace
description: "Query and maintain the shared MemPalace memory: verify facts before answering, file durable memories, keep single-valued facts current."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Memory, Mempalace, Recall, Knowledge Graph, Facts, Diary, Shared Memory]
    related_skills: [gpt-researcher, grounded-citations]
---

# MemPalace Shared Memory

A persistent, semantic memory shared across agents. The tools live on MCP server
`home-mempalace` (`http://127.0.0.1:8765/mcp`). There is no local install, no venv, and no key
of your own — the server holds its own credentials.

## Invoking the Tools — Read This First

The palace's 45 tools are **deferred**: their schemas are deliberately stripped from your tool
list to keep context lean. They are NOT missing. Never call `mempalace_*` as a top-level tool —
it will fail. Invoke every one through the native Tool Search bridge:

```
tool_call(name="mcp__home_mempalace__mempalace_status", arguments={})
tool_call(name="mcp__home_mempalace__mempalace_kg_query",
          arguments={"entity": "Alice"})
```

Rules:

- The wire name is always `mcp__home_mempalace__` + the bare tool name (double underscores; the
  server component uses an underscore, not the hyphen of `home-mempalace`).
- Every bare `mempalace_*` name in this skill means exactly that: pass
  `name="mcp__home_mempalace__<that name>"` to `tool_call`, with the arguments shown.
- You do **not** need `tool_search` or `tool_describe` first when this skill gives you the tool
  name and arguments — call `tool_call` directly. Use `tool_describe` only when a parameter is
  uncertain, and `tool_search` only for tools this skill never mentions.
- Batch independent palace calls into one `tool_call` via
  `calls=[{name, arguments}, …]` when you need several at once.

Everything below uses the bare names for readability.

Storage is not memory. The value comes from **querying before you speak** and **writing back
what you learned**. A drawer you never retrieve is a drawer that never happened.

## When to Use

Reach for the palace when a question is about **this** person, project, household, or past
session — anything a generic model cannot know:

- Names, relationships, ages, roles, health, preferences, past decisions
- "What did we decide about…", "when did X break", "what's my/their Y now"
- Hardware, network, device, or speaker-specific facts about this installation
- Resuming work another agent (or a past you) started
- Recording an outcome, preference, or lesson at the end of meaningful work

Don't use it for:

- General knowledge, or anything a web search answers better → `web_search`, or the
  `gpt-researcher` skill for multi-source reports
- Facts already in front of you in the current conversation
- Secrets, tokens, or API keys — **never file these**. The palace is shared and searchable.
- Bulk file ingestion → `mempalace_mine` is a separate, deliberate operation

## Core Protocol

Follow this order. It is the whole point of the skill.

1. **On wake-up**, call `mempalace_status` once. It returns the wing/room map, the AAAK
   dialect spec, and the server's own protocol text. Everything else is scoped by that map.
2. **Before answering** about any person, project, or past event, call `mempalace_kg_query`
   (structured facts) or `mempalace_search` (prose recall). Never guess. If unsure, say
   "let me check" and query — wrong is worse than slow.
3. **Before writing**, call `mempalace_check_duplicate`. Filing the same fact twice poisons
   recall; the palace does not silently merge.
4. **After meaningful work**, call `mempalace_diary_write` with what happened and what matters.

## Choosing a Tool

| Need | Tool |
|---|---|
| Structured fact about an entity (who/what/when, time-valid) | `mempalace_kg_query(entity)` |
| "What does the palace say about X" in prose | `mempalace_search(query)` |
| Chronology for one entity | `mempalace_kg_timeline(entity)` |
| Free-text recall, fuzzy, semantic | `mempalace_search(query, wing=…, room=…)` |
| Exact record, you have the id | `mempalace_get_drawer(drawer_id)` |
| Browse what exists | `mempalace_list_wings` → `mempalace_list_rooms(wing)` |
| Ideas connected to a room | `mempalace_traverse(start_room)` |
| Bridge between two domains | `mempalace_find_tunnels(wing_a, wing_b)` |

`mempalace_kg_query` answers **facts with validity intervals**; `mempalace_search` answers
**"what do I remember about…"**. When a fact is single-valued and time-bounded, prefer the KG.

## Writing

```
mempalace_check_duplicate(content="…")        # threshold default; skip filing if it hits
mempalace_add_drawer(wing=…, room=…, content="…")
```

Or batch a whole session with `mempalace_checkpoint(items=[…], diary="…")`, which dedups each
item and writes the diary entry in one call. Prefer it at session end.

**Wing and room are the taxonomy — pick deliberately**, or recall degrades. Reuse an existing
wing/room from `mempalace_get_taxonomy` rather than inventing a near-synonym; a new spelling of
an existing wing splits the index. Rooms are hyphenated slugs naming an idea
(`gpu-pricing`, `chromadb-setup`), not generic buckets.

### Changing a fact

This is where agents get it wrong:

- Single-valued fact **changed** (employer, model, address, version) →
  `mempalace_kg_supersede(subject, predicate, old_object, new_object)`. One atomic call at one
  boundary.
- Fact **stopped being true**, nothing replaces it → `mempalace_kg_invalidate`.
- **Independent** fact that can coexist (a second speaker, an extra device) → `mempalace_kg_add`.

Never hand-roll `invalidate` + `add` for a changed value: it leaves old and new overlapping at
the boundary, and later queries return both.

## AAAK

Drawers and diary entries use AAAK, a compressed dialect both humans and models read directly —
3-letter entity codes (`ALC`=Alice), `*emotion*` markers (`*warm*`, `*fierce*`), pipe-separated
`FAM:`/`PROJ:`/`⚠` fields, ISO dates, `Nx` mention counts, `★`–`★★★★★` importance. Read it
naturally; don't announce that you are decoding it. When writing, keep it tight and reuse codes
already present in the palace. `mempalace_get_aaak_spec` returns the full grammar.

## Destructive Operations

`mempalace_delete_drawer`, `mempalace_delete_by_source`, `mempalace_sync`, and
`mempalace_delete_tunnel` are irreversible against a **shared** store other agents depend on.
Confirm with the user first, and use `dry_run`/`apply=false` variants when a tool offers them.
Never delete to clean up recall noise you caused by filing a duplicate — update or supersede
instead.

## Troubleshooting

- **"Unknown tool" on a bare `mempalace_*` name** — you called it as a top-level tool. Wrap it:
  `tool_call(name="mcp__home_mempalace__<tool>", arguments={…})`.
- **Tools missing entirely** (no `home-mempalace` group in the `tool_search` listing) — the MCP
  server isn't loaded in this session. Check `hermes mcp list` for `home-mempalace`;
  `/reload-mcp` or a fresh session picks it up.
- **Stale counts after another agent wrote** — call `mempalace_reconnect` to force a re-read
  of the palace.
- **Auth errors** — the bearer token lives in `~/.hermes/.env` as `MCP_HOME_MEMPALACE_API_KEY`.
  Rotating the server token means updating that **and** `~/.config/opencode/mempalace.token`,
  then `hermes mcp test home-mempalace`.
- **Empty search is not proof of absence.** Try `mempalace_kg_query`, a different wing, or a
  broader phrasing before concluding the palace doesn't know.

## Notes

- The palace is **shared state**. Write conservatively, cite what you filed, and don't assume a
  drawer you found was written by the same agent you are now.
- `mempalace_status` also reports backend health (`sqlite_integrity`) — worth a glance if recall
  behaves oddly.
