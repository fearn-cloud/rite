set positional-arguments

default:
    @just --list

host-bootstrap host:
    @./scripts/host-bootstrap {{host}}

host-configure host tags="":
    @./scripts/host-configure {{host}} "{{tags}}"

vm-up vm:
    @echo "TODO: prepare, apply, and configure VM {{vm}}"

vm-destroy vm:
    @echo "TODO: destroy VM {{vm}}"

service-deploy service:
    @echo "TODO: deploy Service {{service}}"

templates-build host:
    @echo "TODO: build Templates for Host {{host}}"

ingress-regenerate:
    @echo "TODO: regenerate Ingress configuration"
