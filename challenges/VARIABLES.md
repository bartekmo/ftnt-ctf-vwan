# Environment Variable Reference

Complete list of all fields available in challenge MDX files via
`<EnvVar field="..." />` and `<EnvVarInline field="..." />`.

All fields come from `GET /api/teams/my/environment` (`TeamEnvironmentOut`).

The `hub` object (name + location/region) is fetched separately by
`EnvironmentPage` via `GET /api/infra/hubs/{hubName}` and is not available
in MDX components.

---

## Identity

| Field       | Type   | Source           | Detail |
|-------------|--------|------------------|--------|
| `team_id`   | int    | DB               | Auto-assigned integer primary key |
| `team_name` | string | DB               | User-chosen team name |
| `env_id`    | string | DB / calculated  | Zero-padded sequential integer, e.g. `"01"` |
| `hub_name`  | string | Calculated       | `"hub" + env_id`, e.g. `"hub01"` |

---

## Azure credentials

| Field                | Type   | Source          | Detail |
|----------------------|--------|-----------------|--------|
| `azure_username`     | string | Hardcoded pattern | `vwanlab{env_id}@fortinetcloud.onmicrosoft.com` |
| `azure_password`     | string | Env var         | `AZURE_STUDENT_PASSWORD` (default `StudentPassword123!`) |
| `azure_tap`          | string | DB (EnvTap)     | Temporary Access Pass — generated via Graph API, 24h validity |
| `azure_tap_expires`  | string | DB (EnvTap)     | ISO datetime of TAP expiry |
| `rg_name`            | string | Calculated      | `RG_PREFIX + env_id + RG_SUFFIX` |

---

## BGP / ASNs

| Field       | Type | Source          | Detail |
|-------------|------|-----------------|--------|
| `fgt_asn`   | int  | Hardcoded table | `_ASNS[]` in `teams.py`: 64512 + env_id - 1 |
| `azure_asn` | int  | Hardcoded       | Always `65515` |

---

## Networking

| Field                     | Type   | Source     | Detail |
|---------------------------|--------|------------|--------|
| `overlay_network`         | string | Calculated | `10.200.{n}.0/24` |
| `sdwan_healthcheck_range` | string | Calculated | `172.{n}.0.0/16` |

---

## Hub NVAs (FortiGates in vWAN hub)

| Field           | Type   | Source     | Detail |
|-----------------|--------|------------|--------|
| `fgt_nva1_name` | string | ARM API    | NVA instance name from `NetworkVirtualAppliances.list()`, entry [0] |
| `fgt_nva1_pip`  | string | ARM API    | NVA 1 public IP |
| `url_fgt_nva1`  | string | Calculated | `https://{fgt_nva1_pip}` |
| `fgt_nva2_name` | string | ARM API    | NVA instance name, entry [1] |
| `fgt_nva2_pip`  | string | ARM API    | NVA 2 public IP |
| `url_fgt_nva2`  | string | Calculated | `https://{fgt_nva2_pip}` |

---

## FortiFlex tokens

| Field         | Type   | Source           | Detail |
|---------------|--------|------------------|--------|
| `flex_token1` | string | Env var (secret) | `FLEX_TOKENS` JSON → `hubs[n][0]` |
| `flex_token2` | string | Env var (secret) | `FLEX_TOKENS` JSON → `hubs[n][1]` |

---

## Spoke VNet

| Field                 | Type    | Source   | Detail |
|-----------------------|---------|----------|--------|
| `spoke_cidr`          | string  | ARM API  | `VirtualNetworks.get(rg, spoke{n}Vnet)` → address prefix |
| `spoke_server_private`| string  | ARM API  | Spoke server private IP |
| `spoke_server_public` | string  | ARM API  | Spoke server public IP |
| `spoke_peered`        | boolean | ARM API  | Whether VNet has any peerings |

---

## Branch site

| Field            | Type   | Source     | Detail |
|------------------|--------|------------|--------|
| `branch_cidr`    | string | ARM API    | Branch subnet CIDR |
| `branch_fgt_pip` | string | ARM API    | Branch FortiGate public IP |
| `url_fgt_branch` | string | Calculated | `https://{branch_fgt_pip}` |
| `branch_win_pip` | string | ARM API    | Branch Windows Desktop public IP |

---

## FortiManager (shared)

| Field        | Type   | Source     | Detail |
|--------------|--------|------------|--------|
| `fmg_serial` | string | App Config | FortiManager serial number |
| `fmg_ip`     | string | App Config | FortiManager IP or FQDN |
| `url_fmg`    | string | Calculated | `https://{fmg_ip}` |

---

## ARM API resource name patterns

`{n}` = integer env_id, `{ns}` = zero-padded env_id (e.g. `01`)

| Resource            | Resource Group              | Name pattern |
|---------------------|-----------------------------|--------------|
| Hub NVA             | (subscription-wide list)    | filtered by hub = `hub{ns}` |
| Spoke VNet          | `{RG_PREFIX}{ns}{RG_SUFFIX}`| `spoke{ns}Vnet` |
| Spoke server NIC    | `{RG_PREFIX}{ns}{RG_SUFFIX}`| `spoke{ns}Srv-nic1` |
| Spoke server PIP    | `{RG_PREFIX}{ns}{RG_SUFFIX}`| `spoke{ns}Srv-pip` |
| Branch FGT PIP      | `RG_BRANCHES`               | `branch{ns}Fgt-pip` |
| Branch Windows PIP  | `RG_BRANCHES`               | `branch{ns}Win-pip` |
| Branch subnet       | `RG_BRANCHES`               | VNet `branch{ns}Vnet`, subnet `branchPrivate` |

---

## Env vars required on the API container

| Env var                  | Source      | Used for |
|--------------------------|-------------|----------|
| `APP_CONFIG_ENDPOINT`    | Terraform   | App Configuration store URL |
| `AZURE_CLIENT_ID`        | Terraform   | User-assigned managed identity for ARM calls |
| `GRAPH_CLIENT_ID`        | App Config  | Separate identity for Graph/TAP calls |
| `AZURE_TENANT_ID`        | App Config  | Entra tenant ID |
| `AZURE_SUBSCRIPTION_ID`  | App Config  | ARM subscription |
| `AZURE_STUDENT_PASSWORD` | App Config  | `azure_password` field |
| `VWAN_NAME`              | App Config  | Hub lookup |
| `RG_PREFIX`              | App Config  | Student RG name prefix |
| `RG_SUFFIX`              | App Config  | Student RG name suffix |
| `RG_BRANCHES`            | App Config  | Branch resources RG |
| `FLEX_TOKENS`            | App Config  | FortiFlex tokens JSON |
| `FMG_SERIAL`             | App Config  | FortiManager serial |
| `FMG_IP`                 | App Config  | FortiManager IP/FQDN |
| `DATABASE_URL`           | ACA secret  | PostgreSQL connection string |
| `SECRET_KEY`             | ACA secret  | JWT signing key (auto-generated by Terraform) |
| `PROBER_SECRET`          | ACA secret  | Shared secret for prober→API auth (auto-generated) |
