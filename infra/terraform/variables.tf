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
  default     = "B_Standard_B1ms"
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

# ── Azure infrastructure (for live ARM API calls from the API container) ──

variable "azure_subscription_id" {
  description = "Azure subscription ID. The API container uses this with its managed identity to call ARM."
  type        = string
  default     = ""
}

variable "vwan_name" {
  description = "Name of the Azure Virtual WAN resource."
  type        = string
  default     = ""
}

variable "rg_prefix" {
  description = "Prefix for per-student resource group names, e.g. 'vwanlab-student-'."
  type        = string
  default     = "vwanlab-student-"
}

variable "rg_suffix" {
  description = "Suffix for per-student resource group names (often empty)."
  type        = string
  default     = ""
}

variable "rg_branches" {
  description = "Resource group containing shared branch site resources."
  type        = string
  default     = ""
}

variable "flex_tokens" {
  description = <<-EOT
    FortiFlex token data as a JSON string. Format:
    {"hubs": [null, ["token-a", "token-b"], ["token-c", "token-d"], ...]}
    Index 0 is unused; index N corresponds to team env_id N.
  EOT
  type      = string
  sensitive = true
  default   = "{\"hubs\": []}"
}

variable "fmg_serial" {
  description = "FortiManager serial number (shared across all teams)."
  type        = string
  default     = ""
}

variable "fmg_ip" {
  description = "FortiManager IP address or FQDN (shared across all teams)."
  type        = string
  default     = ""
}

variable "azure_student_password" {
  description = "Shared password for all student Azure accounts (vwanlab01@..., vwanlab02@..., etc.)"
  type        = string
  default     = "StudentPassword123!"
}

# ── Probers ───────────────────────────────────────────────────────────────

variable "probers_image" {
  description = "Full image reference for the probers container, e.g. xperts26ctf.azurecr.io/ctf-probers:latest"
  type        = string
  default     = ""
}

variable "prober_api_token" {
  description = <<-EOT
    Long-lived trainer-role JWT for probers to authenticate to the CTF API.
    Generate after first deploy:
      curl -X POST https://<api-fqdn>/api/auth/login \
        -d '{"username":"trainer","password":"<pw"}' | jq -r .access_token
  EOT
  type      = string
  sensitive = true
  default   = ""
}
