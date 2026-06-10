# ── Prober Container App Job ───────────────────────────────────────────────
#
# Runs as an ACA Job with a per-minute cron schedule.
# Uses system-assigned managed identity for ARM API access (same as ctf-api).
# Calls the CTF API internally via http://ctf-api (ACA internal DNS).
#
# The job is only created when probers_image is set — on first apply
# (before the image is built and pushed) set probers_image = "" and the
# resource is skipped. Set it after the first image push and re-apply.


resource "azurerm_container_app_job" "autopromoter" {
  name                         = "${var.prefix}-autopromoter"
  resource_group_name          = local.ctf_rg.name
  location                     = local.ctf_rg.location
  container_app_environment_id = azurerm_container_app_environment.ctf.id

  identity {
    type         = "UserAssigned"
    identity_ids = [data.azurerm_user_assigned_identity.app_id.id]
  }
  /*
  registry {
    server   = var.acr_login_server
    identity = data.azurerm_user_assigned_identity.app_id.id
  }
*/
  replica_timeout_in_seconds = 300
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
      name   = "autopromoter"
      image  = "ghcr.io/bartekmo/ftnt-xperts23-vwan/autopromoter:1.0.8"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "FMG_ADDRESS"
        value = var.fmg_ip
      }

    }
  }

  lifecycle {
    ignore_changes = [
      template[0].container[0].image, # Allow updating the container image without triggering a full replacement
    ]
  }
}

