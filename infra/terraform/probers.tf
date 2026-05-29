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

  name                         = "ctf-probers"
  resource_group_name          = data.azurerm_resource_group.ctf.name
  location                     = data.azurerm_resource_group.ctf.location
  container_app_environment_id = azurerm_container_app_environment.ctf.id

  identity {
    type = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.app_id.id]
  }

  registry {
    server   = azurerm_container_registry.ctf.login_server
    identity = azurerm_user_assigned_identity.app_id.id
  }

  replica_timeout_in_seconds = 120
  replica_retry_limit        = 0

  schedule_trigger_config {
    cron_expression          = "* * * * *"
    parallelism              = 1
    replica_completion_count = 1
  }

  dynamic "secret" {
    for_each = var.prober_api_token != "" ? [1] : []
    content {
      name  = "ctf-api-token"
      value = var.prober_api_token
    }
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
        name  = "CTF_API_URL"
        value = "https://ctf-api.internal.${azurerm_container_app_environment.ctf.default_domain}"
      }
      dynamic "env" {
        for_each = var.prober_api_token != "" ? [1] : []
        content {
          name        = "CTF_API_TOKEN"
          secret_name = "ctf-api-token"
        }
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

  depends_on = [
    azurerm_role_assignment.app_id_acr_pull,
    azurerm_role_assignment.app_id_subscription_reader,
  ]
}

# Grant the prober job's managed identity Reader on the subscription.
# Only created when the job exists.
resource "azurerm_role_assignment" "app_id_acr_pull" {
  #scope                = "/subscriptions/${var.azure_subscription_id}"
  #role_definition_name = "Reader"
  scope                = azurerm_container_registry.ctf.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.app_id.principal_id
}

resource "azurerm_role_assignment" "app_id_subscription_reader" {
  scope                = data.azurerm_subscription.current.id
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.app_id.principal_id
}
