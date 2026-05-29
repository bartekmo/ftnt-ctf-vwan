# Environment Variable Reference

Complete list of all variables available to challenge MDX files via
`<EnvVar field="..." />` and `<EnvVarInline field="..." />` components,
plus the `hub` object available from `GET /api/infra/hubs/{hubName}`.

All fields except `hub` come from `GET /api/teams/my/environment`
(`TeamEnvironmentOut` schema, `backend/app/api/routes/teams.py`).

---

## Identity

| Field       | Type   | Source   | Detail |
|-------------|--------|----------|--------|
| `team_id`   | int    | DB       | Auto-assigned integer primary key |
| `team_name` | string | DB       | User-chosen team name |
| `env_id`    | string | DB / calculated | Sequential integer assigned at team creation, zero-padded → `"01"`, `"02"`, … |

---

## Azure credentials

| Field                | Type   | Source          | Detail |
|----------------------|--------|-----------------|--------|
| `azure_username`     | string | Hardcoded pattern | `vwanlab{env_id}@fortinetcloud.onmicrosoft.com` |
| `azure_password`     | string | Env var         | `AZURE_STUDENT_PASSWORD` (default `StudentPassword123!`) |
| `rg_name`            | string | Calculated      | `RG_PREFIX + env_id + RG_SUFFIX` (both env vars) |

---

## Hub object (from `GET /api/infra/hubs/hub{env_id}`)

Not part of `TeamEnvironmentOut` — fetched separately by `EnvironmentPage`
via `infraApi.hub(hubName)` and displayed as "Region" in the Azure
Credentials card. Available in MDX as `hub?.location` if you extend
`useEnvData` to include it.

| Field      | Type   | Source   | Detail |
|------------|--------|----------|--------|
| `name`     | string | ARM API  | `VirtualHubs.list()` filtered by `VWAN_NAME`, hub name |
| `location` | string | ARM API  | Azure region, e.g. `westeurope` |

---

## BGP / ASNs

| Field       | Type | Source          | Detail |
|-------------|------|-----------------|--------|
| `fgt_asn`   | int  | Hardcoded table | `_ASNS[]` in `teams.py`: index 1→64512, 2→64513, … (64512 + env_id - 1) |
| `azure_asn` | int  | Hardcoded       | Always `65515` |

---

## Networking

| Field                    | Type   | Source          | Detail |
|--------------------------|--------|-----------------|--------|
| `overlay_network`        | string | Calculated      | `10.200.{n}.0/24` where `n` = integer env_id |
| `sdwan_healthcheck_range`| string | Calculated      | `172.{n}.0.0/16` |
| `spoke_cidr`             | string | ARM API         | `VirtualNetworks.get(rg, spoke{n}Vnet)` → `address_space.address_prefixes[0]` |
| `branch_cidr`            | string | ARM API         | `Subnets.get(RG_BRANCHES, branch{n}Vnet, branchPrivate)` → `address_prefix` |

---

## Hub NVAs (FortiGates in vWAN hub)

| Field          | Type   | Source   | Detail |
|----------------|--------|----------|--------|
| `fgt_nva1_name`| string | ARM API  | `NetworkVirtualAppliances.list()` filtered by hub `vwanlab{n}-hub`, sorted by NVA name then NIC instance name → entry [0].instance_name |
| `fgt_nva1_pip` | string | ARM API  | Same call → entry [0].pip (NIC `public_ip_address`) |
| `url_fgt_nva1` | string | Calculated | `https://{fgt_nva1_pip}` |
| `fgt_nva2_name`| string | ARM API  | Same call → entry [1].instance_name |
| `fgt_nva2_pip` | string | ARM API  | Same call → entry [1].pip |
| `url_fgt_nva2` | string | Calculated | `https://{fgt_nva2_pip}` |

---

## FortiFlex tokens

| Field         | Type   | Source          | Detail |
|---------------|--------|-----------------|--------|
| `flex_token1` | string | Env var (secret)| `FLEX_TOKENS` JSON → `hubs[n][0]`; format: `{"hubs": [null, ["tok-a","tok-b"], …]}` |
| `flex_token2` | string | Env var (secret)| `FLEX_TOKENS` JSON → `hubs[n][1]` |

