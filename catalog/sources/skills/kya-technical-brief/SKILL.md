---
name: kya-technical-brief
description: Produce a short, structured KYA technical brief (context, problem, options, decision, next steps). Use when the user asks for a technical note, brief, architecture memo, or a written record of a technical decision.
---

# KYA Technical Brief

Test skill. Produces a one-page technical note, in French, usable directly in a meeting.

Read [references/example-brief.md](references/example-brief.md) before writing the first brief of a session.

## When to use

- The user asks for a technical note, brief, or memo.
- An architecture or stack decision needs to be recorded.
- A technical investigation must be summarized for the team.

Do not use for long product documentation, training guides, or full specifications.

## Required structure

1. **Contexte** - two to four sentences: current state and what triggered the note.
2. **Probleme** - one single, verifiable statement of the problem to solve.
3. **Options** - two to four options, each with benefit, cost, and main risk.
4. **Decision** - the retained option and the reason, in one sentence.
5. **Prochaines etapes** - three to five actions, each with an owner and a due date.

## Required behavior

1. Write in French, short sentences, no decorative jargon.
2. Source every figure, or mark it explicitly as unverified.
3. Keep the note to one page; split the subject into several briefs if it overflows.
4. State uncertainties instead of smoothing them over.
5. Label examples and assumptions explicitly; never invent operational evidence.

Return the brief as Markdown for review. Produce a .docx only when the user explicitly asks for a file to circulate. Do not publish, send, or distribute the brief unless the user explicitly requests that external action.
