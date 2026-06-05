# ── Custom domain: vwanlab.40net.cloud ───────────────────────────────────────
#
# DNS is hosted in GCP Cloud DNS. Authentication is handled by Terraform Cloud.
#
# The zone "vwanlab" manages "vwanlab.40net.cloud". We use the zone apex
# (dns_name = "vwanlab.40net.cloud.") for the frontend — CNAME is not allowed
# at zone apex per DNS spec, so we use an A record pointing to the ACA
# environment's static outbound IP.
#
# ACA managed certificate is provisioned via AzAPI (azurerm provider does not
# support managed certs without a certificate blob).

# ── GCP DNS ───────────────────────────────────────────────────────────────────

data "google_dns_managed_zone" "vwanlab" {
  name = "vwanlab"   # zone name in GCP Cloud DNS
}

# A record at zone apex: vwanlab.40net.cloud → ACA environment static IP
resource "google_dns_record_set" "frontend_a" {
  name         = data.google_dns_managed_zone.vwanlab.dns_name   # "vwanlab.40net.cloud."
  type         = "A"
  ttl          = 300
  managed_zone = data.google_dns_managed_zone.vwanlab.name
  rrdatas      = [azurerm_container_app_environment.ctf.static_ip_address]
}

# TXT record for ACA domain ownership verification
resource "google_dns_record_set" "frontend_verify" {
  name         = "asuid.${data.google_dns_managed_zone.vwanlab.dns_name}"   # "asuid.vwanlab.40net.cloud."
  type         = "TXT"
  ttl          = 300
  managed_zone = data.google_dns_managed_zone.vwanlab.name
  rrdatas      = ["\"${azurerm_container_app.frontend.custom_domain_verification_id}\""]
}

# ── ACA managed certificate ───────────────────────────────────────────────────
# Uses AzAPI because azurerm_container_app_environment_certificate requires a
# certificate blob; managed (ACME) certs are only supported via the ARM API.

resource "azapi_resource" "frontend_managed_cert" {
  type      = "Microsoft.App/managedEnvironments/managedCertificates@2023-05-01"
  name      = "vwanlab-40net-cloud"
  parent_id = azurerm_container_app_environment.ctf.id
  location  = azurerm_container_app_environment.ctf.location

  body = {
    properties = {
      subjectName             = "vwanlab.40net.cloud"
      domainControlValidation = "HTTP"   # ACA uses HTTP-01 challenge via the static IP
    }
  }

  depends_on = [
    google_dns_record_set.frontend_a,
    google_dns_record_set.frontend_verify,
  ]
}

# ── Custom domain binding on the frontend container app ───────────────────────

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
