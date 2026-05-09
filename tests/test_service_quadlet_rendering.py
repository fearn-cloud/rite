import unittest
from pathlib import Path

from fortress_services.quadlet import render_quadlet_container, render_quadlet_service


REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "quadlet_rendering"


class ServiceQuadletRenderingTests(unittest.TestCase):
    def test_golden_service_group_multi_container_rendering(self):
        service = {
            "name": "immich",
            "service_group": "media",
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

        rendered = render_quadlet_service(service, vm)

        self.assert_golden_artifacts(rendered, GOLDEN_FIXTURES / "service_group_multi")
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

        rendered = render_quadlet_service(service, vm)

        self.assert_golden_artifacts(rendered, GOLDEN_FIXTURES / "isolated_share_root")

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

        rendered = render_quadlet_service(service, {})

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

        rendered = render_quadlet_service(service, {})

        server = rendered.artifacts_by_filename["fortress-immich-server.container"]
        self.assertIn("Requires=fortress-immich-postgres.service\n", server.content)
        self.assertIn("After=fortress-immich-postgres.service\n", server.content)
        self.assertIn("BindsTo=fortress-immich-postgres.service\n", server.content)
        self.assertNotIn("health", server.content.lower())
        self.assertNotIn("ready", server.content.lower())

    def test_service_group_uses_shared_network_without_changing_container_identity(self):
        service = {
            "name": "immich",
            "service_group": "media",
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

        rendered = render_quadlet_service(service, {})

        self.assertIn("fortress-group-media.network", rendered.artifacts_by_filename)
        network = rendered.artifacts_by_filename["fortress-group-media.network"]
        container = rendered.artifacts_by_filename["fortress-immich-server.container"]
        self.assertIn("NetworkName=fortress-group-media\n", network.content)
        self.assertIn("ContainerName=fortress-immich-server\n", container.content)
        self.assertIn("Network=fortress-group-media\n", container.content)
        self.assertIn("NetworkAlias=server\n", container.content)

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

        rendered = render_quadlet_service(service, vm)

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

        unit = render_quadlet_container(service, vm, service["deploy"]["containers"][0])

        self.assertIn("Requires=mnt-nas-media.mount", unit)
        self.assertIn("After=mnt-nas-media.mount", unit)
        self.assertIn("Volume=/mnt/nas/media/photos:/photos:ro", unit)

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

        unit = render_quadlet_container(service, {}, service["deploy"]["containers"][0])

        self.assertIn("Volume=/srv/services/immich/upload:/usr/src/app/upload:rw", unit)

    def assert_golden_artifacts(self, rendered, fixture_dir):
        expected_files = sorted(path.name for path in fixture_dir.iterdir())
        self.assertEqual(expected_files, sorted(artifact.filename for artifact in rendered.artifacts))
        for artifact in rendered.artifacts:
            with self.subTest(golden=artifact.filename):
                self.assertEqual((fixture_dir / artifact.filename).read_text(), artifact.content)


if __name__ == "__main__":
    unittest.main()
