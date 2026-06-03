terraform {
  #required_version = "1.15.5"

  cloud {
    organization = "40net"
    workspaces {
      name = "vwanlab-perm"
    }
  }
}

provider "azurerm" {
  features {}
}

provider "azuread" {}


resource "azurerm_resource_group" "infra" {
  name     = var.rg_name
  location = var.location

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [tags]
  }
}

resource "azurerm_container_registry" "ctf" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.infra.name
  location            = azurerm_resource_group.infra.location
  sku                 = "Basic"
  admin_enabled       = false
}
