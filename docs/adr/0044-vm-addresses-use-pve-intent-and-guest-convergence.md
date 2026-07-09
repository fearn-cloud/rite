# VM addresses use PVE intent and guest convergence

VM interface addresses are declared once in Inventory, then projected into both PVE/cloud-init provisioning intent and guest-side VM Configure convergence. PVE/OpenTofu owns the virtual NIC, VLAN, and first-boot network intent for new or rebuilt VMs, while VM Configure owns making an already-running guest persistently match declared primary and Secondary VM Addresses; relying on PVE cloud-init metadata alone would leave live VMs vulnerable to drift until rebuild or reboot.
