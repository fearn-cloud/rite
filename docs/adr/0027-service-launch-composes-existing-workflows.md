# Service Launch composes existing workflows

Service Launch is a first-class operator workflow, but it is a wrapper over existing workflow commands rather than a separate deployment engine. It always delegates Backend VM readiness to VM Lifecycle Convergence, delegates runtime artifact convergence to Service Deploy, and runs Ingress Regeneration only for Services that declare Ingress; Host readiness, NAS readiness, and Ingress infrastructure readiness remain explicit prerequisites so launching one Service does not hide broader infrastructure mutation.
