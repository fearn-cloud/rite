Status: done
Label: wayfinder:grilling
Parent: ../MAP.md
Assignee: Codex

# Confirm canonical Git SSH remote

## Question

What canonical SSH remote form should operators and agents use for `michael-fearn/todo` on `git.fearn.cloud`?

Resolve whether the accepted form is explicitly ported, such as `ssh://git@git.fearn.cloud:2222/michael-fearn/todo.git`, or whether the environment should support an unqualified scp-like remote, such as `git@git.fearn.cloud:michael-fearn/todo.git`.

## Blocked by

None - can start immediately.

## Comments

### Resolution

Operators and agents should use the unqualified, scp-like Git SSH remote:

```text
git@git.fearn.cloud:michael-fearn/todo.git
```

The environment should be updated so ordinary Git-over-SSH does not require callers to include an explicit port in the remote URL. The next endpoint work should therefore make default SSH behavior for `git.fearn.cloud` reach Forgejo, rather than treating `:2222` as the canonical user-facing port.
