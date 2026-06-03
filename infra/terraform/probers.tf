# ── Prober Container App Job ───────────────────────────────────────────────
#
# Runs as an ACA Job with a per-minute cron schedule.
# Uses system-assigned managed identity for ARM API access (same as ctf-api).
# Calls the CTF API internally via http://ctf-api (ACA internal DNS).
#
# The job is only created when probers_image is set — on first apply
# (before the image is built and pushed) set probers_image = "" and the
# resource is skipped. Set it after the first image push and re-apply.

locals {
  probers_enabled = var.probers_image != ""
}

resource "azurerm_container_app_job" "probers" {
  count = local.probers_enabled ? 1 : 0

  name                         = "${var.prefix}-ctf-probers"
  resource_group_name          = local.ctf_rg.name
  location                     = local.ctf_rg.location
  container_app_environment_id = azurerm_container_app_environment.ctf.id

  identity {
    type         = "UserAssigned"
    identity_ids = [data.azurerm_user_assigned_identity.app_id.id]
  }

  registry {
    server   = var.acr_login_server
    identity = data.azurerm_user_assigned_identity.app_id.id
  }

  replica_timeout_in_seconds = 120
  replica_retry_limit        = 0

  schedule_trigger_config {
    cron_expression          = "* * * * *"
    parallelism              = 1
    replica_completion_count = 1
  }

  secret {
    name  = "prober-secret"
    value = random_password.prober_secret.result
  }

  template {
    container {
      name   = "probers"
      image  = var.probers_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "PYTHONPATH"
        value = "/app"
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = data.azurerm_user_assigned_identity.app_id.client_id
      }
      env {
        name  = "FGT_FIRMWARE_VERSION"
        value = var.fgt_firmware_version
      }
      env {
        name  = "FMG_IP"
        value = var.fmg_ip
      }
      env {
        name  = "FMG_USER"
        value = var.fmg_user
      }
      env {
        name  = "FMG_PASSWORD"
        value = var.fmg_password
      }
      env {
        name  = "CTF_API_URL"
        value = "https://ctf-api.internal.${azurerm_container_app_environment.ctf.default_domain}"
      }
      env {
        name        = "PROBER_SECRET"
        secret_name = "prober-secret"
      }
      env {
        name  = "AZURE_SUBSCRIPTION_ID"
        value = var.azure_subscription_id
      }
      env {
        name  = "RG_PREFIX"
        value = var.rg_prefix
      }
      env {
        name  = "RG_SUFFIX"
        value = var.rg_suffix
      }
      env {
        name  = "RG_BRANCHES"
        value = var.rg_branches
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].container[0].image, # Allow updating the container image without triggering a full replacement
    ]
  }
}

