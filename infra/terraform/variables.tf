variable "resource_group_name" {
  description = "Name of the Azure resource group to deploy into. null means the module will create its own resource group."
  type        = string
  default     = null
  nullable    = true
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "westeurope"
}

variable "prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "vwanlab"
}

# ── ACR ───────────────────────────────────────────────────────────────────


# ── PostgreSQL ────────────────────────────────────────────────────────────

variable "db_server_name" {
  description = "PostgreSQL Flexible Server name. Must be globally unique."
  type        = string
  default     = "vwanlab-pg-xperts26"
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
  default     = "ctf-api:latest"
}

variable "frontend_image" {
  description = "Full image reference for the frontend container, e.g. xperts26ctf.azurecr.io/ctf-frontend:latest"
  type        = string
  default     = "ctf-frontend:latest"
}

variable "probers_image" {
  description = "Full image reference for the probers container, e.g. xperts26ctf.azurecr.io/ctf-probers:latest"
  type        = string
  default     = "ctf-probers:latest"
}


# ── Azure infrastructure (for live ARM API calls from the API container) ──


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
  type        = string
  sensitive   = true
  default     = "{\"hubs\": []}"
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


variable "fgt_firmware_version" {
  description = "Expected FortiGate firmware version on hub NVAs. Probers warn if the actual version differs."
  type        = string
  default     = "7.6.6"
}

variable "fmg_user" {
  description = "FortiManager API username for prober authentication"
  type        = string
  default     = ""
}

variable "fmg_password" {
  description = "FortiManager API password for prober authentication"
  type        = string
  sensitive   = true
  default     = ""
}

# ── TAP / Microsoft Graph ─────────────────────────────────────────────────

variable "graph_client_id" {
  description = <<-EOT
    Client ID of the user-assigned managed identity used for Graph API calls.
    This identity needs UserAuthenticationMethod.ReadWrite.All scoped to the
    vwanlab Administrative Unit (not the full tenant).
    Assign the Graph app role via PowerShell — see README.
    Leave empty to disable the TAP feature.
  EOT
  type        = string
  default     = ""
}

variable "azure_tenant_id" {
  description = "Entra tenant ID (used for Graph token acquisition)"
  type        = string
  default     = ""
}


variable "acr_id" {
  description = "Resource ID of the Azure Container Registry (ACR) where container images are stored. Output from the infra/terraform-seed module."
  type        = string
}

variable "acr_login_server" {
  description = "Login server URL of the Azure Container Registry (ACR), e.g. xperts26ctf.azurecr.io. Output from the infra/terraform-seed module."
  type        = string
}

variable "acr_name" {
  description = "Name of the Azure Container Registry (ACR). Output from the infra/terraform-seed module."
  type        = string
  default     = ""
}

variable "app_id_name" {
  description = "Name of the user-assigned managed identity used by the container apps and jobs. Output from the infra/terraform-seed module."
  type        = string
}

variable "app_config_endpoint" {
  description = "Endpoint URL of the Azure App Configuration instance. Output from the infra/terraform-seed module."
  type        = string
}
