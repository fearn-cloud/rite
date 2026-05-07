from pathlib import PurePosixPath


def share_backed_volume_subpaths(service, vm):
    mount_by_name = {
        mount.get("name"): mount
        for mount in vm.get("mounts", []) or []
        if mount.get("name")
    }
    subpaths = []
    for container in service.get("deploy", {}).get("containers", []) or []:
        for volume in container.get("volumes", []) or []:
            mount_name = volume.get("mount")
            source = volume.get("source")
            if not mount_name or source in (None, "/"):
                continue
            mount = mount_by_name[mount_name]
            subpaths.append(str(PurePosixPath(mount["mount_point"]) / source))
    return subpaths
