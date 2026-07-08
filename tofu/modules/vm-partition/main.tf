terraform {
  required_providers {
    proxmox = {
      source = "bpg/proxmox"
    }
  }
}

variable "host_name" {
  type = string
}

variable "pve_node_name" {
  type = string
}

variable "admin_user" {
  type = string
}

variable "templates" {
  type = map(any)
}

variable "vms" {
  type = any
}

locals {
  vm_names = sort(keys(var.vms))
  vm_network_interfaces = {
    for vm_name, vm in var.vms : vm_name => (
      length(try(vm.network.interfaces, [])) == 0 ? [
        {
          address = "dhcp"
          bridge  = "vmbr0"
          gateway = null
          model   = "virtio"
          secondary_addresses = []
          vlan    = null
        }
        ] : [
        for interface in vm.network.interfaces : {
          address             = try(interface.address, "dhcp")
          bridge              = interface.bridge
          gateway             = try(interface.gateway, null)
          model               = try(interface.model, "virtio")
          secondary_addresses = try(interface.secondary_addresses, [])
          vlan                = try(interface.vlan, null)
        }
      ]
    )
  }
  vm_cloud_init_interfaces = {
    for vm_name, vm in var.vms : vm_name => "scsi${max(1, length(try(vm.hardware.disks, [])))}"
  }
  vm_pci_device_mappings = {
    for item in flatten([
      for vm_name, vm in var.vms : [
        for index, pci_device in try(vm.hardware.pci_devices, []) : {
          key              = "${vm_name}-${index}"
          name             = pci_device.mapping_name
          path             = pci_device.host_address
          pci_id           = pci_device.pci_id
          comment          = try(pci_device.mapping_comment, "Managed by fortress for VM ${vm_name}")
          iommu_group      = try(pci_device.iommu_group, null)
          mediated_devices = try(pci_device.mediated_devices, false)
          subsystem_id     = try(pci_device.subsystem_id, null)
        } if try(pci_device.mapping_name, null) != null
      ]
    ]) : item.key => item
  }
}

resource "proxmox_hardware_mapping_pci" "pci" {
  for_each = local.vm_pci_device_mappings

  name             = each.value.name
  comment          = each.value.comment
  mediated_devices = each.value.mediated_devices

  map = [
    {
      comment      = each.value.comment
      id           = each.value.pci_id
      iommu_group  = each.value.iommu_group
      node         = var.pve_node_name
      path         = each.value.path
      subsystem_id = each.value.subsystem_id
    }
  ]
}

resource "proxmox_virtual_environment_file" "cloud_init_user_data" {
  for_each = var.vms

  content_type = "snippets"
  datastore_id = "local"
  node_name    = var.pve_node_name

  source_raw {
    file_name = "${each.key}-user-data.yaml"
    data      = <<-EOF
      #cloud-config
      hostname: ${each.value.cloud_init.hostname}
      manage_etc_hosts: true
      users:
        - name: ${var.admin_user}
          groups: sudo
          shell: /bin/bash
          sudo: ALL=(ALL) NOPASSWD:ALL
          ssh_authorized_keys:
            - ${trimspace(each.value.ssh_public_key)}
      write_files:
        - path: /etc/fortress-network-intent.yaml
          permissions: "0644"
          content: |
            ${indent(12, yamlencode({ interfaces = local.vm_network_interfaces[each.key] }))}
      EOF
  }

  lifecycle {
    precondition {
      condition     = try(length(trimspace(each.value.ssh_public_key)) > 0, false)
      error_message = "missing VM plaintext SSH public key for VM ${each.key}; run Prepare first."
    }
  }
}

resource "proxmox_virtual_environment_vm" "vm" {
  for_each = var.vms

  name      = each.value.cloud_init.hostname
  node_name = var.pve_node_name
  vm_id     = each.value.vmid

  clone {
    vm_id = var.templates[each.value.source.template].vmid
  }

  cpu {
    cores = each.value.hardware.cores
  }

  memory {
    dedicated = each.value.hardware.memory
  }

  initialization {
    interface         = local.vm_cloud_init_interfaces[each.key]
    user_data_file_id = proxmox_virtual_environment_file.cloud_init_user_data[each.key].id

    dynamic "ip_config" {
      for_each = local.vm_network_interfaces[each.key]

      content {
        ipv4 {
          address = ip_config.value.address
          gateway = ip_config.value.gateway
        }
      }
    }
  }

  dynamic "disk" {
    for_each = try(each.value.hardware.disks, [])

    content {
      datastore_id = disk.value.storage
      interface    = "scsi${disk.key}"
      size         = tonumber(trimsuffix(disk.value.size, "G"))
    }
  }

  dynamic "network_device" {
    for_each = local.vm_network_interfaces[each.key]

    content {
      bridge  = network_device.value.bridge
      model   = network_device.value.model
      vlan_id = network_device.value.vlan
    }
  }

  dynamic "hostpci" {
    for_each = try(each.value.hardware.pci_devices, [])

    content {
      device  = "hostpci${hostpci.key}"
      id      = try(hostpci.value.mapping_name, null) == null ? hostpci.value.host_address : null
      mapping = try(hostpci.value.mapping_name, null)
      pcie    = hostpci.value.pcie
      rombar  = hostpci.value.rombar
      xvga    = hostpci.value.primary_gpu
    }
  }

  depends_on = [proxmox_hardware_mapping_pci.pci]

  lifecycle {
    precondition {
      condition     = startswith(local.vm_cloud_init_interfaces[each.key], "scsi")
      error_message = "cloud-init must attach through SCSI so q35/OVMF Debian guests can see the first-boot datasource."
    }
  }
}

output "vm_names" {
  value = local.vm_names
}
