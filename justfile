set positional-arguments

default:
    @just --list

test:
    python3 -m unittest discover -s tests
    pre-commit run --all-files

host-bootstrap host:
    @./scripts/host-bootstrap {{host}}

host-configure host tags="":
    @./scripts/host-configure {{host}} "{{tags}}"

vm-up vm:
    @./scripts/vm-up {{vm}}

vm-configure vm:
    @./scripts/vm-configure {{vm}}

vm-destroy vm delete_vm_yaml="false":
    @if [ "{{delete_vm_yaml}}" = "true" ] || [ "{{delete_vm_yaml}}" = "delete_vm_yaml=true" ]; then ./scripts/vm-destroy {{vm}} --delete-vm-yaml; else ./scripts/vm-destroy {{vm}}; fi

service-deploy service:
    @echo "TODO: deploy Service {{service}}"

templates-build host:
    @./scripts/templates-build {{host}}

template-verify host template keep_on_fail="false":
    @./scripts/template-verify host={{host}} template={{template}} keep_on_fail={{keep_on_fail}}

ingress-regenerate:
    @echo "TODO: regenerate Ingress configuration"
