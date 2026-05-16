from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fortress_inventory.model import load_inventory_tree
from fortress_workflows.runner import CommandPhase, FailurePolicy, OperatorWorkflowPlan, WorkflowResult


HOST_CONFIGURE_TAGS = [
    "proxmox_repos",
    "system_hygiene",
    "proxmox_network",
    "proxmox_users",
    "gpu_passthrough",
]


@dataclass(frozen=True)
class HostReadinessPlan:
    plan: OperatorWorkflowPlan
    bootstrap_summary: str


class HostReadinessPlanError(Exception):
    pass


def build_host_readiness_plan(
    repo_root: Path,
    host_name: str,
    endpoint_arg: str,
    auto_confirm: bool,
    keep_on_fail: bool,
) -> HostReadinessPlan:
    inventory = load_inventory_tree(repo_root)
    host = inventory.hosts.get(host_name)
    if host is None:
        raise HostReadinessPlanError(
            f"Host {host_name!r} is not declared at {repo_root / 'inventory' / 'hosts' / f'{host_name}.yaml'}"
        )

    templates = host.get("proxmox", {}).get("templates", []) or []
    if not templates:
        raise HostReadinessPlanError(f"Host {host_name} declares no Templates under proxmox.templates")
    for template in templates:
        if template not in inventory.templates:
            raise HostReadinessPlanError(
                f"Host {host_name} references missing Template {template} at "
                f"{repo_root / 'inventory' / 'templates' / f'{template}.yaml'}"
            )

    if endpoint_arg == "all":
        endpoints = sorted(inventory.nas_endpoints)
    else:
        if endpoint_arg not in inventory.nas_endpoints:
            raise HostReadinessPlanError(
                f"NAS Endpoint {endpoint_arg!r} is not declared at "
                f"{repo_root / 'inventory' / 'nas' / f'{endpoint_arg}.yaml'}"
            )
        endpoints = [endpoint_arg]

    steps = []
    host_sops = repo_root / "inventory" / "hosts" / f"{host_name}.sops.yaml"
    if host_sops.is_file():
        steps.append(
            CommandPhase(
                id="bootstrap-satisfied",
                display_name="Bootstrap Satisfied",
                command=[
                    "bash",
                    "-c",
                    _bootstrap_sops_probe_script(),
                    "bootstrap-satisfied",
                    str(host_sops),
                ],
                diagnostic_label="bootstrap",
            )
        )
        bootstrap_summary = "bootstrap: satisfied"
    else:
        steps.append(
            CommandPhase(
                id="bootstrap",
                display_name="Bootstrap",
                command=[str(repo_root / "scripts" / "host-bootstrap"), host_name],
                diagnostic_label="bootstrap",
                streaming=True,
            )
        )
        bootstrap_summary = "bootstrap: ran"

    steps.extend(
        [
            CommandPhase(
                id="host-shell",
                display_name="Host Reachability",
                command=[str(repo_root / "scripts" / "host-shell"), host_name, "--", "true"],
                diagnostic_label="host-shell",
                streaming=True,
            ),
            CommandPhase(
                id="configure",
                display_name="Host Configure",
                command=[
                    str(repo_root / "scripts" / "host-configure"),
                    host_name,
                    ",".join(HOST_CONFIGURE_TAGS),
                ],
                diagnostic_label="configure",
                streaming=True,
            ),
            CommandPhase(
                id="templates-build",
                display_name="Template Build",
                command=[str(repo_root / "scripts" / "templates-build"), host_name],
                diagnostic_label="templates-build",
                streaming=True,
            ),
        ]
    )

    for template in templates:
        steps.append(
            CommandPhase(
                id=f"template-verify {template}",
                display_name=f"Template Verification {template}",
                command=[
                    str(repo_root / "scripts" / "template-verify"),
                    f"host={host_name}",
                    f"template={template}",
                    f"keep_on_fail={bool_arg(keep_on_fail)}",
                ],
                diagnostic_label=f"template-verify {template}",
                streaming=True,
            )
        )

    acceptance_failure_policy = FailurePolicy.STOP if keep_on_fail else FailurePolicy.CONTINUE
    for endpoint in endpoints:
        for template in templates:
            for workflow, script_name in [
                ("nfs-shared-mount", "acceptance-nfs-shared-mount"),
                ("service-layer", "acceptance-service-layer"),
            ]:
                label = f"acceptance {workflow} {template}@{endpoint}"
                command = [
                    str(repo_root / "scripts" / script_name),
                    f"host={host_name}",
                    f"template={template}",
                    f"endpoint={endpoint}",
                    f"auto_confirm={bool_arg(auto_confirm)}",
                    f"keep_on_fail={bool_arg(keep_on_fail)}",
                ]
                steps.append(
                    CommandPhase(
                        id=label,
                        display_name=label,
                        command=acceptance_command(repo_root, workflow, command, cleanup_on_failure=not keep_on_fail),
                        diagnostic_label=label,
                        streaming=True,
                        failure_policy=acceptance_failure_policy,
                    )
                )

    return HostReadinessPlan(
        plan=OperatorWorkflowPlan(id=f"host-readiness {host_name}", steps=steps),
        bootstrap_summary=bootstrap_summary,
    )


