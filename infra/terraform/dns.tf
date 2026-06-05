# ── Custom domain: vwanlab.40net.cloud ───────────────────────────────────────
#
# DNS is hosted in GCP Cloud DNS. Authentication handled by Terraform Cloud.
#
# Deployment order required by ACA API:
#   1. DNS A record + TXT verification record
#   2. Bind hostname to container app (no cert yet — bindingType=Disabled)
#   3. Create managed certificate (requires hostname already bound)
#   4. Update binding to reference the certificate (bindingType=SniEnabled)

# ── GCP DNS ───────────────────────────────────────────────────────────────────

data "google_dns_managed_zone" "vwanlab" {
  name = "vwanlab"
}

# A record at zone apex — CNAME not allowed at apex per DNS spec
resource "google_dns_record_set" "frontend_a" {
  name         = data.google_dns_managed_zone.vwanlab.dns_name
  type         = "A"
  ttl          = 300
  managed_zone = data.google_dns_managed_zone.vwanlab.name
  rrdatas      = [azurerm_container_app_environment.ctf.static_ip_address]
}

# TXT record for ACA domain ownership verification
resource "google_dns_record_set" "frontend_verify" {
  name         = "asuid.${data.google_dns_managed_zone.vwanlab.dns_name}"
  type         = "TXT"
  ttl          = 300
  managed_zone = data.google_dns_managed_zone.vwanlab.name
  rrdatas      = ["\"${azurerm_container_app.frontend.custom_domain_verification_id}\""]
}

# ── Step 1: bind hostname without certificate ─────────────────────────────────

resource "azapi_update_resource" "frontend_hostname_binding" {
  type        = "Microsoft.App/containerApps@2023-05-01"
  resource_id = azurerm_container_app.frontend.id

  body = {
    properties = {
      configuration = {
        ingress = {
          customDomains = [{
            name        = "vwanlab.40net.cloud"
            bindingType = "Disabled"
          }]
        }
      }
    }
  }

  depends_on = [
    google_dns_record_set.frontend_a,
    google_dns_record_set.frontend_verify,
  ]
}

# ── Step 2: create managed certificate (hostname must already be bound) ───────

resource "azapi_resource" "frontend_managed_cert" {
  type      = "Microsoft.App/managedEnvironments/managedCertificates@2023-05-01"
  name      = "vwanlab-40net-cloud"
  parent_id = azurerm_container_app_environment.ctf.id
  location  = azurerm_container_app_environment.ctf.location

  body = {
    properties = {
      subjectName             = "vwanlab.40net.cloud"
      domainControlValidation = "HTTP"
    }
  }

  depends_on = [azapi_update_resource.frontend_hostname_binding]
}

# ── Step 3: update binding to enable TLS with the managed certificate ─────────

resource "azapi_update_resource" "frontend_custom_domain" {
  type        = "Microsoft.App/containerApps@2023-05-01"
  resource_id = azurerm_container_app.frontend.id

  body = {
    properties = {
      configuration = {
        ingress = {
          customDomains = [{
            name          = "vwanlab.40net.cloud"
            bindingType   = "SniEnabled"
            certificateId = azapi_resource.frontend_managed_cert.id
          }]
        }
      }
    }
  }

  depends_on = [azapi_resource.frontend_managed_cert]
}
