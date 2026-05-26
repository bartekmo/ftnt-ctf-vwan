variable "resource_group_name" {
  description = "Name of the Azure resource group to deploy into."
  type        = string
  default     = "rg-xperts26-ctf"
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "westeurope"
}

# ── ACR ───────────────────────────────────────────────────────────────────

variable "acr_name" {
  description = "Azure Container Registry name. Must be globally unique, lowercase, alphanumeric only."
  type        = string
  default     = "xperts26ctf"
}

# ── PostgreSQL ────────────────────────────────────────────────────────────

variable "db_server_name" {
  description = "PostgreSQL Flexible Server name. Must be globally unique."
  type        = string
  default     = "ctf-pg-xperts26"
}

variable "db_admin_user" {
  description = "PostgreSQL administrator username."
  type        = string
  default     = "ctfadmin"
}

variable "db_admin_password" {
  description = "PostgreSQL administrator password."
  type        = string
  sensitive   = true
}

variable "db_name" {
  description = "Name of the application database."
  type        = string
  default     = "ctfdb"
}

variable "db_sku" {
  description = "PostgreSQL Flexible Server SKU."
  type        = string
  default     = "Standard_B1ms"
}

# ── Container Apps ────────────────────────────────────────────────────────

variable "api_image" {
  description = "Full image reference for the API container, e.g. xperts26ctf.azurecr.io/ctf-api:latest"
  type        = string
}

variable "frontend_image" {
  description = "Full image reference for the frontend container, e.g. xperts26ctf.azurecr.io/ctf-frontend:latest"
  type        = string
}

variable "api_secret_key" {
  description = "JWT secret key for the API. Generate with: openssl rand -hex 32"
  type        = string
  sensitive   = true
}

# ── OIDC / GitHub Actions ─────────────────────────────────────────────────

variable "github_org" {
  description = "GitHub organisation or user that owns the repository."
  type        = string
  default     = "bartekmo"
}

variable "github_repo" {
  description = "GitHub repository name (without org prefix)."
  type        = string
  default     = "ftnt-ctf-vwan"
}
