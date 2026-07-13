from __future__ import annotations

import os
import re
from dataclasses import dataclass


SAFE_RESOURCE = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
SAFE_PROJECT = re.compile(r"^[a-z][a-z0-9-]{4,62}$")


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_anon_key: str
    admin_email: str
    gcp_project: str
    gcp_region: str
    cloud_run_job: str

    def __post_init__(self):
        if not self.supabase_url.startswith("https://"):
            raise ValueError("SUPABASE_URL must use https")
        if not self.supabase_anon_key:
            raise ValueError("SUPABASE_ANON_KEY is required")
        if self.admin_email.lower() != "plusmg@gmail.com":
            raise ValueError("ADMIN_EMAIL must be the configured owner")
        if not SAFE_PROJECT.fullmatch(self.gcp_project):
            raise ValueError("GCP_PROJECT is invalid")
        if not SAFE_RESOURCE.fullmatch(self.gcp_region) or not SAFE_RESOURCE.fullmatch(self.cloud_run_job):
            raise ValueError("Cloud Run resource name is invalid")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            supabase_url=os.environ.get("SUPABASE_URL", ""),
            supabase_anon_key=os.environ.get("SUPABASE_ANON_KEY", ""),
            admin_email=os.environ.get("ADMIN_EMAIL", "plusmg@gmail.com"),
            gcp_project=os.environ.get("GCP_PROJECT", ""),
            gcp_region=os.environ.get("GCP_REGION", "asia-northeast3"),
            cloud_run_job=os.environ.get("CLOUD_RUN_JOB", "todaysingi-worker"),
        )
