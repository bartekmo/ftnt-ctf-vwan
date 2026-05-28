terraform {
  required_version = ">= 1.7"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.53"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Uncomment and configure to store state remotely (recommended for team use):
  # backend "azurerm" {
  #   resource_group_name  = "rg-tfstate"
  #   storage_account_name = "tfstatexperts26"
  #   container_name       = "tfstate"
  #   key                  = "ctf.tfstate"
  # }
}

provider "azurerm" {
  features {}
}

provider "azuread" {}

# ── Current context ───────────────────────────────────────────────────────

data "azurerm_client_config" "current" {}

# ── Resource group ────────────────────────────────────────────────────────

data "azurerm_resource_group" "ctf" {
  name     = var.resource_group_name
}

data "azurerm_subscription" "current" {
  subscription_id = var.azure_subscription_id
}