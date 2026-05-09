import unittest

from fortress_services.quadlet import render_quadlet_container


class ServiceQuadletRenderingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
