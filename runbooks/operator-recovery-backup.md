# Operator Recovery Backup

Create and maintain an offline **Recovery Kit** that lets the Operator rebuild
a lost Operator Workstation. The kit is deliberately a separate age identity,
not a copy of the workstation age identity: either identity can decrypt the
repository, and loss of one does not destroy access to the SOPS material.

This runbook protects access to credentials encrypted in the repository,
including the per-Host and per-VM SSH private keys and API credentials. It
does not replace backups of VM data, NAS Datasets, or a password-manager vault.

## Recovery Kit boundary

Use encrypted removable physical media stored away from the normal Operator
Workstation. Keep it offline except during this ceremony, an annual restore
drill, or recovery. A second encrypted copy in a different physical location
protects against media failure; do not keep either copy permanently attached to
a Host, VM, NAS, or the Operator Workstation.

The kit contains only these private files:

- `age/rite-sops-recovery.agekey`: the distinct offline age identity that is a
  SOPS Recipient.
- `ssh/fortress-bootstrap`: the shared bootstrap SSH private key, if it is
  still used to add new Hosts. It is not needed for normal operation after a
  Host has its per-Host credential in its Sibling SOPS File, but retaining it
  prevents a lost workstation from blocking a new-Host bootstrap ceremony.

The repository, `age/recipients.txt`, and `.sops.yaml` are not secret and can
be recovered by cloning the repository. Do not put a general SSH agent,
workstation disk image, cloud-sync credentials, password-manager export, or
unrelated personal keys in this kit. Preserve recovery codes and break-glass
credentials for systems outside Rite in their own documented recovery process;
do not silently add them to the SOPS recovery key.

## Create the offline SOPS identity

Start with the encrypted recovery medium mounted at a path represented below by
`$RECOVERY_MEDIA`. Verify it is the intended encrypted removable medium before
continuing. Do not run this from the repository or use a path inside the
workstation home directory.

```bash
export RECOVERY_MEDIA=/media/operator/rite-recovery
test -d "$RECOVERY_MEDIA"
umask 077
install -d -m 0700 "$RECOVERY_MEDIA/age" "$RECOVERY_MEDIA/ssh"
age-keygen -o "$RECOVERY_MEDIA/age/rite-sops-recovery.agekey"
chmod 0600 "$RECOVERY_MEDIA/age/rite-sops-recovery.agekey"
age-keygen -y "$RECOVERY_MEDIA/age/rite-sops-recovery.agekey"
```

Record the last command's public Recipient in `age/recipients.txt` as the
offline recovery Recipient. The file must contain exactly two non-comment
Recipients: the current workstation Recipient and this recovery Recipient.
Then set `.sops.yaml`'s `age` value to those same two public Recipients,
comma-separated. Public Recipients are safe to commit; never commit an
`AGE-SECRET-KEY-...` value.

Rewrap all existing SOPS files so the recovery identity can decrypt material
created before this ceremony:

```bash
find inventory -type f -name '*.sops.yaml' -print0 \
  | xargs -0 -r sops updatekeys --yes
```

Review and commit the public-recipient and rewrapped-SOPS changes together.
Do not remove the current workstation Recipient until a replacement
workstation identity has been added, rewrapped, and tested.

## Preserve the shared bootstrap SSH key

If `~/.ssh/fortress-bootstrap` exists and is still used, copy it directly to
the mounted encrypted medium while `umask 077` is in effect:

```bash
test -f ~/.ssh/fortress-bootstrap
install -m 0600 ~/.ssh/fortress-bootstrap "$RECOVERY_MEDIA/ssh/fortress-bootstrap"
ssh-keygen -y -f "$RECOVERY_MEDIA/ssh/fortress-bootstrap"
```

Compare the printed public key with the expected bootstrap public key before
unmounting the medium. Never decrypt this or any SOPS-held SSH key to make a
backup: the recovery age identity already grants access to the encrypted
per-Entity keys in the repository.

## Prove the recovery identity works alone

Keep the recovery medium mounted for this test. The command below supplies only
the recovery identity and sends all decrypted data to `/dev/null`; it neither
writes plaintext inventory nor uses the normal workstation key location.

```bash
RECOVERY_KEY="$RECOVERY_MEDIA/age/rite-sops-recovery.agekey"
test -r "$RECOVERY_KEY"
SOPS_AGE_KEY_FILE="$RECOVERY_KEY" \
  python3 -m fortress_inventory.check_sops_decryptable .
```

If that succeeds, the recovery identity can decrypt every committed Sibling
SOPS File. Also confirm the bootstrap key, when present, has mode `0600`:

```bash
test ! -e "$RECOVERY_MEDIA/ssh/fortress-bootstrap" \
  || test "$(stat -c '%a' "$RECOVERY_MEDIA/ssh/fortress-bootstrap")" = 600
```

Unmount or power off the medium and store it separately from the Operator
Workstation. Repeat the decryptability test at least annually and whenever
Recipients change. Do not perform the drill by permanently importing the
recovery identity into `~/.config/sops/age/keys.txt`.

## Lost-workstation recovery

1. Provision a clean workstation with the standard toolchain and clone Rite.
2. Retrieve and mount the Recovery Kit only for the recovery ceremony.
3. Copy the recovery age identity to `~/.config/sops/age/keys.txt` with mode
   `0600`, or set `SOPS_AGE_KEY_FILE` to the mounted identity for the first
   decryptability test.
4. Run the verification command above. Do not proceed if it fails.
5. Create a new workstation age identity, add its public Recipient while
   retaining the recovery Recipient, update `.sops.yaml`, and run `sops
   updatekeys --yes` for every Sibling SOPS File.
6. Verify decryption with the new workstation identity and, separately, the
   recovery identity. Commit the rewrapped files and public-recipient changes.
7. Restore `ssh/fortress-bootstrap` only if a new-Host bootstrap ceremony
   needs it; otherwise leave it on offline media. The SOPS-held per-Entity SSH
   credentials are consumed through normal Rite workflows and remain tmpfs-only
   when decrypted.

If both the workstation and recovery age identities are lost, the encrypted
repository material is intentionally unrecoverable. Rotate any external
credentials that might have been exposed by a lost workstation, even after the
new identity is working.
