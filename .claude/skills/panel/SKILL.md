---
name: panel
description: Convene a panel of the repo's roster agents (planning, design, review, testing, or its domain lenses) on one task, run them in parallel, and merge their output into a single ranked, de-duplicated result. Invoke as /panel <stage> [target].
argument-hint: <plan|design|review|test|lenses> [what to look at]
disable-model-invocation: true
---

# /panel

Arguments: `$ARGUMENTS`

The first word is the **stage**. The rest is the **target**: a feature
description, a path, a PR number, or a branch. If the target is missing, use
the default for the stage below.

## 1. Seat the panel

Check the agent types you can launch and seat **only agents that exist** from
the stage's roster. They come from `.claude/agents/` or from a plugin, which
prefixes the name (`roster-review:code-reviewer`). A roster name matches
either form; if both exist, seat the unprefixed one.

| Stage | Roster | Default target |
|---|---|---|
| `plan` | product-manager, software-architect | Ask what to plan. |
| `design` | ux-designer, visual-designer, accessibility-specialist, content-designer | The UI touched by the current diff. |
| `review` | code-reviewer, security-reviewer, performance-reviewer, maintainability-reviewer | The current diff (`git diff` + `git diff --staged`; on a branch with no local changes, `git diff <default-branch>...HEAD`). |
| `test` | test-engineer, qa-explorer, e2e-test-engineer | The current diff. |
| `lenses` | every `lens-*` agent | The current diff. |

If the stage is unknown or no agents for it exist, say which rosters are
installed and stop.

Skip members whose lens doesn't apply. For example, drop the visual-designer
for a copy-only change, or drop the performance-reviewer for a docs change. Say
who you skipped, in one line.

## 2. Brief once, dispatch in parallel

Write one shared brief: the target, the exact diff or paths, the relevant
CLAUDE.md conventions, and what "done" looks like. Then launch every seated
agent **in a single message**, so they run concurrently. Give each one the brief
plus one line on its specific lens. Don't make agents rediscover context you
already have.

For `plan`, run the product-manager first and pass its output to the
software-architect. Architecture without scope is guesswork.

For `lenses`, seat **every** lens; don't skip any. A lens whose angle doesn't
apply answers *n/a* with a reason, so a skipped lens can't pass for an
approving one. Add a `Verdicts:` line to the output (`lens-x: approve ·
lens-y: block`), and any **block** makes the verdict **rework**.

For `test`, testers that write tests may edit files. Before dispatching, ask
whether this run should **write tests** or only **propose cases and find bugs**.

## 3. Synthesize

Don't paste the agents' reports end to end. Merge them:

1. **Verify.** Drop findings that cite code which doesn't exist or behavior you
   can disprove in a minute. Mark anything unverified as *plausible*.
2. **De-duplicate.** When several agents found the same issue, keep one entry
   and credit every lens ("security + correctness").
3. **Rank** everything on one scale: what reaches users or attackers first, and
   how badly. A blocker from any lens outranks style from all of them.
4. **Resolve conflicts.** When agents disagree (for example, the visual designer
   wants an icon-only button and the accessibility specialist objects), state
   the trade-off and recommend one option.

## Output

```markdown
## Panel: <stage> — <target>
Seated: <agents> · Skipped: <agents + why>

### Must fix
1. <finding> — `path:line` — <lens(es)>
   <one-line why> → <fix>

### Should fix
…

### Consider
…

### Conflicts & trade-offs
…
```

Finish with a one-line verdict: **ship**, **ship after must-fix**, or **rework**.
Don't apply fixes unless the user asks.
