# Challenge Authoring Guide

## Directory structure

```
challenges/
  index.yaml                  ← ordered list, metadata for all challenges
  01-access-azure/
    challenge.mdx             ← MDX content (Markdown + React components)
    img/                      ← images referenced in challenge.mdx
  02-license-nvas/
    challenge.mdx
    img/
  ...
```

## index.yaml fields

| Field    | Type   | Description |
|----------|--------|-------------|
| id       | string | Unique slug, must match directory name |
| title    | string | Shown in sidebar and challenge header |
| category | enum   | networking, vpn, routing, security, monitoring, misc |
| points   | int    | Base score. 0 = informational |
| scored   | bool   | false = no prober, no points, no submit button |
| prober   | string | Prober function name (omit when scored: false) |
| visible  | bool   | false = hidden from attendees |

Order is determined by the position in the  list — no separate field needed.

## MDX frontmatter fields

```yaml
---
title: "Establish the Branch VPN tunnel"
category: vpn
points: 150
scored: true
prober: check_branch_vpn
hints:
  - text: "Hint text visible after purchase"
    cost: 20        # points deducted on unlock
  - text: "Second hint"
    cost: 30
refs:
  - label: "Link display text"
    url: "https://..."
---
```

## Available components in MDX

### EnvVar (block display — labelled row with copy button)

```mdx
# Field from environment
<EnvVar field="branch_fgt_pip" label="Branch FortiGate IP" />

# Static literal string
<EnvVar value="admin" label="Username" />

# Field with prefix or suffix (mixed)
<EnvVar field="fgt_nva1_pip" prefix="https://" label="NVA 1 URL" />
<EnvVar field="env_id" prefix="vwanlab" suffix="@fortinetcloud.onmicrosoft.com" label="Username" />

# Clickable link (opens new tab, shows external link icon)
<EnvVar field="url_fmg" label="FortiManager" link />
<EnvVar value="https://portal.azure.com" label="Azure Portal" link />
<EnvVar field="fmg_ip" prefix="https://" label="FortiManager" link />

# Secret (hidden by default, reveal button)
<EnvVar field="azure_password" label="Password" secret />
```

### EnvVarInline (inline in prose)

```mdx
# Field from environment
Connect to <EnvVarInline field="branch_fgt_pip" /> in your browser.

# With prefix/suffix
Open <EnvVarInline field="hub_name" prefix="hub" /> in Azure.

# Static literal
Login as <EnvVarInline value="admin" />.
```

Available field names come from the `TeamEnvironmentOut` schema:
- `azure_username`, `azure_password`
- `rg_name`, `env_id`
- `fgt_asn`, `azure_asn`
- `overlay_network`, `sdwan_healthcheck_range`
- `fgt_nva1_name`, `fgt_nva1_pip`, `fgt_nva2_name`, `fgt_nva2_pip`
- `flex_token1`, `flex_token2`
- `spoke_cidr`, `spoke_server_private`, `spoke_server_public`, `spoke_peered`
- `branch_cidr`, `branch_fgt_pip`, `branch_win_pip`
- `fmg_serial`, `fmg_ip`

### Images

Place images in `img/` inside the challenge directory. Reference them using the
absolute public path (relative paths do not work from compiled MDX bundles):

```mdx
![Alt text](/challenges/00-access-azure/img/my-diagram.png)
```

The Docker build copies all `challenges/*/img/` files into the frontend `public/`
directory so they are served as static assets.

## Adding a new challenge

1. Add an entry to `index.yaml`
2. Create directory `challenges/NN-slug/`
3. Create `challenges/NN-slug/challenge.mdx`
4. `git push` — the frontend build picks up changes automatically

## Informational challenges

Set `scored: false` and `points: 0`. Omit the `prober` field.
The challenge page will show no submit button and no point value.
