set positional-arguments

default:
    @just --list

test:
    pre-commit run --all-files

host-bootstrap host:
    @./scripts/host-bootstrap {{host}}

host-configure host tags="":
    @./scripts/host-configure {{host}} "{{tags}}"

vm-up vm auto_confirm="false":
    @if [ "{{auto_confirm}}" = "true" ] || [ "{{auto_confirm}}" = "auto_confirm=true" ]; then ./scripts/vm-up {{vm}} --auto-confirm; else ./scripts/vm-up {{vm}}; fi

vm-configure vm:
    @./scripts/vm-configure {{vm}}

vm-shell vm:
    @./scripts/vm-shell {{vm}}

vm-destroy vm delete_vm_yaml="false":
    @if [ "{{delete_vm_yaml}}" = "true" ] || [ "{{delete_vm_yaml}}" = "delete_vm_yaml=true" ]; then ./scripts/vm-destroy {{vm}} --delete-vm-yaml; else ./scripts/vm-destroy {{vm}}; fi

service-deploy service:
    @./scripts/service-deploy {{service}}

nas-reconcile-plan reality_json:
    @./scripts/nas-reconcile-plan --reality-json {{reality_json}}

nas-reconcile reality_json confirm_disruptive_mount_changes="false":
    @if [ "{{confirm_disruptive_mount_changes}}" = "true" ] || [ "{{confirm_disruptive_mount_changes}}" = "confirm_disruptive_mount_changes=true" ]; then ./scripts/nas-reconcile-plan --reality-json {{reality_json}} --apply --confirm-disruptive-mount-changes; else ./scripts/nas-reconcile-plan --reality-json {{reality_json}} --apply; fi

nas-reconcile-live-plan endpoint:
    @./scripts/nas-reconcile-plan --live {{endpoint}}

nas-reconcile-live endpoint confirm_disruptive_mount_changes="false":
    @if [ "{{confirm_disruptive_mount_changes}}" = "true" ] || [ "{{confirm_disruptive_mount_changes}}" = "confirm_disruptive_mount_changes=true" ]; then ./scripts/nas-reconcile-plan --live {{endpoint}} --apply --confirm-disruptive-mount-changes; else ./scripts/nas-reconcile-plan --live {{endpoint}} --apply; fi

templates-build host:
    @./scripts/templates-build {{host}}

template-verify host template keep_on_fail="false":
    @./scripts/template-verify host={{host}} template={{template}} keep_on_fail={{keep_on_fail}}

acceptance-nfs-shared-mount host template endpoint auto_confirm="false" keep_on_fail="false":
    @host="{{host}}"; template="{{template}}"; endpoint="{{endpoint}}"; auto_confirm="{{auto_confirm}}"; keep_on_fail="{{keep_on_fail}}"; ./scripts/acceptance-nfs-shared-mount host="${host#host=}" template="${template#template=}" endpoint="${endpoint#endpoint=}" auto_confirm="${auto_confirm#auto_confirm=}" keep_on_fail="${keep_on_fail#keep_on_fail=}"

acceptance-service-layer host template endpoint auto_confirm="false" keep_on_fail="false":
    @host="{{host}}"; template="{{template}}"; endpoint="{{endpoint}}"; auto_confirm="{{auto_confirm}}"; keep_on_fail="{{keep_on_fail}}"; ./scripts/acceptance-service-layer host="${host#host=}" template="${template#template=}" endpoint="${endpoint#endpoint=}" auto_confirm="${auto_confirm#auto_confirm=}" keep_on_fail="${keep_on_fail#keep_on_fail=}"

acceptance-clean-generated-artifacts workflow auto_confirm="false":
    @workflow="{{workflow}}"; auto_confirm="{{auto_confirm}}"; ./scripts/acceptance-clean-generated-artifacts workflow=${workflow#workflow=} auto_confirm=${auto_confirm#auto_confirm=}

template-destroy host template delete_template_yaml="false":
    @if [ "{{delete_template_yaml}}" = "true" ] || [ "{{delete_template_yaml}}" = "delete_template_yaml=true" ]; then ./scripts/template-destroy {{host}} {{template}} --delete-template-yaml; else ./scripts/template-destroy {{host}} {{template}}; fi

ingress-regenerate:
    @echo "TODO: regenerate Ingress configuration"
