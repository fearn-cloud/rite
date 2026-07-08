Status: ready-for-agent
Label: wayfinder:task
Parent: ../MAP.md

# Prove pull and push for todo

## Question

Can this workspace pull from and push to `michael-fearn/todo` over the accepted `git.fearn.cloud` SSH remote?

Perform the final acceptance proof in a temporary worktree or clone. Pull/fetch must succeed, then a harmless push must be made and verified. Record exactly what branch/ref was touched and whether any cleanup was performed.

## Blocked by

- .scratch/git-over-ssh/issues/03-confirm-forgejo-ssh-authz-for-todo.md
- .scratch/git-over-ssh/issues/06-implement-inventory-managed-caddy-ssh-forwarding.md

## Comments
