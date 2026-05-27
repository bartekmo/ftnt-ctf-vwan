# ── Log Analytics workspace (required by Container Apps) ──────────────────

resource "azurerm_log_analytics_workspace" "ctf" {
  name                = "ctf-logs"
  resource_group_name = data.azurerm_resource_group.ctf.name
  location            = data.azurerm_resource_group.ctf.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# ── Container Apps environment ────────────────────────────────────────────

resource "azurerm_container_app_environment" "ctf" {
  name                       = "ctf-env"
  resource_group_name        = data.azurerm_resource_group.ctf.name
  location                   = data.azurerm_resource_group.ctf.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.ctf.id
}

# ── API Container App ─────────────────────────────────────────────────────

resource "azurerm_container_app" "api" {
  name                         = "ctf-api"
  resource_group_name          = data.azurerm_resource_group.ctf.name
  container_app_environment_id = azurerm_container_app_environment.ctf.id
  revision_mode                = "Single"

  # System-assigned managed identity — used to pull from ACR at runtime
  identity {
    type = "SystemAssigned"
  }

  # Pull image from ACR using the managed identity (no stored registry creds)
  registry {
    server   = azurerm_container_registry.ctf.login_server
    identity = "system"
  }

  # Sensitive values are stored as Container Apps secrets (encrypted at rest)
  # and referenced by env vars — never passed as plain env vars
  secret {
    name  = "db-url"
    value = "postgresql+asyncpg://${var.db_admin_user}:${var.db_admin_password}@${azurerm_postgresql_flexible_server.ctf.fqdn}:5432/${var.db_name}"
  }
  secret {
    name  = "secret-key"
    value = var.api_secret_key
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
      # CORS is set after frontend FQDN is known — see outputs.tf for the value
      env {
        name  = "CORS_ORIGINS"
        value = "https://ctf-frontend.${azurerm_container_app_environment.ctf.default_domain}" #"https://${azurerm_container_app.frontend.ingress[0].fqdn}"
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
    external_enabled = false
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  # Depends on frontend so CORS FQDN is available; see note in outputs.tf
  depends_on = [azurerm_container_app.frontend]
}

# Grant the API's managed identity AcrPull on the registry
resource "azurerm_role_assignment" "api_acr_pull" {
  scope                = azurerm_container_registry.ctf.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_container_app.api.identity[0].principal_id
}

# ── Frontend Container App ────────────────────────────────────────────────

resource "azurerm_container_app" "frontend" {
  name                         = "ctf-frontend"
  resource_group_name          = data.azurerm_resource_group.ctf.name
  container_app_environment_id = azurerm_container_app_environment.ctf.id
  revision_mode                = "Single"

  identity {
    type = "SystemAssigned"
  }

  registry {
    server   = azurerm_container_registry.ctf.login_server
    identity = "system"
  }

  template {
    min_replicas = 1
    max_replicas = 2

    container {
      name   = "ctf-frontend"
      image  = var.frontend_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "API_URL"
        value = "https://ctf-api.internal.${azurerm_container_app_environment.ctf.default_domain}"
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
}

# Grant the frontend's managed identity AcrPull on the registry
resource "azurerm_role_assignment" "frontend_acr_pull" {
  scope                = azurerm_container_registry.ctf.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_container_app.frontend.identity[0].principal_id
}