---

## Spoke VNet

| Field                 | Type    | Source   | Detail |
|-----------------------|---------|----------|--------|
| `spoke_cidr`          | string  | ARM API  | `VirtualNetworks.get(rg, spoke{n}Vnet)` → `address_space.address_prefixes[0]` |
| `spoke_server_private`| string  | ARM API  | `NetworkInterfaces.get(rg, spoke{n}Srv-nic1)` → `ip_configurations[0].private_ip_address` |
| `spoke_server_public` | string  | ARM API  | `PublicIpAddresses.get(rg, spoke{n}Srv-pip)` → `ip_address` |
| `spoke_peered`        | boolean | ARM API  | `VirtualNetworks.get(…)` → `len(virtual_network_peerings) > 0` |

---

## Branch site

| Field            | Type   | Source   | Detail |
|------------------|--------|----------|--------|
| `branch_cidr`    | string | ARM API  | `Subnets.get(RG_BRANCHES, branch{n}Vnet, branchPrivate)` → `address_prefix` |
| `branch_fgt_pip` | string | ARM API  | `PublicIpAddresses.get(RG_BRANCHES, branch{n}Fgt-pip)` → `ip_address` |
| `url_fgt_branch` | string | Calculated | `https://{branch_fgt_pip}` |
| `branch_win_pip` | string | ARM API  | `PublicIpAddresses.get(RG_BRANCHES, branch{n}Win-pip)` → `ip_address` |

---

## FortiManager (shared across all teams)

| Field       | Type   | Source     | Detail |
|-------------|--------|------------|--------|
| `fmg_serial`| string | Env var    | `FMG_SERIAL` |
| `fmg_ip`    | string | Env var    | `FMG_IP` |
| `url_fmg`   | string | Calculated | `https://{fmg_ip}` |

---

## ARM API resource name patterns

These are the exact Azure resource names the backend looks up, where
`{n}` is the integer env_id (e.g. `1`) and `{ns}` is zero-padded (`01`).

| Resource                     | RG                          | Name pattern            |
|------------------------------|-----------------------------|-------------------------|
| Hub NVA (FortiGate)          | (subscription-wide list)    | filtered: hub = `vwanlab{ns}-hub` |
| Spoke VNet                   | `{RG_PREFIX}{ns}{RG_SUFFIX}`| `spoke{ns}Vnet`         |
| Spoke server NIC             | `{RG_PREFIX}{ns}{RG_SUFFIX}`| `spoke{ns}Srv-nic1`     |
| Spoke server PIP             | `{RG_PREFIX}{ns}{RG_SUFFIX}`| `spoke{ns}Srv-pip`      |
| Branch FGT PIP               | `RG_BRANCHES`               | `branch{ns}Fgt-pip`     |
| Branch Windows PIP           | `RG_BRANCHES`               | `branch{ns}Win-pip`     |
| Branch subnet                | `RG_BRANCHES`               | VNet `branch{ns}Vnet`, subnet `branchPrivate` |

---

## Env vars required on the API container

| Env var                  | Default                  | Used for |
|--------------------------|--------------------------|----------|
| `AZURE_SUBSCRIPTION_ID`  | _(empty)_                | ARM API calls |
| `AZURE_STUDENT_PASSWORD` | `StudentPassword123!`    | `azure_password` field |
| `VWAN_NAME`              | _(empty)_                | Hub lookup |
| `RG_PREFIX`              | `vwanlab-student-`       | Student RG name prefix |
| `RG_SUFFIX`              | _(empty)_                | Student RG name suffix |
| `RG_BRANCHES`            | _(empty)_                | Branch resources RG |
| `FLEX_TOKENS`            | `{"hubs": []}`           | FortiFlex tokens (secret) |
| `FMG_SERIAL`             | _(empty)_                | FortiManager serial |
| `FMG_IP`                 | _(empty)_                | FortiManager IP/FQDN |
