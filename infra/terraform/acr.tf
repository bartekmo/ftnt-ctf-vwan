# Azure Container Registry
# Admin access is disabled — authentication is handled entirely via managed
# identities (Container Apps) and federated identity (GitHub Actions).

resource "azurerm_container_registry" "ctf" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.ctf.name
  location            = azurerm_resource_group.ctf.location
  sku                 = "Basic"
  admin_enabled       = false
}
