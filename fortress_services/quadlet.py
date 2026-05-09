from dataclasses import dataclass
from pathlib import PurePosixPath


QUADLET_SYSTEM_PATH = "/etc/containers/systemd"


@dataclass(frozen=True)
class QuadletArtifact:
    filename: str
    content: str

    @property
    def path(self):
        return f"{QUADLET_SYSTEM_PATH}/{self.filename}"


@dataclass(frozen=True)
class ServiceDataDirectory:
    path: str
    uid: int | None = None
    gid: int | None = None


@dataclass(frozen=True)
class RenderedQuadletService:
    artifacts: tuple[QuadletArtifact, ...]
    service_data_directories: tuple[ServiceDataDirectory, ...] = ()

    @property
    def artifacts_by_filename(self):
        return {artifact.filename: artifact for artifact in self.artifacts}


def render_quadlet_service(service, vm):
    network_name = _service_network_name(service)
    artifacts = [
        QuadletArtifact(
            filename=f"{network_name}.network",
            content="\n".join(
                [
                    "[Network]",
                    f"NetworkName={network_name}",
                    "",
                ]
            ),
        )
    ]
    for container in service["deploy"]["containers"]:
        runtime_name = _container_runtime_name(service, container)
        artifacts.append(
            QuadletArtifact(
                filename=f"{runtime_name}.container",
                content=render_quadlet_container(service, vm, container),
            )
        )
    return RenderedQuadletService(
        artifacts=tuple(artifacts),
        service_data_directories=tuple(_service_data_directories(service)),
    )


def render_quadlet_container(service, vm, container):
    mount_by_name = {
        mount.get("name"): mount
        for mount in vm.get("mounts", []) or []
        if mount.get("name")
    }
    required_units = []
    ordered_after_units = []
    bound_units = []
    for dependency in container.get("depends_on", []) or []:
        dependency_unit = f"fortress-{service['name']}-{dependency}.service"
        required_units.append(dependency_unit)
        ordered_after_units.append(dependency_unit)
        bound_units.append(dependency_unit)
    lines = [
        "[Unit]",
        f"Description=Fortress Service {service['name']} container {container['name']}",
        "",
        "[Container]",
        f"ContainerName={_container_runtime_name(service, container)}",
        f"Image={container['image']}",
        f"Network={_service_network_name(service)}",
        f"NetworkAlias={container['name']}",
    ]

    for published_port in container.get("published_ports", []) or []:
        lines.append(f"PublishPort={_published_port(published_port)}")

    for volume in container.get("volumes", []) or []:
        if volume.get("mount"):
            mount = mount_by_name[volume["mount"]]
            mount_unit = systemd_mount_unit_name(mount["mount_point"])
            required_units.append(mount_unit)
            ordered_after_units.append(mount_unit)
            lines.append(
                f"Volume={_share_backed_volume_source(mount, volume)}:"
                f"{volume['container']}:{_volume_mode(volume, mount)}"
            )
        else:
            lines.append(
                f"Volume={_service_owned_volume_source(service, volume)}:"
                f"{volume['container']}:{_volume_mode(volume)}"
            )

    unit_lines = []
    if required_units:
        unit_lines.append(f"Requires={_unique_units(required_units)}")
    if ordered_after_units:
        unit_lines.append(f"After={_unique_units(ordered_after_units)}")
    if bound_units:
        unit_lines.append(f"BindsTo={_unique_units(bound_units)}")
    if unit_lines:
        lines[2:2] = unit_lines

    return "\n".join(lines) + "\n"


def systemd_mount_unit_name(mount_point):
    return f"{mount_point.strip('/').replace('/', '-')}.mount"


def _service_network_name(service):
    if service.get("service_group"):
        return f"fortress-group-{service['service_group']}"
    return f"fortress-{service['name']}"


def _container_runtime_name(service, container):
    return f"fortress-{service['name']}-{container['name']}"


def _published_port(published_port):
    bind = published_port.get("bind")
    host = published_port.get("host", published_port["container"])
    container = published_port["container"]
    protocol = published_port.get("protocol", "tcp")
    protocol_suffix = "tcp,udp" if protocol == "tcp_udp" else protocol
    if bind:
        return f"{bind}:{host}:{container}/{protocol_suffix}"
    return f"{host}:{container}/{protocol_suffix}"


def _unique_units(units):
    return " ".join(dict.fromkeys(units))


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


def _service_data_directories(service):
    owner = service.get("service_data_owner") or {}
    directories = []
    seen = set()
    for container in service.get("deploy", {}).get("containers", []) or []:
        for volume in container.get("volumes", []) or []:
            if "service_path" not in volume:
                continue
            path = _service_owned_volume_source(service, volume)
            if path in seen:
                continue
            seen.add(path)
            directories.append(
                ServiceDataDirectory(
                    path=path,
                    uid=owner.get("uid"),
                    gid=owner.get("gid"),
                )
            )
    return directories
