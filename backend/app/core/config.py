from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://ctf:ctfpassword@localhost:5432/ctfdb"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # App
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # CTF
    CTF_NAME: str = "Xperts26 vWAN CTF"
    FIRST_BLOOD_BONUS: int = 50

    # Shared secret for prober-to-API authentication.
    # Set the same value as PROBER_SECRET on the prober container.
    # Generate with: openssl rand -hex 32
    PROBER_SECRET: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()


class AzureSettings(BaseSettings):
    # Azure identity & subscription
    AZURE_SUBSCRIPTION_ID: str = ""

    # vWAN infrastructure
    VWAN_NAME: str = ""
    RG_PREFIX: str = "vwanlab-student-"
    RG_SUFFIX: str = ""
    RG_BRANCHES: str = ""

    # FortiFlex tokens — JSON string: {"hubs": [null, [token1, token2], [token1, token2], ...]}
    # Index 0 is unused; index N corresponds to env_id N.
    FLEX_TOKENS: str = "{\"hubs\": []}"

    # Azure student account password (same for all teams)
    AZURE_STUDENT_PASSWORD: str = "StudentPassword123!"

    # Microsoft Graph — TAP generation
    # Client ID of a separate user-assigned managed identity with
    # UserAuthenticationMethod.ReadWrite.All scoped to the vwanlab AU only.
    # If empty, the TAP endpoint will return 503.
    GRAPH_CLIENT_ID: str = ""
    AZURE_TENANT_ID: str = ""
    # UPN domain that all student accounts belong to
    STUDENT_UPN_DOMAIN: str = "fortinetcloud.onmicrosoft.com"
    STUDENT_UPN_PREFIX: str = "vwanlab"
    # TAP lifetime in minutes (default 24h)
    TAP_LIFETIME_MINUTES: int = 1440

    # FortiManager (shared across all teams)
    FMG_SERIAL: str = ""
    FMG_IP: str = ""

    class Config:
        env_file = ".env"


azure_settings = AzureSettings()
