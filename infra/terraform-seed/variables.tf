variable "prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "vwanlab"
}

variable "location" {
  description = "Azure region. France Central for lower probability of capacity problems"
  type        = string
  default     = "francecentral"
}

variable "rg_name" {
  description = "Name of an existing resource group to use. If null, a new one will be created."
  type        = string
  default     = "vwanlab-infra"
}

variable "acr_name" {
  type        = string
  description = "Name of ACR for hosting container images"
  default     = "vwanlab"
}

# ── OIDC / GitHub Actions ─────────────────────────────────────────────────

variable "github_org" {
  description = "GitHub organisation or user that owns the repository."
  type        = string
  default     = "bartekmo"
}

variable "github_repo" {
  description = "GitHub repository name hosting actions (without org prefix)."
  type        = string
  default     = "ftnt-ctf-vwan"
}

variable "tfc_project_name" {
  type        = string
  description = "Name of the project in HCL Terraform"
  default     = "vwanlab"
}

variable "tfc_org_name" {
  type        = string
  description = "Name of the organization in HCL Terraform"
  default     = "40net"
}

variable "ctf_workspace_name" {
  type        = string
  description = "Name of the Terraform Cloud workspace for the CTF environment"
  default     = "vwanlab-ctf"
}
