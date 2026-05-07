from dataclasses import dataclass


@dataclass(frozen=True)
class NasReality:
    datasets: dict
    nfs_shares: list


def load_reality(data):
    datasets = {
        dataset.get("path"): dataset
        for dataset in data.get("datasets", []) or []
        if dataset.get("path")
    }
    return NasReality(datasets=datasets, nfs_shares=data.get("nfs_shares", []) or [])


def build_nas_reconcile_plan(inventory, reality):
    dataset_findings = []
    for dataset in sorted(inventory.datasets.values(), key=lambda item: item.get("name", "")):
        if dataset.get("lifecycle", "adopted") != "adopted":
            continue
        dataset_name = dataset.get("name")
        dataset_path = dataset.get("path")
        actual_dataset = reality.datasets.get(dataset_path)
        if not actual_dataset:
            dataset_findings.append(
                {
                    "code": "missing_dataset",
                    "dataset": dataset_name,
                    "path": dataset_path,
                    "message": f"Adopted Dataset {dataset_name} is missing at {dataset_path}",
                }
            )
            continue

        expected_owner = dataset.get("owner")
        actual_owner = actual_dataset.get("owner")
        if expected_owner and actual_owner != expected_owner:
            expected_uid = expected_owner.get("uid")
            expected_gid = expected_owner.get("gid")
            actual_uid = actual_owner.get("uid") if actual_owner else None
            actual_gid = actual_owner.get("gid") if actual_owner else None
            dataset_findings.append(
                {
                    "code": "dataset_owner_drift",
                    "dataset": dataset_name,
                    "path": dataset_path,
                    "expected": expected_owner,
                    "actual": actual_owner,
                    "message": (
                        f"Adopted Dataset {dataset_name} root owner is {actual_uid}:{actual_gid}, "
                        f"expected {expected_uid}:{expected_gid}"
                    ),
                }
            )

    desired_nfs_shares = derive_desired_nfs_shares(inventory)
    share_findings = _share_findings(desired_nfs_shares, reality.nfs_shares)
    blocking_codes = {"unmanaged_share_overlap"}

    return {
        "read_only": True,
        "blocked": bool(dataset_findings)
        or any(finding["code"] in blocking_codes for finding in share_findings),
        "write_actions": [],
        "connection": _redacted_connection(inventory),
        "dataset_findings": dataset_findings,
        "desired_nfs_shares": desired_nfs_shares,
        "share_findings": share_findings,
    }


def derive_desired_nfs_shares(inventory):
    datasets_by_name = {
        dataset.get("name"): dataset
        for dataset in inventory.datasets.values()
        if dataset.get("name")
    }
    grouped = {}
    for vm in inventory.vms.values():
        clients = _vm_static_addresses(vm)
        for mount in vm.get("mounts", []) or []:
            if mount.get("protocol") != "nfs":
                continue
            dataset_name = mount.get("dataset")
            dataset = datasets_by_name.get(dataset_name)
            if not dataset:
                continue
            key = (dataset_name, dataset.get("path"), mount.get("protocol"), mount.get("access"))
            grouped.setdefault(key, set()).update(clients)

    desired = []
    for (dataset_name, path, protocol, access), clients in sorted(grouped.items()):
        desired.append(
            {
                "name": f"fortress-{protocol}-{dataset_name}-{access.replace('_', '-')}",
                "dataset": dataset_name,
                "path": path,
                "protocol": protocol,
                "access": access,
                "clients": sorted(clients),
            }
        )
    return desired


def _share_findings(desired_nfs_shares, existing_nfs_shares):
    existing_by_name = {share.get("name"): share for share in existing_nfs_shares}
    desired_names = {share["name"] for share in desired_nfs_shares}
    findings = []
    for desired in desired_nfs_shares:
        if desired["name"] not in existing_by_name:
            findings.append(
                {
                    "code": "missing_share",
                    "share": desired["name"],
                    "dataset": desired["dataset"],
                    "path": desired["path"],
                    "message": f"Desired NFS Share {desired['name']} is missing",
                }
            )
    for share in sorted(existing_nfs_shares, key=lambda item: item.get("name", "")):
        if share.get("fortress_owned") is True and share.get("name") not in desired_names:
            findings.append(
                {
                    "code": "stale_fortress_owned_share",
                    "share": share.get("name"),
                    "path": share.get("path"),
                    "message": f"Fortress-owned NFS Share {share.get('name')} is no longer desired",
                }
            )
    for share in sorted(existing_nfs_shares, key=lambda item: item.get("name", "")):
        if _is_fortress_owned_share(share):
            continue
        for desired in desired_nfs_shares:
            if _paths_overlap(share.get("path"), desired["path"]):
                findings.append(
                    {
                        "code": "unmanaged_share_overlap",
                        "share": share.get("name"),
                        "dataset": desired["dataset"],
                        "path": share.get("path"),
                        "message": (
                            f"Unmanaged NFS Share {share.get('name')} overlaps desired Dataset "
                            f"{desired['dataset']}"
                        ),
                    }
                )
    return findings


def _is_fortress_owned_share(share):
    return share.get("fortress_owned") is True


def _paths_overlap(existing_path, desired_path):
    if not existing_path or not desired_path:
        return False
    return existing_path == desired_path or existing_path.startswith(f"{desired_path}/")


def _vm_static_addresses(vm):
    addresses = []
    for interface in vm.get("network", {}).get("interfaces", []) or []:
        address = interface.get("address")
        if address:
            addresses.append(address.split("/", 1)[0])
    return addresses


def _redacted_connection(inventory):
    endpoints = inventory.globals.get("nas", {}).get("endpoints", {}) or {}
    redacted = {}
    for name, endpoint in sorted(endpoints.items()):
        visible = {}
        has_secret = False
        for key, value in endpoint.items():
            if key.endswith("_env"):
                visible[key] = value
            elif "token" in key or "secret" in key or "password" in key:
                has_secret = True
            else:
                visible[key] = value
        if has_secret:
            visible["credentials"] = "redacted"
        redacted[name] = visible
    return redacted
