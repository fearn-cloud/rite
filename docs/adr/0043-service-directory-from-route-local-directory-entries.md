# Service Directory is generated from route-local Directory Entries

The Service Directory is generated from route-local Directory Entries declared on existing Service, Host, and NAS ingress routes, rather than maintained as hand-written Homepage configuration. Service Deploy owns the stable `service-directory` Homepage installation, while Directory Regeneration owns the generated Homepage configuration, mirroring the Ingress Regeneration split between stable ingress scaffolding and generated route/DNS artifacts. This keeps ingress route declarations as the source of truth for destinations while allowing each route to opt into operator navigation with only presentation intent.

