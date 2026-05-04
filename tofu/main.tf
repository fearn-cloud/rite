terraform {
  required_version = ">= 1.8.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.105"
    }
  }
}

variable "selected_vm" {
  type        = string
  default     = null
  description = "Optional VM name to plan or apply while preserving the single fleet state root."
}

locals {
  vm_files = fileset("../inventory/vms", "*.yaml")
  vms = {
    for path in local.vm_files :
    trimsuffix(basename(path), ".yaml") => yamldecode(file("../inventory/vms/${path}"))
    if !startswith(basename(path), "_")
  }
  template_files = fileset("../inventory/templates", "*.yaml")
  templates = {
    for path in local.template_files :
    trimsuffix(basename(path), ".yaml") => yamldecode(file("../inventory/templates/${path}"))
    if !startswith(basename(path), "_")
  }
  selected_vms = var.selected_vm == null ? local.vms : {
    (var.selected_vm) = local.vms[var.selected_vm]
  }
}
