---
name: decision-briefings
description: "Use when asked status, open decisions, or next steps."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [communication, status, decisions, reporting, scope]
    related_skills: []
---

# Decision & Status Briefings

For "where are we up to", "remind me what decisions are required", "what's blocking this", "what are my next
steps" — questions asked mid-build, where the state lives in files and installed artifacts rather than in chat.
The deliverable is a short answer, not progress on the work. Doing the work instead (or as well) is the common
failure: it buries the answer under output the user did not ask for.

## When to Use

- The user resumes a multi-session effort and wants its state: what was built, what was verified, what is open.
- The user asks which decisions are still required, or asks for a reminder of them.
- The user asks what is blocking a path forward.

Don't use for: actually resuming the work. If they asked for the work, do the work and brief afterwards.

## Rules

1. **Verify state before briefing.** Read the artifacts on disk (files, installed versions, recorded dry-run or test
   output) rather than reconstructing from conversation memory. Stale memory is how a briefing ends up naming a path
   that no longer exists. Budget a few reads, not an investigation.
2. **Answer in the frame the question was asked.** "What decisions are required" gets the decisions — not the history
   of how they were found, not the option space you considered. "Where are we up to" gets built / verified / open,
   in that order, three short blocks.
3. **A reminder compresses; it does not expand.** Re-read the state, then give a shorter version than last time. A
   reminder that is longer than the original answer is a rewrite, and it reads as if nothing was settled.
4. **Number the open decisions; one entry each.** Per entry: the options one line each, marked (a)/(b)/(c), and say
   plainly which one blocks the others. Name what is *not* a decision in a single line ("LLM is settled — key already
   present") so the user does not re-litigate it.
5. **Stop at the answer.** Do not append a plan, an offer, or a next-steps list that was not asked for. A status
   answer ends when the answer ends; the user asked what they asked because they want to decide, not to be queued
   more work.
6. **Name your access boundary in one line when part of the question is unanswerable from where you sit** (host-side
   data, another machine, a missing credential), give the single smallest thing that would unblock it, and end. Do not
   substitute a batch of commands or a plan for the missing answer unless the plan is what was requested.

## Pitfalls

1. **A "help me understand X" question is still a question.** It licenses an answer about X, not an investigation of
   everything adjacent to X. Answer at the depth asked; surface an adjacent finding in at most one line, then return
   to the question.
2. **When the user narrows scope mid-thread, drop the abandoned thread entirely.** No callback, no "as I mentioned",
   no re-offering it in the same reply. Partial drift on a dropped thread undoes the correction.
3. **Long command blocks are not an answer.** Handing over a runbook reads as pushing the work back to the user.
   Give the conclusion, and the runbook only when one was asked for.
