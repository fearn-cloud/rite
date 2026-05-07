# NFS mounts as systemd `.mount` units

NFS Shares are mounted via systemd `.mount` units — not `/etc/fstab`, not autofs, not in-container mounts. Datasets are declared separately from the Shares derived from VM Mount and Service consumption declarations; each Mount declares its Dataset and Share protocol explicitly. The `.mount` unit is a first-class systemd dependency, which lets Quadlet containers declare ordering on Share-backed Volumes and start in the correct order. Fstab and autofs offer no equivalent ordering hook, and in-container mounts couple service definitions to NAS topology.
