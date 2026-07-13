from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "test.yml"
DEPLOY = ROOT / ".github" / "workflows" / "deploy-cloud-worker.yml"
RUNBOOK = ROOT / "docs" / "CLOUD_RUN_RUNBOOK.md"
ENV_EXAMPLE = ROOT / ".env.example"


PINNED_ACTIONS = {
    "actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10",
    "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
    "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e",
}


def test_ci_is_secretless_pinned_and_runs_every_test_suite():
    text = CI.read_text(encoding="utf-8")

    for action in PINNED_ACTIONS:
        assert action in text
    assert "permissions:\n  contents: read" in text
    assert "python -m pytest tests/ -q" in text
    assert "npm --prefix admin test" in text
    assert "npm --prefix admin run build" in text
    assert "secrets." not in text


def test_deploy_uses_github_oidc_and_updates_both_cloud_run_images():
    text = DEPLOY.read_text(encoding="utf-8")

    assert "id-token: write" in text
    assert "google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093" in text
    assert "google-github-actions/setup-gcloud@aa5489c8933f4cc7a4f7d45035b3b1440c9c10db" in text
    assert "workload_identity_provider" in text
    assert "docker build" in text and "docker push" in text
    assert "gcloud run jobs update" in text
    assert "gcloud run deploy" in text
    assert "service_account_key" not in text.lower()


def test_runbook_keeps_side_effect_retries_off_and_schedules_maintenance():
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "--max-retries=0" in text
    assert "--sync-ga4" in text
    assert "--cleanup" in text
    assert "roles/run.invoker" in text
    assert "CLOUD_DISPATCHER_URL" in text
    assert "GA4 Property Viewer" in text


def test_environment_template_declares_cloud_and_ga4_contract_without_values():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")

    for name in (
        "GA4_PROPERTY_ID", "LLM_API_URL", "LLM_API_KEY", "LLM_MODEL",
        "TYPECAST_VOICE_ID", "INSTAGRAM_ACCOUNT_ID", "INSTAGRAM_ACCESS_TOKEN",
        "NETLIFY_BUILD_HOOK_URL", "CLOUD_DISPATCHER_URL",
    ):
        assert f"{name}=" in text
