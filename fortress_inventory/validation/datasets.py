from .errors import ValidationError


def validate_dataset_names(model):
    errors = []
    seen = {}
    for dataset_file, dataset in model.datasets.items():
        dataset_name = dataset.get("name")
        if not dataset_name:
            continue
        if dataset_name in seen:
            errors.append(
                ValidationError(
                    "duplicate_dataset_name",
                    f"inventory/datasets/{dataset_file}.yaml.name",
                    f"Datasets {seen[dataset_name]} and {dataset_file} both declare name {dataset_name}",
                )
            )
        else:
            seen[dataset_name] = dataset_file
    return errors


def validate_dataset_nas_refs(model):
    errors = []
    endpoints = set(model.nas_endpoints.keys())
    for dataset_file, dataset in model.datasets.items():
        nas_name = dataset.get("nas")
        if nas_name and nas_name not in endpoints:
            errors.append(
                ValidationError(
                    "missing_dataset_nas_endpoint",
                    f"inventory/datasets/{dataset_file}.yaml.nas",
                    f"Dataset {dataset.get('name', dataset_file)} references missing NAS endpoint {nas_name}",
                )
            )
    return errors


def validate_dataset_lifecycle_policy(model, allow_ephemeral_datasets=False):
    errors = []
    if allow_ephemeral_datasets:
        return errors
    acceptance_dataset_names = {
        policy.get("dataset")
        for policy in model.acceptance_policies.values()
        if policy.get("dataset")
    }
    for dataset_file, dataset in model.datasets.items():
        if dataset.get("lifecycle") == "ephemeral" and dataset.get("name") not in acceptance_dataset_names:
            errors.append(
                ValidationError(
                    "ordinary_ephemeral_dataset",
                    f"inventory/datasets/{dataset_file}.yaml.lifecycle",
                    f"Dataset {dataset.get('name', dataset_file)} uses ephemeral lifecycle outside Acceptance Test inventory",
                )
            )
    return errors
