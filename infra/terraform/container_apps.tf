# ── Log Analytics workspace (required by Container Apps) ──────────────────

resource "azurerm_log_analytics_workspace" "ctf" {
  name                = "${var.prefix}-ctf-logs"
  resource_group_name = local.ctf_rg.name
  location            = local.ctf_rg.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# ── Container Apps environment ────────────────────────────────────────────

resource "azurerm_container_app_environment" "ctf" {
  name                       = "${var.prefix}-ctf-env"
  resource_group_name        = local.ctf_rg.name
  location                   = local.ctf_rg.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.ctf.id
}

# ── API Container App ─────────────────────────────────────────────────────
# Ingress is INTERNAL only — the API is not exposed to the public internet.
# The frontend nginx proxies /api and /ws to http://ctf-api using ACA's
# internal DNS. Traffic never leaves the Container Apps environment.

resource "azurerm_container_app" "api" {
  name                         = "${var.prefix}-ctf-api"
  resource_group_name          = local.ctf_rg.name
  container_app_environment_id = azurerm_container_app_environment.ctf.id
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [data.azurerm_user_assigned_identity.app_id.id]
  }

  registry {
    server   = var.acr_login_server
    identity = data.azurerm_user_assigned_identity.app_id.id
  }

  secret {
    name  = "db-url"
    value = "postgresql+asyncpg://${var.db_admin_user}:${var.db_admin_password}@${azurerm_postgresql_flexible_server.ctf.fqdn}:5432/${var.db_name}"
  }
  secret {
    name  = "secret-key"
    value = random_password.api_secret_key.result
  }
  secret {
    name  = "flex-tokens"
    value = var.flex_tokens
  }
  secret {
    name  = "prober-secret"
    value = random_password.prober_secret.result
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name   = "ctf-api"
      image  = var.api_image
      cpu    = 1.0
      memory = "2Gi"

      env {
        name  = "ENVIRONMENT"
        value = "production"
      }
      env {
        name  = "AZURE_STUDENT_PASSWORD"
        value = var.azure_student_password
      }
      env {
        name  = "GRAPH_CLIENT_ID"
        value = var.graph_client_id
      }
      env {
        name  = "AZURE_TENANT_ID"
        value = var.azure_tenant_id
      }
      # Azure infrastructure settings for live ARM API calls
      env {
        name  = "AZURE_SUBSCRIPTION_ID"
        value = var.azure_subscription_id
      }
      env {
        name  = "VWAN_NAME"
        value = var.vwan_name
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
      env {
        name  = "FMG_SERIAL"
        value = var.fmg_serial
      }
      env {
        name  = "FMG_IP"
        value = var.fmg_ip
      }
      env {
        name        = "PROBER_SECRET"
        secret_name = "prober-secret"
      }
      # Sensitive: FortiFlex tokens JSON stored as a Container Apps secret
      env {
        name        = "FLEX_TOKENS"
        secret_name = "flex-tokens"
      }
      # CORS origin is the frontend's public FQDN — derived from the
      # environment default domain which is known at plan time.
      env {
        name  = "CORS_ORIGINS"
        value = "https://ctf-frontend.${azurerm_container_app_environment.ctf.default_domain}"
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "db-url"
      }
      env {
        name        = "SECRET_KEY"
        secret_name = "secret-key"
      }
    }
  }

  ingress {
    # Internal only — reachable as http://ctf-api from within the same
    # ACA environment; not accessible from the public internet.
    external_enabled = false
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].container[0].image, # Allow updating the container image without triggering a full replacement
    ]
  }
}
/*
resource "azurerm_role_assignment" "api_acr_pull" {
  scope                = var.acr_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_container_app.api.identity[0].principal_id
}

# Reader on the subscription — required for ARM API calls from the API container:
# - GET /providers/Microsoft.Network/virtualHubs            (subscription-wide)
# - GET /providers/Microsoft.Network/networkVirtualAppliances (subscription-wide)
# - GET /resourceGroups/<student-rg>/providers/Microsoft.Network/... (per-team RGs)
# - GET /resourceGroups/<branches-rg>/providers/Microsoft.Network/... (branch RG)
# All queries span multiple resource groups so subscription-level Reader is needed.
resource "azurerm_role_assignment" "api_subscription_reader" {
  scope                = data.azurerm_subscription.current.id
  role_definition_name = "Reader"
  principal_id         = azurerm_container_app.api.identity[0].principal_id
}
*/
# ── Frontend Container App ────────────────────────────────────────────────
# Public-facing. nginx proxies /api and /ws to the API using ACA internal DNS.

resource "azurerm_container_app" "frontend" {
  name                         = "${var.prefix}-ctf-frontend"
  resource_group_name          = local.ctf_rg.name
  container_app_environment_id = azurerm_container_app_environment.ctf.id
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [data.azurerm_user_assigned_identity.app_id.id]
  }

  registry {
    server   = var.acr_login_server
    identity = data.azurerm_user_assigned_identity.app_id.id
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name   = "ctf-frontend"
      image  = var.frontend_image
      cpu    = 0.5
      memory = "1Gi"

      # ACA internal DNS: http://<app-name> resolves within the same environment.
      # envsubst in the container entrypoint substitutes this into nginx.conf.
      # Full internal FQDN required for ACA inter-app communication.
      # Format: <app-name>.internal.<env-unique-id>.<region>.azurecontainerapps.io
      # Traffic stays within the ACA environment and never hits the public internet.
      env {
        name  = "API_URL"
        value = "https://ctf-api.internal.${azurerm_container_app_environment.ctf.default_domain}"
      }
      env {
        name  = "API_HOST"
        value = "ctf-api.internal.${azurerm_container_app_environment.ctf.default_domain}"
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 80
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].container[0].image, # Allow updating the container image without triggering a full replacement
    ]
  }
}
/*
resource "azurerm_role_assignment" "frontend_acr_pull" {
  scope                = var.acr_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_container_app.frontend.identity[0].principal_id
}
*/
