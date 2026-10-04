# AI Trainings

Companion repo for the **AI Assisted Engineering** sessions: [open the sessions page](https://claude.ai/artifact/RJ8dsCQrrkQUBzuwnMJszq).

Everything here is a normal Claude Code project setup under `.claude/`: skills, subagents, hooks, and permissions. Open this repo in Claude Code to try them.

## Directory structure

```
ai-trainings/
├── CLAUDE.md                          project memory, loaded in every session
└── .claude/
    ├── settings.json                  permissions: allow, ask, deny
    ├── skills/
    │   ├── python-fastapi-coding-conventions/
    │   ├── python-fastapi-test-conventions/
    │   ├── git-push-workflow/
    │   ├── modular-monolith-architecture/
    │   ├── design-multi-tenant-saas/
    │   ├── implementation-spec/
    │   ├── llm-integration/
    │   ├── build-tickets-from-feature/  orchestrator skill
    │   └── build-prs-from-tickets/      orchestrator skill
    ├── agents/
    │   ├── ticket-drafter.md          drafts tickets (read-only)
    │   ├── ticket-implementer.md      implements one ticket in its own worktree
    │   ├── diff-reviewer.md           reviews one ticket's diff (read-only)
    │   └── test-runner.md             runs `make test`
    └── hooks/
        ├── guard-test-runner.sh       blocks installs, deletes, pushes, network for test-runner
        └── block-no-verify.sh         stops ticket-implementer skipping git hooks
```

| Part | What it shows |
|---|---|
| `skills/` | Knowledge skills (conventions, architecture) and two orchestrator skills that start subagents |
| `agents/` | Subagents with preloaded skills (`skills:`) and their own hooks (`hooks:`) in the frontmatter |
| `hooks/` | Scripts that always run, whatever the agent decides |
| `settings.json` | Permission rules: `deny` always wins, then `ask`, then `allow` |

## The PR factory flow

Two orchestrator skills turn one feature into reviewed, tested pull requests:

```
build-tickets-from-feature            build-prs-from-tickets
  agree the scope with you              pull the issues
  ticket-drafter drafts tickets   ──►   ticket-implementer builds each ticket
  you review them one by one            diff-reviewer reviews the diff
  create the issues                     test-runner runs make test
                                        ticket-implementer opens the PR
```

The same setup as an installable plugin: [feature-to-pr-factory in claude-everything](https://github.com/aishajv/claude-everything/tree/main/plugins/feature-to-pr-factory).
