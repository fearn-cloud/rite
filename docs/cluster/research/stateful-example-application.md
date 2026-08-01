> Historical Canon source — migrated to Rite on 2026-07-31 from `docs/research/stateful-example-application.md`. See [migration status](../README.md).

# Stateful example application

_Research current on 2026-07-26. Sources are first-party application documentation and repositories._

## Recommendation

Use **linkding with its default SQLite database** for Canon's first stateful example.

It is a genuinely useful bookmark manager, yet its operational shape stays small: the basic image is a single application container, SQLite is the default, and the project says the image runs on ARM platforms including Raspberry Pi. The optional `-plus` image adds Chromium, memory use, and storage demand, so Canon should use the basic image for this milestone. [linkding installation](https://linkding.link/installation/) The application still provides enough real state to exercise a persistent volume, ingress and TLS, a generated credential, backup export, off-cluster retention, full-loss restore, and verification.

Most importantly, linkding has an application-native, transaction-safe backup path. `python manage.py full_backup` creates a ZIP containing the SQLite database plus bookmark assets, favicons, and previews. The official restore procedure extracts that archive as the data directory of a fresh installation. The documentation explicitly warns that copying a live SQLite file is not transaction-safe, so the full-backup command should be the required path. [linkding backup and restore](https://linkding.link/backups/)

### Restore acceptance check

Before the backup, create a sentinel bookmark through the normal application path with:

- URL `https://example.invalid/canon-restore-sentinel`
- title `Canon restore sentinel`
- a randomly generated nonce in `notes`
- tag `canon-restore-test`

After rebuilding the Cluster from Git and restoring the backup into a fresh volume:

1. Reach linkding through its normal `home.arpa` HTTPS hostname and log in.
2. Fetch `GET /api/bookmarks/check/?url=https%3A%2F%2Fexample.invalid%2Fcanon-restore-sentinel`.
3. Require a non-null bookmark whose URL, title, nonce, and tag all match the pre-backup values.

The exact-URL check and returned bookmark fields are part of linkding's documented REST API, making this stronger than a visual "page loads" check. [linkding REST API](https://linkding.link/api/)

## Ranked candidates

| Rank | Application | Why it fits | Why it ranks here | Unambiguous restore evidence |
|---|---|---|---|---|
| 1 | **linkding** | Minimal bookmark manager; one basic container; SQLite by default; native full-backup ZIP covers the database and file assets. [Project overview](https://github.com/sissbruecker/linkding), [installation](https://linkding.link/installation/), [backups](https://linkding.link/backups/) | Smallest operational surface while still exercising every Canon recovery contract. Its backup artifact also keeps application state separate from Git-declared configuration. | Exact sentinel bookmark lookup over the documented API, comparing URL, title, notes nonce, and tag. [API](https://linkding.link/api/) |
| 2 | **Vikunja** | Useful task/project manager delivered as one binary or container; SQLite is the default and is recommended for personal use. Its `dump` command includes configuration, version, uploaded files, and the full database, and `restore` consumes that ZIP. [Installation](https://vikunja.io/docs/installing/), [CLI](https://vikunja.io/docs/cli/) | Nearly as compact and its CLI has explicit dump and restore commands. It ranks second because its richer feature set adds application-specific surface, and the dump includes configuration; that makes the backup sensitive and overlaps with Git/SOPS-managed Cluster Desired State unless restore uses `--preserve-config`. | Restore a project containing a uniquely named task, description nonce, label, due date, and attachment; verify all fields and attachment bytes through the normal hostname. |
| 3 | **Mealie** | Genuinely useful recipe manager with recipes, meal plans, and shopping lists. The supported SQLite deployment is one container, is described as suitable for 1–20 users, and the example caps memory at 1000 MB. It provides integrated backup/upload/restore in the admin UI. [Introduction](https://docs.mealie.io/documentation/getting-started/introduction/), [SQLite installation](https://docs.mealie.io/documentation/getting-started/installation/sqlite/), [backup and restore](https://docs.mealie.io/documentation/getting-started/usage/backups-and-restoring/) | Still modest, but more application behavior and a UI-oriented backup workflow distract from infrastructure automation. The official docs call a stopped copy of `/app/data` the best SQLite site backup, which is less useful for demonstrating an online application-native backup pipeline. | Restore a uniquely named recipe containing a nonce in its instructions plus a tagged shopping-list item, then confirm both in the UI. |
| 4 | **Paperless-ngx** | Excellent recovery semantics: `document_exporter` captures documents, thumbnails, metadata, settings, and database contents; `document_importer` restores a fresh instance. [Administration](https://docs.paperless-ngx.com/administration/) | Do not use for the first milestone. A Redis-compatible broker is required, document ingestion uses background workers and OCR, and exports must be imported into the same application version. Those are worthwhile later but make application complexity a central lesson now. [Setup](https://docs.paperless-ngx.com/setup/), [configuration](https://docs.paperless-ngx.com/configuration/), [administration](https://docs.paperless-ngx.com/administration/) | Import a uniquely named one-page PDF, assign a correspondent and tags including a nonce, then verify metadata and downloaded file checksum after restore. |

## Consequences for the milestone specification

- Pin the linkding image version in Git. For the disaster drill, first restore using the same version that created the backup; test upgrade behavior separately.
- Use the basic image and SQLite. Website snapshots are optional and should be disabled initially; enabling them changes both resource needs and backup size.
- Schedule the native `full_backup` command and move its ZIP to the External Recovery Substrate. A successful file creation inside the Cluster is not a successful backup.
- Record backup timestamp, application image version, archive checksum, and sentinel nonce outside the Cluster so the drill can prove which recovery point was restored.
- Treat the API verification credential as a recoverable secret. The drill must not depend on a credential that existed only inside the lost Cluster.

## Decisions newly exposed

1. **How will Kubernetes invoke and externalize linkding's native backup?** Choose between an application sidecar, an application-aware CronJob that mounts the volume, or another controlled mechanism; avoid granting broad Kubernetes API permissions merely to `exec` into the running Pod.
2. **What recovery-point and retention objectives apply to the example data?** These determine schedule, pruning, and how much loss the acceptance drill permits.
3. **Will bookmark HTML snapshots be in scope?** Keeping them disabled preserves the recommended small footprint; enabling them intentionally adds file-asset recovery and Chromium resource costs.
4. **Where is the restore-verification credential held and rotated?** It must survive total Cluster loss without making the application credential part of Git plaintext.
