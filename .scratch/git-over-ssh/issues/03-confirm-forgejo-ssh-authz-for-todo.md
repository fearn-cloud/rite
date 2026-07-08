Status: ready-for-agent
Label: wayfinder:task
Parent: ../MAP.md

# Confirm Forgejo SSH authorization for todo

## Question

Which local SSH identity should this workspace use for Forgejo, and does that identity have pull and push authorization on `michael-fearn/todo`?

Resolve the key selection, known-host behavior, and Forgejo repository authorization without mutating the repository. The expected proof is a successful non-mutating Git-over-SSH read operation against `michael-fearn/todo` after the endpoint reaches Forgejo.

## Blocked by

- .scratch/git-over-ssh/issues/02-make-git-fearn-cloud-ssh-reach-forgejo.md

## Comments
