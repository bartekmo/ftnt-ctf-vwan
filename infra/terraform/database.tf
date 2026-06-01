# PostgreSQL 16 Flexible Server — Burstable tier, suitable for workshop scale
# (~50 attendees, ephemeral event lasting 3-8 hours).

resource "azurerm_postgresql_flexible_server" "ctf" {
  name                   = var.db_server_name
  resource_group_name    = local.ctf_rg.name
  location               = local.ctf_rg.location
  version                = "16"
  administrator_login    = var.db_admin_user
  administrator_password = var.db_admin_password
  sku_name               = var.db_sku
  storage_mb             = 32768
  #zone                   = "1"

  backup_retention_days        = 7
  geo_redundant_backup_enabled = false

  lifecycle {
    ignore_changes = [
      # Ignore changes to admin password after initial creation
      zone
    ]
  }
}

resource "azurerm_postgresql_flexible_server_database" "ctfdb" {
  name      = var.db_name
  server_id = azurerm_postgresql_flexible_server.ctf.id
  collation = "en_US.utf8"
  charset   = "utf8"
}

# Allow connections from all Azure services (Container Apps uses Azure IPs).
# For tighter security, use VNet integration on both the Container Apps
# environment and the PostgreSQL server.
resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "allow-azure-services"
  server_id        = azurerm_postgresql_flexible_server.ctf.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}
