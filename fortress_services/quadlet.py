from pathlib import PurePosixPath


def render_quadlet_container(service, vm, container):
    mount_by_name = {
        mount.get("name"): mount
        for mount in vm.get("mounts", []) or []
        if mount.get("name")
    }
    unit_dependencies = []
    lines = [
        "[Unit]",
        f"Description=Fortress Service {service['name']} container {container['name']}",
        "",
        "[Container]",
        f"Image={container['image']}",
    ]

    for volume in container.get("volumes", []) or []:
        if volume.get("mount"):
            mount = mount_by_name[volume["mount"]]
            mount_unit = systemd_mount_unit_name(mount["mount_point"])
            unit_dependencies.append(mount_unit)
            lines.append(
                f"Volume={_share_backed_volume_source(mount, volume)}:"
                f"{volume['container']}:{_volume_mode(volume, mount)}"
            )
        else:
            lines.append(
                f"Volume={_service_owned_volume_source(service, volume)}:"
                f"{volume['container']}:{_volume_mode(volume)}"
            )

    if unit_dependencies:
        dependencies = " ".join(dict.fromkeys(unit_dependencies))
        lines[1:1] = [
            f"Requires={dependencies}",
            f"After={dependencies}",
        ]

    return "\n".join(lines) + "\n"


def systemd_mount_unit_name(mount_point):
    return f"{mount_point.strip('/').replace('/', '-')}.mount"


def _share_backed_volume_source(mount, volume):
    if volume["source"] == "/":
        return mount["mount_point"]
    return str(PurePosixPath(mount["mount_point"]) / volume["source"])


def _service_owned_volume_source(service, volume):
    return str(PurePosixPath("/srv/services") / service["name"] / volume["service_path"])


def _volume_mode(volume, mount=None):
    access = volume.get("access")
    if access is None and mount is not None:
        access = mount.get("access")
    return "ro" if access == "read_only" else "rw"
