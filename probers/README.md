# Challenge Probers

Probers are Azure-only workers that verify whether a team has solved a challenge by checking the actual infrastructure state (FortiGate configs, Azure resources, routing tables, etc.).

## Architecture (planned)

```
┌──────────────────────────────────────┐
│  Azure Container Instance / ACI      │
│  (privileged, has Azure credentials) │
│                                      │
│  prober_runner.py                    │
│    └─ polls each challenge prober    │
│    └─ calls POST /api/solves         │
│       (authenticated as trainer)     │
└──────────────────────────────────────┘
```

## Interface Contract

Each prober is a Python module exposing:

```python
async def check(team_id: int, team_context: dict) -> ProbeResult:
    """
    Returns ProbeResult(solved=True/False, points=int)
    team_context contains Azure subscription/resource group info per team.
    """
```

## Implementation Status

- [ ] Base runner scaffold
- [ ] Azure SDK integration
- [ ] Challenge-specific probers (implemented alongside each challenge)

## Prober Authentication

Probers authenticate to the CTF API using a trainer-role JWT token stored as an Azure Key Vault secret. The token is long-lived (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).
