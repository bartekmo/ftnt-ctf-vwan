# Challenge Probers

Probers verify whether a team has solved a challenge by checking live
Azure infrastructure state. They run as an **ACA Job** on a per-minute
cron schedule inside the same Container Apps environment as the CTF API.

---

## Architecture

```
ACA Job: ctf-probers  (cron: * * * * *)
│
│  runner.py  ← entrypoint; orchestrates everything
│    │
│    ├─ api_client.py    GET /api/teams, GET /api/solves
│    │                   POST /api/solves  (record verified solve)
│    │
│    ├─ scoring.py       calculate_points(base, position, first_blood_at)
│    │                   pure math, no I/O
│    │
│    └─ challenges/
│         check_spoke_peered.py   ← ARM: VNet peering state
│         check_branch_vpn.py     ← ARM: IPsec tunnel state  (TODO)
│         check_branch_bgp.py     ← ARM: BGP session state   (TODO)
│         check_spoke_routing.py  ← ARM: effective routes     (TODO)
│         check_nva_licensed.py   ← ARM: NVA license state    (TODO)
```

**Why ACA Jobs:**
- Cron trigger built-in — no `while True: sleep(60)` process
- System-assigned managed identity for ARM access — no stored credentials
- Same ACA environment as the API — calls `http://ctf-api` internally
- Only consumes compute for ~5-10 seconds per minute (essentially free)

---

## Separation of concerns

| Module | Responsibility | Does NOT do |
|--------|---------------|-------------|
| `challenges/*.py` | Detect: is condition met? Returns True/False | Score, API calls |
| `scoring.py` | Calculate bonus from position + time | Network I/O |
| `api_client.py` | Talk to CTF API | Probe, score |
| `runner.py` | Orchestrate: fetch teams → probe → score → record | Any of the above |

---

## Scoring algorithm

```
total = base_points + bonus

bonus(position, minutes_since_first_blood) =
    round(100 × position_factor × time_factor)

position_factor = max(0,  1 - log(position) / log(20))
time_factor     = max(0,  1 - minutes / 60)
```

| pos | t=0min | t=15min | t=30min | t=45min | t=60min |
|-----|--------|---------|---------|---------|---------|
| 1   | 100    | 75      | 50      | 25      | 0       |
| 2   | 77     | 58      | 39      | 19      | 0       |
| 5   | 56     | 42      | 28      | 14      | 0       |
| 10  | 33     | 25      | 17      | 8       | 0       |
| 20  | 0      | 0       | 0       | 0       | 0       |

Run `python -m probers.scoring` to print the full bonus table.

---

## Writing a new prober

1. Copy `challenges/_template.py` to `challenges/check_<name>.py`
2. Implement `async def check(team: TeamContext) -> ProbeResult`
3. Add the prober name to `challenges/index.yaml` under the challenge
4. Push — GitHub Actions builds and deploys the prober image automatically

### Prober contract

```python
async def check(team: TeamContext) -> ProbeResult:
    # team.env_id          — "01", "02", ...
    # team.rg_name         — "vwanlab-student-01"
    # team.rg_branches     — shared branch RG
    # team.subscription_id — Azure subscription
    # team.hub_name        — "hub01"

    # DO:   check Azure resources via ARM SDK
    # DON'T: call the CTF API
    # DON'T: calculate scores

    return ProbeResult(solved=True/False, detail="optional reason")
```

---

## Deployment

### Environment variables

| Var | Description |
|-----|-------------|
| `CTF_API_URL` | Internal URL of the CTF API |
| `CTF_API_TOKEN` | Long-lived trainer JWT (stored as ACA secret) |
| `AZURE_SUBSCRIPTION_ID` | Subscription for ARM calls |
| `RG_PREFIX` | Student RG prefix, e.g. `vwanlab-student-` |
| `RG_SUFFIX` | Student RG suffix (often empty) |
| `RG_BRANCHES` | Shared branch site RG |

### Generate the API token

```bash
TOKEN=$(curl -s -X POST "https://<api-fqdn>/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"trainer","password":"<pw>"}' | jq -r .access_token)
# Add as prober_api_token in terraform.tfvars
```

### Terraform

```bash
cd infra/terraform
# Set in terraform.tfvars:
#   probers_image    = "xperts26ctf.azurecr.io/ctf-probers:latest"
#   prober_api_token = "<token from above>"
terraform apply
```
