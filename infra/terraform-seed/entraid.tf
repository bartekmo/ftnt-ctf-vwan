resource "azuread_administrative_unit" "example" {
  display_name              = "${var.prefix}-AU"
  description               = "AU for vwanlab resources (EMEA Cloud CSE team)"
  hidden_membership_enabled = false
}


resource "azurerm_user_assigned_identity" "ctf_app" {
  name                = "${var.prefix}-ctf-app"
  resource_group_name = azurerm_resource_group.infra.name
  location            = azurerm_resource_group.infra.location
}

