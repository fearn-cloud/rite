# Declare the forgejo-mcp Service

Status: done
Category: enhancement

## What to build

Declare `forgejo-mcp` as a new Rite Service on `forgejo-vm` using the upstream `goern/forgejo-mcp` container image pinned to an immutable release tag. The Service should run streamable HTTP transport and point at Forgejo through `https://git.fearn.cloud`.

The container must not receive `FORGEJO_ACCESS_TOKEN`, `--token`, or any other global Forgejo token. The intended runtime mode is per-request client tokens supplied through HTTP `Authorization` headers.

## Acceptance criteria

- [x] Inventory declares a `forgejo-mcp` Service whose Backend VM is `forgejo-vm`.
- [x] The Service image is pinned to an immutable `goern/forgejo-mcp` release tag, not `latest`.
- [x] The Service starts `goern/forgejo-mcp` in streamable HTTP mode, equivalent to `--transport http --http-port <port>`.
- [x] The upstream Forgejo URL is configured as `https://git.fearn.cloud`.
- [x] The Service exposes one VM-local Published Port for the MCP HTTP endpoint.
- [x] The expected client endpoint is documented as `/mcp` on that Published Port.
- [x] The Service definition does not include a global Forgejo access token.
- [x] Inventory schema/validation/tests pass for the new Service.

## Blocked by

None - can start immediately

## Comments

- 2026-07-13: Declared `inventory/services/forgejo-mcp.yaml` with the immutable `codeberg.org/goern/forgejo-mcp:v2.30.2` image, streamable HTTP on VM port 8080, and `https://git.fearn.cloud` as its upstream. The definition has no global Forgejo token. `python3 -m fortress_inventory.validate_inventory .` and `python3 -m unittest` pass. The standalone `check_jsonschema` invocation is unavailable locally because the `check_jsonschema` module is not installed.
