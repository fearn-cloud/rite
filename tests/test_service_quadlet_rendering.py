from dataclasses import replace
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fortress_inventory.model import load_inventory_tree
from fortress_inventory.service_runtime_intent import (
    ContainerIdentityRuntimeFact,
    ServiceDataDirectoryRuntimeFact,
    ServiceRuntimeIntent,
    ServiceNetworkIdentityRuntimeFact,
    ServiceOwnedVolumeRuntimeFact,
    ServiceSecretRuntimeFact,
    ServiceUnitOrderRuntimeFact,
    ShareBackedVolumeRuntimeFact,
)
from fortress_services.quadlet import (
    render_quadlet_container,
    render_quadlet_service,
    systemd_mount_unit_name,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "quadlet_rendering"


def quadlet_runtime_intent_fixture(service, vm=None):
    vm = vm or {}
    service_name = service["name"]
    vm_name = service.get("backend", {}).get("vm")
    network_name = (
        f"fortress-network-{service['service_network']}"
        if service.get("service_network")
        else f"fortress-{service_name}"
    )
    containers = service.get("deploy", {}).get("containers", []) or []
    service_secrets = []
    service_owned_volumes = []
    share_backed_volumes = []
    service_data_directories = []
    seen_directories = set()
    owner = service.get("service_data_owner") or {}
    mount_by_name = {
        mount.get("name"): mount
        for mount in vm.get("mounts", []) or []
        if mount.get("name")
    }

    for container_index, container in enumerate(containers):
        for secret_index, secret in enumerate(container.get("secrets", []) or []):
            secret_key = secret["secret"].split(".", 1)[-1]
            service_secrets.append(
                ServiceSecretRuntimeFact(
                    service_name=service_name,
                    container_name=container.get("name"),
                    container_index=container_index,
                    secret_index=secret_index,
                    secret_key=secret_key,
                    podman_name=f"fortress_{service_name}_{secret_key}",
                    env=secret.get("env"),
                    sops_extract=f'["secrets"]["{secret_key}"]["value"]',
                    env_value_mode=secret.get("env_value", "file_path"),
                )
            )
        for volume_index, volume in enumerate(container.get("volumes", []) or []):
            if volume.get("mount"):
                mount = mount_by_name.get(volume["mount"], {})
                source = _share_volume_source(mount, volume)
                share_backed_volumes.append(
                    ShareBackedVolumeRuntimeFact(
                        service_name=service_name,
                        vm_name=vm_name,
                        container_name=container.get("name"),
                        container_index=container_index,
                        volume_index=volume_index,
                        mount_name=volume["mount"],
                        dataset_name=mount.get("dataset"),
                        vm_mount_path=mount.get("mount_point"),
                        resolved_source_path=source,
                        container_path=volume.get("container"),
                        access=volume.get("access") or mount.get("access"),
                        required_mount_unit=systemd_mount_unit_name(mount.get("mount_point")),
                    )
                )
                continue

            vm_path = f"/srv/services/{service_name}/{volume['service_path']}"
            service_owned_volumes.append(
                ServiceOwnedVolumeRuntimeFact(
                    service_name=service_name,
                    vm_name=vm_name,
                    container_name=container.get("name"),
                    container_index=container_index,
                    volume_index=volume_index,
                    service_path=volume["service_path"],
                    vm_path=vm_path,
                    container_path=volume.get("container"),
                    access_mode="ro" if volume.get("access") == "read_only" else "rw",
                )
            )
            if vm_path not in seen_directories:
                seen_directories.add(vm_path)
                service_data_directories.append(
                    ServiceDataDirectoryRuntimeFact(
                        service_name=service_name,
                        vm_name=vm_name,
                        path=vm_path,
                        uid=owner.get("uid"),
                        gid=owner.get("gid"),
                    )
                )

    start_units = _quadlet_start_units(service_name, containers)
    return ServiceRuntimeIntent(
        backends=(),
        published_ports=(),
        telemetry_targets=(),
        service_secrets=tuple(service_secrets),
        service_owned_volumes=tuple(service_owned_volumes),
        service_data_directories=tuple(service_data_directories),
        share_backed_volumes=tuple(share_backed_volumes),
        native_environment_secrets=(),
        service_network_identities=(
            ServiceNetworkIdentityRuntimeFact(
                service_name=service_name,
                vm_name=vm_name,
                declared_service_network=service.get("service_network"),
                podman_name=network_name,
                isolated=not bool(service.get("service_network")),
            ),
        ),
        container_identities=tuple(
            ContainerIdentityRuntimeFact(
                service_name=service_name,
                vm_name=vm_name,
                container_name=container.get("name"),
                container_index=container_index,
                container_alias=container.get("name"),
                podman_name=f"fortress-{service_name}-{container['name']}",
                systemd_unit_name=f"fortress-{service_name}-{container['name']}.service",
                service_network_podman_name=network_name,
            )
            for container_index, container in enumerate(containers)
        ),
        service_unit_orders=(
            ServiceUnitOrderRuntimeFact(
                service_name=service_name,
                vm_name=vm_name,
                start_units=tuple(start_units),
                stop_units=tuple(reversed(start_units)),
            ),
        ),
        diagnostics=(),
    )


def _share_volume_source(mount, volume):
    if volume.get("source") == "/":
        return mount.get("mount_point")
    return f"{mount.get('mount_point')}/{volume.get('source')}"


def _quadlet_start_units(service_name, containers):
    by_name = {container["name"]: container for container in containers}
    ordered = []
    visiting = set()
    visited = set()

    def visit(container_name):
        if container_name in visited:
            return
        if container_name in visiting:
            raise ValueError(f"cycle in Container Dependency graph for Service {service_name}")
        visiting.add(container_name)
        for dependency in by_name[container_name].get("depends_on", []) or []:
            visit(dependency)
        visiting.remove(container_name)
        visited.add(container_name)
        ordered.append(f"fortress-{service_name}-{container_name}.service")

    for container in containers:
        visit(container["name"])
    return ordered


class ServiceQuadletRenderingTests(unittest.TestCase):
    def test_quadlet_rendering_requires_service_runtime_intent(self):
        service = {
            "name": "paperless",
            "backend": {"vm": "media01", "port": 8000},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "web",
                        "image": "ghcr.io/paperless-ngx/paperless-ngx:2.13.5",
                    }
                ],
            },
        }

        with self.assertRaisesRegex(
            ValueError,
            "Service Runtime Intent is required to render Quadlet artifacts for Service paperless",
        ):
            render_quadlet_service(service, {})

    def test_quadlet_container_rendering_requires_service_runtime_intent(self):
        service = {
            "name": "paperless",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "web",
                        "image": "ghcr.io/paperless-ngx/paperless-ngx:2.13.5",
                    }
                ],
            },
        }

        with self.assertRaisesRegex(
            ValueError,
            "Service Runtime Intent is required to render Quadlet container for Service paperless",
        ):
            render_quadlet_container(service, {}, service["deploy"]["containers"][0])

    def test_golden_service_network_multi_container_rendering(self):
        service = {
            "name": "immich",
            "service_group": "media",
            "service_network": "media",
            "service_data_owner": {"uid": 1000, "gid": 1000},
            "backend": {"vm": "media01", "port": 2283},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                        "published_ports": [
                            {
                                "bind": "127.0.0.1",
                                "host": 2283,
                                "container": 2283,
                                "protocol": "tcp",
                                "ingress": True,
                            }
                        ],
                        "volumes": [
                            {
                                "service_path": "upload",
                                "container": "/usr/src/app/upload",
                                "access": "read_write",
                            },
                            {
                                "mount": "media",
                                "source": "photos",
                                "container": "/photos",
                                "access": "read_only",
                            },
                        ],
                        "depends_on": ["postgres"],
                    },
                    {
                        "name": "postgres",
                        "image": "postgres:16",
                    },
                ],
            },
        }
        vm = {
            "mounts": [
                {
                    "name": "media",
                    "dataset": "media",
                    "protocol": "nfs",
                    "mount_point": "/mnt/nas/media",
                    "access": "read_write",
                }
            ]
        }

        rendered = render_quadlet_service(service, vm, runtime_intent=quadlet_runtime_intent_fixture(service, vm))

        self.assert_golden_artifacts(rendered, GOLDEN_FIXTURES / "service_network_multi")
        self.assertEqual(
            [("/srv/services/immich/upload", 1000, 1000)],
            [
                (directory.path, directory.uid, directory.gid)
                for directory in rendered.service_data_directories
            ],
        )

    def test_golden_isolated_single_container_with_share_backed_root_mount(self):
        service = {
            "name": "paperless",
            "backend": {"vm": "media01", "port": 8000},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "web",
                        "image": "ghcr.io/paperless-ngx/paperless-ngx:2.13.5",
                        "volumes": [
                            {
                                "mount": "documents",
                                "source": "/",
                                "container": "/documents",
                                "access": "read_write",
                            }
                        ],
                    }
                ],
            },
        }
        vm = {
            "mounts": [
                {
                    "name": "documents",
                    "dataset": "documents",
                    "protocol": "nfs",
                    "mount_point": "/mnt/nas/documents",
                    "access": "read_write",
                }
            ]
        }

        rendered = render_quadlet_service(service, vm, runtime_intent=quadlet_runtime_intent_fixture(service, vm))

        self.assert_golden_artifacts(rendered, GOLDEN_FIXTURES / "isolated_share_root")

    def test_golden_service_secret_injection_rendering(self):
        service = {
            "name": "paperless",
            "backend": {"vm": "media01", "port": 8000},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "web",
                        "image": "ghcr.io/paperless-ngx/paperless-ngx:2.13.5",
                        "env": {"PAPERLESS_URL": "https://paperless.fearn.cloud"},
                        "secrets": [
                            {
                                "secret": "secrets.admin_password",
                                "env": "PAPERLESS_ADMIN_PASSWORD_FILE",
                            }
                        ],
                    }
                ],
            },
        }

        rendered = render_quadlet_service(service, {}, runtime_intent=quadlet_runtime_intent_fixture(service))

        self.assert_golden_artifacts(rendered, GOLDEN_FIXTURES / "service_secret_injection")

    def test_golden_quadlet_fragment_merge(self):
        service = {
            "name": "immich",
            "backend": {"vm": "media01", "port": 2283},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                    }
                ],
            },
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fragment_dir = root / "inventory" / "services" / "immich.quadlet.d"
            fragment_dir.mkdir(parents=True)
            (fragment_dir / "network.network").write_text(
                "[Network]\nLabel=fortress.fragment=yes\n"
            )
            (fragment_dir / "server.container").write_text(
                "\n".join(
                    [
                        "[Unit]",
                        "StartLimitBurst=3",
                        "",
                        "[Container]",
                        "User=1000",
                        "",
                        "[Service]",
                        "RestartSec=10",
                        "",
                    ]
                )
            )

            rendered = render_quadlet_service(service, {}, inventory_root=root / "inventory", runtime_intent=quadlet_runtime_intent_fixture(service))

        self.assert_golden_artifacts(rendered, GOLDEN_FIXTURES / "with_fragments")

    def test_single_container_service_renders_rootful_quadlet_artifacts(self):
        service = {
            "name": "immich",
            "backend": {"vm": "media01", "port": 2283},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                        "published_ports": [
                            {
                                "bind": "127.0.0.1",
                                "host": 2283,
                                "container": 2283,
                                "protocol": "tcp",
                                "ingress": True,
                            }
                        ],
                    }
                ],
            },
        }

        rendered = render_quadlet_service(service, {}, runtime_intent=quadlet_runtime_intent_fixture(service))

        self.assertEqual(
            ["fortress-immich.network", "fortress-immich-server.container"],
            [artifact.filename for artifact in rendered.artifacts],
        )
        network, container = rendered.artifacts
        self.assertEqual("/etc/containers/systemd/fortress-immich.network", network.path)
        self.assertEqual(
            "\n".join(
                [
                    "[Network]",
                    "NetworkName=fortress-immich",
                    "",
                    "[Install]",
                    "WantedBy=multi-user.target",
                    "",
                ]
            ),
            network.content,
        )
        self.assertEqual("/etc/containers/systemd/fortress-immich-server.container", container.path)
        self.assertIn("ContainerName=fortress-immich-server\n", container.content)
        self.assertIn("Network=fortress-immich\n", container.content)
        self.assertIn("NetworkAlias=server\n", container.content)
        self.assertIn("PublishPort=127.0.0.1:2283:2283/tcp\n", container.content)
        self.assertNotIn("AutoUpdate", container.content)

    def test_tcp_udp_published_port_renders_separate_quadlet_ports(self):
        service = {
            "name": "dns-primary",
            "backend": {"vm": "dns-primary-vm", "port": 53},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "pihole",
                        "image": "docker.io/pihole/pihole:2025.05.0",
                        "published_ports": [
                            {
                                "bind": "0.0.0.0",
                                "host": 53,
                                "container": 53,
                                "protocol": "tcp_udp",
                            }
                        ],
                    }
                ],
            },
        }

        rendered = render_quadlet_service(service, {}, runtime_intent=quadlet_runtime_intent_fixture(service))
        container = rendered.artifacts_by_filename["fortress-dns-primary-pihole.container"]

        self.assertIn("PublishPort=0.0.0.0:53:53/tcp\n", container.content)
        self.assertIn("PublishPort=0.0.0.0:53:53/udp\n", container.content)
        self.assertNotIn("tcp,udp", container.content)

    def test_dns_pihole_services_receive_web_api_password_file_secret(self):
        services = ["dns-primary", "dns-secondary"]

        for service_name in services:
            with self.subTest(service=service_name):
                service = load_inventory_tree(REPO_ROOT).services[service_name]

                rendered = render_quadlet_service(service, {}, runtime_intent=quadlet_runtime_intent_fixture(service))
                container = rendered.artifacts_by_filename[f"fortress-{service_name}-pihole.container"]

                secret_name = f"fortress_{service_name}_web_api_password"
                self.assertIn(f"Secret={secret_name}\n", container.content)
                self.assertIn(
                    f"Environment=WEBPASSWORD_FILE={secret_name}\n",
                    container.content,
                )
                self.assertNotIn(
                    f"Environment=WEBPASSWORD_FILE=/run/secrets/{secret_name}\n",
                    container.content,
                )
                self.assertNotIn("created:", container.content)
                self.assertNotIn("version:", container.content)
                self.assertNotIn("value:", container.content)

    def test_dns_unbound_services_seed_empty_default_include_files(self):
        services = ["dns-primary", "dns-secondary"]

        for service_name in services:
            with self.subTest(service=service_name):
                service = load_inventory_tree(REPO_ROOT).services[service_name]

                rendered = render_quadlet_service(service, {}, runtime_intent=quadlet_runtime_intent_fixture(service))

                self.assertEqual(
                    [
                        (f"/srv/services/{service_name}/unbound/a-records.conf", "", 1000, 1000, "0644"),
                        (f"/srv/services/{service_name}/unbound/srv-records.conf", "", 1000, 1000, "0644"),
                        (f"/srv/services/{service_name}/unbound/forward-records.conf", "", 1000, 1000, "0644"),
                    ],
                    [
                        (file.path, file.content, file.uid, file.gid, file.mode)
                        for file in rendered.service_data_files
                    ],
                )

    def test_jellyfin_declares_render_node_without_replacing_runtime_user(self):
        model = load_inventory_tree(REPO_ROOT)

        rendered = render_quadlet_service(
            model.services["jellyfin"],
            model.vms["media-vm"],
            inventory_root=REPO_ROOT / "inventory",
            runtime_intent=quadlet_runtime_intent_fixture(
                model.services["jellyfin"],
                model.vms["media-vm"],
            ),
        )

        jellyfin = rendered.artifacts_by_filename["fortress-jellyfin-jellyfin.container"]
        self.assertIn("User=1001:1001\n", jellyfin.content)
        self.assertIn("AddDevice=/dev/dri\n", jellyfin.content)
        self.assertIn("GroupAdd=__FORTRESS_HOST_GROUP_GID_render__\n", jellyfin.content)

    def test_container_device_renders_add_device_and_host_group_marker(self):
        service = {
            "name": "jellyfin",
            "backend": {"vm": "media01", "port": 8096},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "docker.io/jellyfin/jellyfin:10.11.8",
                        "devices": [{"path": "/dev/dri", "host_group": "render"}],
                    }
                ],
            },
        }

        rendered = render_quadlet_service(service, {}, runtime_intent=quadlet_runtime_intent_fixture(service))
        container = rendered.artifacts_by_filename["fortress-jellyfin-server.container"]

        self.assertIn("AddDevice=/dev/dri\n", container.content)
        self.assertIn("GroupAdd=__FORTRESS_HOST_GROUP_GID_render__\n", container.content)

    def test_container_renders_non_secret_env_and_service_secret_file_env(self):
        service = {
            "name": "paperless",
            "backend": {"vm": "media01", "port": 8000},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "web",
                        "image": "ghcr.io/paperless-ngx/paperless-ngx:2.13.5",
                        "env": {
                            "PAPERLESS_URL": "https://paperless.fearn.cloud",
                            "PAPERLESS_ENABLE_HTTP_REMOTE_USER": True,
                        },
                        "secrets": [
                            {
                                "secret": "secrets.admin_password",
                                "env": "PAPERLESS_ADMIN_PASSWORD_FILE",
                            }
                        ],
                    }
                ],
            },
        }

        rendered = render_quadlet_service(service, {}, runtime_intent=quadlet_runtime_intent_fixture(service))

        container = rendered.artifacts_by_filename["fortress-paperless-web.container"]
        self.assertIn("Environment=PAPERLESS_URL=https://paperless.fearn.cloud\n", container.content)
        self.assertIn("Environment=PAPERLESS_ENABLE_HTTP_REMOTE_USER=true\n", container.content)
        self.assertIn("Secret=fortress_paperless_admin_password\n", container.content)
        self.assertIn(
            "Environment=PAPERLESS_ADMIN_PASSWORD_FILE=/run/secrets/fortress_paperless_admin_password\n",
            container.content,
        )
        self.assertNotIn("admin_password: ", container.content)

    def test_container_service_secret_lines_use_service_runtime_intent_when_provided(self):
        service = {
            "name": "paperless",
            "backend": {"vm": "media01", "port": 8000},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "web",
                        "image": "ghcr.io/paperless-ngx/paperless-ngx:2.13.5",
                        "secrets": [
                            {
                                "secret": "secrets.raw_yaml_password",
                                "env": "RAW_YAML_PASSWORD_FILE",
                            }
                        ],
                    }
                ],
            },
        }
        runtime_intent = replace(
            quadlet_runtime_intent_fixture(service),
            service_secrets=(
                ServiceSecretRuntimeFact(
                    service_name="paperless",
                    container_name="web",
                    container_index=0,
                    secret_index=0,
                    secret_key="admin_password",
                    podman_name="fortress_paperless_admin_password",
                    env="PAPERLESS_ADMIN_PASSWORD_FILE",
                    sops_extract='["secrets"]["admin_password"]["value"]',
                    env_value_mode="file_path",
                ),
            ),
        )

        rendered = render_quadlet_service(service, {}, runtime_intent=runtime_intent)

        container = rendered.artifacts_by_filename["fortress-paperless-web.container"]
        self.assertIn("Secret=fortress_paperless_admin_password\n", container.content)
        self.assertIn(
            "Environment=PAPERLESS_ADMIN_PASSWORD_FILE=/run/secrets/fortress_paperless_admin_password\n",
            container.content,
        )
        self.assertNotIn("raw_yaml_password", container.content)
        self.assertNotIn("RAW_YAML_PASSWORD_FILE", container.content)

    def test_quadlet_artifacts_use_service_runtime_identity_facts_when_provided(self):
        service = {
            "name": "raw-service",
            "backend": {"vm": "media01", "port": 8080},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "web",
                        "image": "docker.io/library/nginx:1.27",
                        "depends_on": ["db"],
                        "volumes": [
                            {
                                "service_path": "raw-data",
                                "container": "/data",
                            }
                        ],
                    },
                    {
                        "name": "db",
                        "image": "postgres:16",
                    },
                ],
            },
        }
        runtime_intent = ServiceRuntimeIntent(
            backends=(),
            published_ports=(),
            telemetry_targets=(),
            service_secrets=(),
            service_owned_volumes=(
                ServiceOwnedVolumeRuntimeFact(
                    service_name="raw-service",
                    vm_name="media01",
                    container_name="web",
                    container_index=0,
                    volume_index=0,
                    service_path="intent-data",
                    vm_path="/srv/runtime-intent/raw-service/intent-data",
                    container_path="/data",
                    access_mode="ro",
                ),
            ),
            service_data_directories=(),
            share_backed_volumes=(),
            native_environment_secrets=(),
            service_network_identities=(
                ServiceNetworkIdentityRuntimeFact(
                    service_name="raw-service",
                    vm_name="media01",
                    declared_service_network=None,
                    podman_name="intent-network",
                    isolated=True,
                ),
            ),
            container_identities=(
                ContainerIdentityRuntimeFact(
                    service_name="raw-service",
                    vm_name="media01",
                    container_name="web",
                    container_index=0,
                    container_alias="intent-web",
                    podman_name="intent-web-container",
                    systemd_unit_name="intent-web-container.service",
                    service_network_podman_name="intent-network",
                ),
                ContainerIdentityRuntimeFact(
                    service_name="raw-service",
                    vm_name="media01",
                    container_name="db",
                    container_index=1,
                    container_alias="intent-db",
                    podman_name="intent-db-container",
                    systemd_unit_name="intent-db-container.service",
                    service_network_podman_name="intent-network",
                ),
            ),
            service_unit_orders=(),
            diagnostics=(),
        )

        rendered = render_quadlet_service(service, {}, runtime_intent=runtime_intent)

        self.assertEqual(
            ["intent-network.network", "intent-web-container.container", "intent-db-container.container"],
            [artifact.filename for artifact in rendered.artifacts],
        )
        network = rendered.artifacts_by_filename["intent-network.network"]
        web = rendered.artifacts_by_filename["intent-web-container.container"]
        self.assertIn("NetworkName=intent-network\n", network.content)
        self.assertIn("ContainerName=intent-web-container\n", web.content)
        self.assertIn("Network=intent-network\n", web.content)
        self.assertIn("NetworkAlias=intent-web\n", web.content)
        self.assertIn("Requires=intent-db-container.service\n", web.content)
        self.assertIn("After=intent-db-container.service\n", web.content)
        self.assertIn("BindsTo=intent-db-container.service\n", web.content)
        self.assertIn("Volume=/srv/runtime-intent/raw-service/intent-data:/data:ro\n", web.content)
        self.assertNotIn("fortress-raw-service", web.content)
        self.assertNotIn("/srv/services/raw-service/raw-data", web.content)

    def test_container_dependencies_render_same_service_start_order_and_stop_coupling(self):
        service = {
            "name": "immich",
            "backend": {"vm": "media01", "port": 2283},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                        "depends_on": ["postgres"],
                    },
                    {
                        "name": "postgres",
                        "image": "postgres:16",
                    },
                ],
            },
        }

        rendered = render_quadlet_service(service, {}, runtime_intent=quadlet_runtime_intent_fixture(service))

        server = rendered.artifacts_by_filename["fortress-immich-server.container"]
        self.assertIn("Requires=fortress-immich-postgres.service\n", server.content)
        self.assertIn("After=fortress-immich-postgres.service\n", server.content)
        self.assertIn("BindsTo=fortress-immich-postgres.service\n", server.content)
        self.assertNotIn("health", server.content.lower())
        self.assertNotIn("ready", server.content.lower())

    def test_service_network_uses_shared_network_without_changing_container_identity(self):
        service = {
            "name": "immich",
            "service_group": "media-apps",
            "service_network": "media",
            "backend": {"vm": "media01", "port": 2283},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                    }
                ],
            },
        }

        rendered = render_quadlet_service(service, {}, runtime_intent=quadlet_runtime_intent_fixture(service))

        self.assertIn("fortress-network-media.network", rendered.artifacts_by_filename)
        network = rendered.artifacts_by_filename["fortress-network-media.network"]
        container = rendered.artifacts_by_filename["fortress-immich-server.container"]
        self.assertIn("NetworkName=fortress-network-media\n", network.content)
        self.assertIn("ContainerName=fortress-immich-server\n", container.content)
        self.assertIn("Network=fortress-network-media\n", container.content)
        self.assertIn("NetworkAlias=server\n", container.content)

    def test_service_group_without_service_network_keeps_isolated_network(self):
        service = {
            "name": "seerr",
            "service_group": "media-apps",
            "backend": {"vm": "media01", "port": 5055},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/seerr-team/seerr:v3.2.0",
                    }
                ],
            },
        }

        rendered = render_quadlet_service(service, {}, runtime_intent=quadlet_runtime_intent_fixture(service))

        self.assertIn("fortress-seerr.network", rendered.artifacts_by_filename)
        container = rendered.artifacts_by_filename["fortress-seerr-server.container"]
        self.assertIn("Network=fortress-seerr\n", container.content)
        self.assertNotIn("fortress-network-media-apps", container.content)

    def test_service_data_owner_applies_only_to_service_owned_volume_paths(self):
        service = {
            "name": "immich",
            "service_data_owner": {"uid": 1000, "gid": 1000},
            "backend": {"vm": "media01", "port": 2283},
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                        "volumes": [
                            {
                                "service_path": "upload",
                                "container": "/usr/src/app/upload",
                            },
                            {
                                "mount": "media",
                                "source": "photos",
                                "container": "/photos",
                            },
                        ],
                    }
                ],
            },
        }
        vm = {
            "mounts": [
                {
                    "name": "media",
                    "dataset": "media",
                    "protocol": "nfs",
                    "mount_point": "/mnt/nas/media",
                    "access": "read_write",
                }
            ]
        }

        rendered = render_quadlet_service(service, vm, runtime_intent=quadlet_runtime_intent_fixture(service, vm))

        self.assertEqual(
            [("/srv/services/immich/upload", 1000, 1000)],
            [
                (directory.path, directory.uid, directory.gid)
                for directory in rendered.service_data_directories
            ],
        )

    def test_share_backed_volume_orders_container_after_vm_mount_unit(self):
        service = {
            "name": "immich",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                        "volumes": [
                            {
                                "mount": "media",
                                "source": "photos",
                                "container": "/photos",
                                "access": "read_only",
                            }
                        ],
                    }
                ],
            },
        }
        vm = {
            "mounts": [
                {
                    "name": "media",
                    "dataset": "media",
                    "protocol": "nfs",
                    "mount_point": "/mnt/nas/media",
                    "access": "read_write",
                }
            ]
        }

        unit = render_quadlet_container(service, vm, service["deploy"]["containers"][0], runtime_intent=quadlet_runtime_intent_fixture(service, vm))

        self.assertIn("Requires=mnt-nas-media.mount", unit)
        self.assertIn("After=mnt-nas-media.mount", unit)
        self.assertIn("Volume=/mnt/nas/media/photos:/photos:ro", unit)

    def test_share_backed_volume_uses_systemd_escaped_mount_unit_name(self):
        service = {
            "name": "demo",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "web",
                        "image": "docker.io/library/nginx:1.27",
                        "volumes": [
                            {
                                "mount": "nfs-demo",
                                "source": "/",
                                "container": "/mnt/shared",
                                "access": "read_write",
                            }
                        ],
                    }
                ],
            },
        }
        vm = {
            "mounts": [
                {
                    "name": "nfs-demo",
                    "dataset": "acceptance-nfs-demo",
                    "protocol": "nfs",
                    "mount_point": "/mnt/nfs-demo",
                    "access": "read_write",
                }
            ]
        }

        unit = render_quadlet_container(service, vm, service["deploy"]["containers"][0], runtime_intent=quadlet_runtime_intent_fixture(service, vm))

        self.assertIn("Requires=mnt-nfs\\x2ddemo.mount", unit)
        self.assertIn("After=mnt-nfs\\x2ddemo.mount", unit)
        self.assertNotIn("mnt-nfs-demo.mount", unit)

    def test_share_backed_volume_lines_use_service_runtime_intent_when_provided(self):
        service = {
            "name": "media",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "web",
                        "image": "docker.io/library/nginx:1.27",
                        "volumes": [
                            {
                                "mount": "raw-media",
                                "source": "raw-photos",
                                "container": "/photos",
                                "access": "read_write",
                            }
                        ],
                    }
                ],
            },
        }
        vm = {
            "mounts": [
                {
                    "name": "raw-media",
                    "mount_point": "/mnt/raw-media",
                    "access": "read_write",
                }
            ]
        }
        runtime_intent = replace(
            quadlet_runtime_intent_fixture(service, vm),
            share_backed_volumes=(
                ShareBackedVolumeRuntimeFact(
                    service_name="media",
                    vm_name="media01",
                    container_name="web",
                    container_index=0,
                    volume_index=0,
                    mount_name="intent-media",
                    dataset_name="media",
                    vm_mount_path="/mnt/intent-media",
                    resolved_source_path="/mnt/intent-media/intent-photos",
                    container_path="/photos",
                    access="read_only",
                    required_mount_unit="mnt-intent\\x2dmedia.mount",
                ),
            ),
        )

        unit = render_quadlet_container(
            service,
            vm,
            service["deploy"]["containers"][0],
            runtime_intent=runtime_intent,
        )

        self.assertIn("Requires=mnt-intent\\x2dmedia.mount", unit)
        self.assertIn("After=mnt-intent\\x2dmedia.mount", unit)
        self.assertIn("Volume=/mnt/intent-media/intent-photos:/photos:ro", unit)
        self.assertNotIn("/mnt/raw-media/raw-photos", unit)

    def test_service_owned_volume_sources_are_relative_service_paths(self):
        service = {
            "name": "immich",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                        "volumes": [
                            {
                                "service_path": "upload",
                                "container": "/usr/src/app/upload",
                            }
                        ],
                    }
                ],
            },
        }

        unit = render_quadlet_container(service, {}, service["deploy"]["containers"][0], runtime_intent=quadlet_runtime_intent_fixture(service))

        self.assertIn("Volume=/srv/services/immich/upload:/usr/src/app/upload:rw", unit)

    def test_quadlet_fragment_merges_native_options_into_container_artifact(self):
        service = {
            "name": "immich",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                    }
                ],
            },
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fragment_dir = root / "inventory" / "services" / "immich.quadlet.d"
            fragment_dir.mkdir(parents=True)
            (fragment_dir / "server.container").write_text(
                "\n".join(
                    [
                        "[Unit]",
                        "StartLimitBurst=3",
                        "",
                        "[Container]",
                        "User=1000",
                        "",
                    ]
                )
            )

            rendered = render_quadlet_service(service, {}, inventory_root=root / "inventory", runtime_intent=quadlet_runtime_intent_fixture(service))

        container = rendered.artifacts_by_filename["fortress-immich-server.container"]
        self.assertIn("StartLimitBurst=3\n", container.content)
        self.assertIn("User=1000\n", container.content)

    def test_observability_mounts_generated_prometheus_config_and_uses_matching_service_data_user(self):
        model = load_inventory_tree(REPO_ROOT)
        rendered = render_quadlet_service(
            model.services["observability"],
            model.vms["observability-vm"],
            inventory_root=REPO_ROOT / "inventory",
            runtime_intent=quadlet_runtime_intent_fixture(
                model.services["observability"],
                model.vms["observability-vm"],
            ),
        )

        prometheus = rendered.artifacts_by_filename["fortress-observability-prometheus.container"]
        self.assertIn(
            "Volume=/srv/services/observability/prometheus-config:/etc/prometheus:ro\n",
            prometheus.content,
        )
        self.assertIn("User=1000:1000\n", prometheus.content)
        for name in ("alertmanager", "grafana", "loki", "blackbox"):
            artifact = rendered.artifacts_by_filename[f"fortress-observability-{name}.container"]
            self.assertIn("User=1000:1000\n", artifact.content)
        self.assertIn(
            "/srv/services/observability/prometheus-config",
            [directory.path for directory in rendered.service_data_directories],
        )

    def test_observability_mounts_generated_grafana_provisioning_and_dashboards(self):
        model = load_inventory_tree(REPO_ROOT)
        rendered = render_quadlet_service(
            model.services["observability"],
            model.vms["observability-vm"],
            inventory_root=REPO_ROOT / "inventory",
            runtime_intent=quadlet_runtime_intent_fixture(
                model.services["observability"],
                model.vms["observability-vm"],
            ),
        )

        grafana = rendered.artifacts_by_filename["fortress-observability-grafana.container"]
        self.assertIn(
            "Volume=/srv/services/observability/grafana-provisioning:"
            "/etc/grafana/provisioning:ro\n",
            grafana.content,
        )
        self.assertIn(
            "Volume=/srv/services/observability/grafana-dashboards/generated:"
            "/var/lib/grafana/dashboards/fortress-generated:ro\n",
            grafana.content,
        )
        directories = {
            directory.path: directory
            for directory in rendered.service_data_directories
        }
        for path in (
            "/srv/services/observability/grafana-provisioning",
            "/srv/services/observability/grafana-dashboards/generated",
        ):
            self.assertIn(path, directories)
            self.assertEqual(1000, directories[path].uid)
            self.assertEqual(1000, directories[path].gid)

    def test_quadlet_fragment_rejects_unknown_fragment_filename(self):
        service = {
            "name": "immich",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                    }
                ],
            },
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fragment_dir = root / "inventory" / "services" / "immich.quadlet.d"
            fragment_dir.mkdir(parents=True)
            (fragment_dir / "stale.container").write_text("[Container]\nUser=1000\n")

            with self.assertRaisesRegex(ValueError, "unknown Quadlet Fragment.*stale.container"):
                render_quadlet_service(service, {}, inventory_root=root / "inventory", runtime_intent=quadlet_runtime_intent_fixture(service))

    def test_quadlet_fragment_rejects_invalid_ini_syntax(self):
        service = {
            "name": "immich",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                    }
                ],
            },
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fragment_dir = root / "inventory" / "services" / "immich.quadlet.d"
            fragment_dir.mkdir(parents=True)
            (fragment_dir / "server.container").write_text("User=1000\n")

            with self.assertRaisesRegex(ValueError, "invalid Quadlet Fragment INI syntax"):
                render_quadlet_service(service, {}, inventory_root=root / "inventory", runtime_intent=quadlet_runtime_intent_fixture(service))

    def test_quadlet_fragment_rejects_fortress_owned_generated_key(self):
        service = {
            "name": "immich",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                    }
                ],
            },
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fragment_dir = root / "inventory" / "services" / "immich.quadlet.d"
            fragment_dir.mkdir(parents=True)
            (fragment_dir / "server.container").write_text("[Container]\nImage=postgres:16\n")

            with self.assertRaisesRegex(ValueError, "fortress-owned key: Container.Image"):
                render_quadlet_service(service, {}, inventory_root=root / "inventory", runtime_intent=quadlet_runtime_intent_fixture(service))

    def test_quadlet_fragment_rejects_reserved_install_update_and_secret_keys(self):
        service = {
            "name": "immich",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                    }
                ],
            },
        }

        forbidden_fragments = {
            "AutoUpdate=registry": "[Container]\nAutoUpdate=registry\n",
            "Secret=db_password": "[Container]\nSecret=db_password\n",
            "WantedBy=default.target": "[Install]\nWantedBy=default.target\n",
        }
        for label, fragment in forbidden_fragments.items():
            with self.subTest(fragment=label), TemporaryDirectory() as tmp:
                root = Path(tmp)
                fragment_dir = root / "inventory" / "services" / "immich.quadlet.d"
                fragment_dir.mkdir(parents=True)
                (fragment_dir / "server.container").write_text(fragment)

                with self.assertRaisesRegex(ValueError, "reserved fortress-owned key"):
                    render_quadlet_service(service, {}, inventory_root=root / "inventory", runtime_intent=quadlet_runtime_intent_fixture(service))

    def test_quadlet_fragment_adds_repeated_unit_dependencies_without_replacing_generated_ones(self):
        service = {
            "name": "immich",
            "deploy": {
                "type": "quadlet",
                "containers": [
                    {
                        "name": "server",
                        "image": "ghcr.io/immich-app/immich-server:v1.120.0",
                        "depends_on": ["postgres"],
                    },
                    {
                        "name": "postgres",
                        "image": "postgres:16",
                    },
                ],
            },
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fragment_dir = root / "inventory" / "services" / "immich.quadlet.d"
            fragment_dir.mkdir(parents=True)
            (fragment_dir / "server.container").write_text(
                "[Unit]\nRequires=network-online.target\nAfter=network-online.target\n"
            )

            rendered = render_quadlet_service(service, {}, inventory_root=root / "inventory", runtime_intent=quadlet_runtime_intent_fixture(service))

        container = rendered.artifacts_by_filename["fortress-immich-server.container"]
        self.assertIn(
            "Requires=fortress-immich-postgres.service network-online.target\n",
            container.content,
        )
        self.assertIn(
            "After=fortress-immich-postgres.service network-online.target\n",
            container.content,
        )

    def assert_golden_artifacts(self, rendered, fixture_dir):
        expected_files = sorted(path.name for path in fixture_dir.iterdir())
        self.assertEqual(expected_files, sorted(artifact.filename for artifact in rendered.artifacts))
        for artifact in rendered.artifacts:
            with self.subTest(golden=artifact.filename):
                self.assertEqual((fixture_dir / artifact.filename).read_text(), artifact.content)


if __name__ == "__main__":
    unittest.main()