def render_host_readiness_summary(resolved: HostReadinessPlan, result: WorkflowResult) -> list[str]:
    lines = []
    phase_by_id = {phase.step_id: phase for phase in result.phase_results}
    if "bootstrap-satisfied" in phase_by_id or "bootstrap" in phase_by_id:
        bootstrap_phase = phase_by_id.get("bootstrap-satisfied") or phase_by_id["bootstrap"]
        lines.append(resolved.bootstrap_summary if bootstrap_phase.status == "passed" else "bootstrap: failed")

    for phase in result.phase_results:
        if phase.step_id in ("bootstrap", "bootstrap-satisfied"):
            continue
        lines.append(f"{phase.step_id}: {phase.status}")

    lines.append(f"host-readiness: {'passed' if result.success else 'failed'}")
    return lines


def bool_arg(value: bool) -> str:
    return "true" if value else "false"


def acceptance_command(
    repo_root: Path,
    workflow: str,
    command: list[str],
    cleanup_on_failure: bool,
) -> list[str]:
    if not cleanup_on_failure:
        return command
    return [
        "bash",
        "-c",
        _acceptance_cleanup_wrapper_script(),
        "acceptance-with-cleanup",
        command[0],
        str(repo_root / "scripts" / "acceptance-clean-generated-artifacts"),
        workflow,
        *command[1:],
    ]


def _acceptance_cleanup_wrapper_script() -> str:
    return (
        'acceptance_script="$1"\n'
        'cleanup_script="$2"\n'
        'workflow="$3"\n'
        "shift 3\n"
        '"$acceptance_script" "$@"\n'
        "status=$?\n"
        'if [ "$status" -ne 0 ]; then\n'
        '  "$cleanup_script" "workflow=$workflow" "auto_confirm=true"\n'
        "fi\n"
        'exit "$status"\n'
    )


def _bootstrap_sops_probe_script() -> str:
    return (
        'host_sops="$1"\n'
        'private_key="$(sops --decrypt --extract \'["ssh_keys"]["bootstrap"]["private_key"]\' "$host_sops")"\n'
        "status=$?\n"
        "if [ $status -ne 0 ]; then\n"
        '  echo "Host Sibling SOPS File $host_sops does not expose ssh_keys.bootstrap.private_key" >&2\n'
        "  exit $status\n"
        "fi\n"
        'if [ -z "${private_key//[[:space:]]/}" ]; then\n'
        '  echo "Host Sibling SOPS File $host_sops exposes an empty ssh_keys.bootstrap.private_key" >&2\n'
        "  exit 1\n"
        "fi\n"
    )
