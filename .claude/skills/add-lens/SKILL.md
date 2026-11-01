---
name: add-lens
description: Create a review lens for this repo, a read-only agent that judges changes from one domain expert's, persona's or invariant owner's point of view and returns approve / approve-with-changes / block with evidence. Invoke as /add-lens <who> (e.g. "running coach", "tenant-isolation reviewer", "persona: phone-only runner").
argument-hint: <expert, persona, or invariant to guard>
disable-model-invocation: true
---

# /add-lens

Request: `$ARGUMENTS`

A lens is a reviewer that knows **this** repo's domain: a running coach for a
training planner, a payments engineer for a billing app, a persona who only
ever uses a phone. Generic reviewers catch generic bugs. Lenses catch "this is
correct code that does the wrong thing for the people it's for".

## 1. Pin down the lens

From the request and the repo, settle on:

- **slug**: kebab-case, short (`running-coach`, `tenant-isolation`,
  `persona-phone-only`). The agent is `lens-<slug>`.
- **mandate**: one sentence on what it checks and what it blocks.
- **reads**: the real files that hold its source of truth: specs, personas,
  invariants, the code it guards. Check each path exists. If the source of
  truth doesn't exist yet, say so in the mandate ("no persona doc exists;
  argue from the README's stated audience").
- **blocks on**: two to five concrete conditions, taken from the repo's
  stated invariants where possible.
- **for a persona**: who they are, their constraints, and what makes them
  give up or stop trusting the product.

If any of these can't be found in the repo, ask the user once, with your best
guesses as options. First list your agents (`.claude/agents/` and plugin
agents such as `roster-review:security-reviewer`): if a `lens-*` agent or a
generic reviewer (security, accessibility) already covers this, offer to
extend it or narrow the new lens to the domain-specific angle.

Three kinds of lens need slightly different bodies:

- **Invariant owner** (tenant isolation): judges against the repo's stated
  rules.
- **Domain expert** (running coach): also brings established outside
  knowledge, and may flag a repo rule that is itself wrong. Findings from
  outside the repo cite their source and are marked *outside the repo*.
- **Persona** (phone-only runner): walks the changed flow as that person. If
  the repo can render the UI (a Playwright suite, a screenshot script), use it
  at the persona's viewport and settings rather than reading markup alone.

## 2. Write `.claude/agents/lens-<slug>.md`

```markdown
---
name: lens-<slug>
description: <Lens> review: <mandate>. Read-only. Use when a change affects <behavior or symbols, e.g. "plan progression (generatePlan, GOALS)">, or when convened by /panel lenses.
tools: Read, Grep, Glob, Bash
model: inherit
---

You review changes as **<lens>**. <One or two sentences of who this is and what
they care about, in this repo's terms.>

## Sources of truth
- `<path>`: <what it settles>
(Judge against these, not personal taste. If they're silent, say so. <Expert
only: where established practice disagrees with them, say so, cite the source,
and mark it *outside the repo*.>)

## Block when
- <condition>
- <condition>

## How to review
Read the diff and enough surrounding code to follow it. <For a persona: walk
the changed flow as them, step by step, and note where they'd get stuck,
confused, or lose trust.> Don't modify files.

## Verdict
**approve** | **approve-with-changes** | **block**

Each finding: what, where (`path` or flow step), why it matters to <lens>,
and the evidence (file, test, spec section). "No concerns" is a valid answer.
Say it in one line rather than skipping the review.
```

Keep the body under about 40 lines. Every line is loaded on each use, so cut
anything that doesn't change what the lens reports.

## 3. Report

Say which file you wrote, and that a new session (or `/agents`) is needed for
it to load. If the repo's CLAUDE.md already describes this lens in prose, link
that entry to the agent rather than adding a second description.
