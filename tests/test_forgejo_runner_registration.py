import json
import re
import unittest
from pathlib import Path

from fortress_inventory.forgejo_runner_registration import (
    ObservedForgejoRunnerRegistration,
    desired_forgejo_runner_registrations,
    plan_forgejo_runner_registrations,
    render_forgejo_runner_convergence_script,
    render_forgejo_runner_registration_command,
    render_forgejo_runner_state_file,
)
from fortress_inventory.model import load_inventory_tree


REPO_ROOT = Path(__file__).resolve().parents[1]


class ForgejoRunnerRegistrationTests(unittest.TestCase):
    def test_registration_identity_is_derived_from_vm_runtime_intent(self):
        model = load_inventory_tree(REPO_ROOT)

        registration = desired_forgejo_runner_registrations(model)[0]

        self.assertEqual("forgejo-runner-vm", registration.vm_name)
        self.assertEqual("forgejo", registration.forgejo_service)
        self.assertEqual("fortress-forgejo-runner-vm", registration.name)
        self.assertEqual("instance", registration.scope)
        self.assertEqual("", registration.cli_scope)
        self.assertEqual("https://git.fearn.cloud/", registration.url)
        self.assertEqual(("debian-13:docker://debian:13",), registration.labels)
        self.assertRegex(registration.secret_identifier, r"^[0-9a-f]{16}$")
        self.assertRegex(registration.secret_token, r"^[0-9a-f]{40}$")
        self.assertTrue(registration.secret_token.startswith(registration.secret_identifier))
        self.assertEqual("forgejo-vm", registration.forgejo_backend_vm)

    def test_registration_plan_is_idempotent_when_observed_runner_matches_declared_state(self):
        model = load_inventory_tree(REPO_ROOT)
        registration = desired_forgejo_runner_registrations(model)[0]

        plan = plan_forgejo_runner_registrations(
            model,
            observed=[
                ObservedForgejoRunnerRegistration(
                    id=101,
                    uuid="11111111-1111-1111-1111-111111111111",
                    name=registration.name,
                    scope=registration.scope,
                    labels=registration.labels,
                    active=True,
                )
            ],
        )

        self.assertEqual((), plan.actions)

    def test_registration_plan_refreshes_labels_without_creating_duplicate_runner(self):
        model = load_inventory_tree(REPO_ROOT)
        registration = desired_forgejo_runner_registrations(model)[0]

        plan = plan_forgejo_runner_registrations(
            model,
            observed=[
                ObservedForgejoRunnerRegistration(
                    id=101,
                    uuid="11111111-1111-1111-1111-111111111111",
                    name=registration.name,
                    scope=registration.scope,
                    labels=("ubuntu-latest:docker://node:20",),
                    active=True,
                )
            ],
        )

        self.assertEqual(["refresh"], [action.action for action in plan.actions])
        self.assertIn("labels differ", plan.actions[0].reason)

    def test_registration_plan_disables_duplicate_active_runners_for_declared_identity(self):
        model = load_inventory_tree(REPO_ROOT)
        registration = desired_forgejo_runner_registrations(model)[0]

        plan = plan_forgejo_runner_registrations(
            model,
            observed=[
                ObservedForgejoRunnerRegistration(
                    id=101,
                    uuid="11111111-1111-1111-1111-111111111111",
                    name=registration.name,
                    scope=registration.scope,
                    labels=registration.labels,
                    active=True,
                ),
                ObservedForgejoRunnerRegistration(
                    id=102,
                    uuid="22222222-2222-2222-2222-222222222222",
                    name=registration.name,
                    scope=registration.scope,
                    labels=registration.labels,
                    active=True,
                ),
            ],
        )

        self.assertEqual(["disable_duplicate"], [action.action for action in plan.actions])
        self.assertEqual(102, plan.actions[0].observed.id)

    def test_registration_rendering_uses_idempotent_forgejo_cli_with_declared_labels(self):
        model = load_inventory_tree(REPO_ROOT)
        registration = desired_forgejo_runner_registrations(model)[0]

        command = render_forgejo_runner_registration_command(
            registration,
            secret_file="/run/fortress/forgejo-runner.secret",
        )

        self.assertEqual(
            (
                "forgejo forgejo-cli actions register --name fortress-forgejo-runner-vm "
                "--scope '' --labels debian-13:docker://debian:13 "
                "--secret-file /run/fortress/forgejo-runner.secret"
            ),
            command,
        )

    def test_registration_rendering_writes_runner_state_file_from_registered_uuid_and_token(self):
        model = load_inventory_tree(REPO_ROOT)
        registration = desired_forgejo_runner_registrations(model)[0]

        content = render_forgejo_runner_state_file(
            registration,
            uuid="33333333-3333-3333-3333-333333333333",
            token="0123456789abcdef0123456789abcdef01234567",
        )

        payload = json.loads(content)
        self.assertEqual("fortress-forgejo-runner-vm", payload["name"])
        self.assertEqual("https://git.fearn.cloud/", payload["address"])
        self.assertEqual("33333333-3333-3333-3333-333333333333", payload["uuid"])
        self.assertEqual("0123456789abcdef0123456789abcdef01234567", payload["token"])
        self.assertEqual(["debian-13:docker://debian:13"], payload["labels"])
        self.assertIn("automatically generated by forgejo-runner", payload["WARNING"])

    def test_convergence_script_registers_and_renders_runner_state_in_one_rebuildable_step(self):
        model = load_inventory_tree(REPO_ROOT)
        registration = desired_forgejo_runner_registrations(model)[0]

        script = render_forgejo_runner_convergence_script(
            registration,
            secret_file="/run/fortress/forgejo-runner.secret",
            runner_state_file="/var/lib/forgejo-runner/.runner",
        )

        self.assertIn("forgejo forgejo-cli actions register", script)
        self.assertIn(f"beginning with {registration.secret_identifier}", script)
        self.assertIn("--labels debian-13:docker://debian:13", script)
        self.assertIn("--secret-file /run/fortress/forgejo-runner.secret", script)
        self.assertIn("/var/lib/forgejo-runner/.runner", script)
        self.assertRegex(script, re.escape('"labels": ["debian-13:docker://debian:13"]'))


if __name__ == "__main__":
    unittest.main()
