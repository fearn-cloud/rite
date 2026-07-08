Status: done
Label: wayfinder:task
Parent: ../MAP.md
Assignee: Codex

# Make git.fearn.cloud SSH reach Forgejo

## Question

What live endpoint change makes the chosen unqualified `git.fearn.cloud` SSH remote reach the Forgejo Service rather than requiring callers to specify port `2222`?

Use the existing evidence from the Forgejo upgrade verification as the starting point: `git.fearn.cloud` resolved to the internal Ingress VM (`10.40.0.16`), while Forgejo listens on `forgejo-vm` (`10.40.0.12`) port `2222`. Resolve the immediate routing/forwarding owner, apply the smallest reversible change if appropriate, and record whether default SSH to `git.fearn.cloud` reaches Forgejo for the canonical remote `git@git.fearn.cloud:michael-fearn/todo.git`.

## Blocked by

- .scratch/git-over-ssh/issues/01-confirm-canonical-git-ssh-remote.md

## Comments

### Resolution

The immediate viable owner for the chosen unqualified remote in this workspace is the workspace SSH client configuration, not a live ingress TCP forwarding change.

Findings:

- `git.fearn.cloud` still resolves to `10.40.0.16`, the internal ingress VM.
- Default TCP/22 on `10.40.0.16` is the ingress VM's management OpenSSH daemon, not Forgejo. Its host key was observed as `SHA256:E7KH8am5JageIfruY8Lcs8R+gQgQGF7PDgNvjKQA+RI`.
- TCP/2222 on `git.fearn.cloud`/`10.40.0.16` is refused.
- Forgejo is healthy on `forgejo-vm` (`10.40.0.12`), with the container SSH listener published as host port `2222`.
- The live Caddy build on `internal-ingress-vm` has no `layer4`, raw TCP, or SSH proxy module; replacing port 22 on the ingress VM would collide with VM management SSH.

Applied workspace change:

```sshconfig
Host git.fearn.cloud
    HostName 10.40.0.12
    Port 2222
    User git
    StrictHostKeyChecking accept-new
```

This was written to `/home/vscode/.ssh/config`, and `/home/vscode/.ssh` ownership was corrected so `known_hosts` can be written by the `vscode` user.

Proof:

- `ssh -G git@git.fearn.cloud` resolves to `hostname 10.40.0.12`, `port 2222`, `user git`.
- `ssh -o BatchMode=yes -o ConnectTimeout=5 git@git.fearn.cloud` connects to `10.40.0.12:2222` and sees Forgejo's SSH server host key `SHA256:tzoaCrIxqtz9uC+OVXGK6/XzNwhy3y990OCJrK74Xa0`.
- `GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=5' git ls-remote git@git.fearn.cloud:michael-fearn/todo.git HEAD` now reaches Forgejo and fails at the expected next boundary: `git@10.40.0.12: Permission denied (publickey)`.

So the canonical remote now reaches Forgejo from this workspace without an explicit port in the remote URL. Repository authorization remains unresolved and belongs to **Confirm Forgejo SSH authorization for todo**.
