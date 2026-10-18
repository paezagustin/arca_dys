"""Pruebas del host con Docker/GitHub simulados: nunca operan el host productivo."""
import hashlib
import json
from pathlib import Path
import zipfile
import pytest
from scripts.deploy_agent import (Blocked, Deferred, GitHub, Host, atomic_json, deploy,
                                  routine_change, unpack, verified_run, REQUIRED_JOBS)

OLD, NEW = "a" * 40, "b" * 40
OLD_IMAGE, NEW_IMAGE = "sha256:" + "1" * 64, "sha256:" + "2" * 64
REVISION = "0013_mp_identity"


class API:
    def __init__(self):
        self.run = {"id": 42, "head_sha": NEW, "head_branch": "main", "event": "push", "status": "completed", "conclusion": "success"}
        self.jobs = [{"name": n, "status": "completed", "conclusion": "success"} for n in REQUIRED_JOBS]
        self.artifact = {"name": "production-arm64-" + NEW, "expired": False, "id": 7}
        self.comparison = {"status": "ahead", "merge_base_commit": {"sha": OLD}, "files": [{"filename": "app/templates/dashboard.html"}],
                           "total_commits": 1, "commits": [{"sha": NEW}]}
        self.pulls = [{"merged_at": "2026-10-18", "merge_commit_sha": NEW,
                       "base": {"ref": "main", "repo": {"full_name": "paezagustin/arca_dys"}}}]

    def get(self, path):
        if "/pulls?" in path:
            return self.pulls
        if "/compare/" in path:
            return self.comparison
        if "/jobs?" in path:
            return {"total_count": len(self.jobs), "jobs": self.jobs}
        if "/artifacts?" in path:
            return {"total_count": 1, "artifacts": [self.artifact]}
        return {"total_count": 1, "workflow_runs": [self.run]}


@pytest.mark.parametrize("conclusion", ["failure", "skipped", "neutral", "cancelled", None])
def test_ci_rejects_any_required_job_without_explicit_success(conclusion):
    api = API()
    api.jobs[0]["conclusion"] = conclusion
    with pytest.raises(Blocked, match="required-job-not-successful"):
        verified_run(api, NEW)


def test_ci_accepts_only_completed_main_push_and_exact_artifact():
    api = API()
    assert verified_run(api, NEW)["id"] == 7
    api.run["status"] = "in_progress"
    with pytest.raises(Deferred):
        verified_run(api, NEW)
    api.run["status"] = "completed"
    api.run["event"] = "pull_request"
    with pytest.raises(Deferred):
        verified_run(api, NEW)
    api.run["event"] = "push"
    api.artifact["name"] = "production-arm64-" + OLD
    with pytest.raises(Blocked):
        verified_run(api, NEW)


def test_missing_duplicate_and_expired_results_fail_closed():
    api = API()
    api.jobs.append(api.jobs[0])
    with pytest.raises(Blocked):
        verified_run(api, NEW)
    api.jobs = api.jobs[:-2]
    with pytest.raises(Blocked):
        verified_run(api, NEW)
    api = API()
    api.artifact["expired"] = True
    with pytest.raises(Blocked):
        verified_run(api, NEW)


@pytest.mark.parametrize("name", ["migrations/versions/new.py", "app/services/billing.py", "Dockerfile", ".github/workflows/tests.yml", "app/core/config.py", "requirements.txt", "scripts/deploy_agent.py", "AGENTS.md", "unknown.txt"])
def test_sensitive_or_unknown_changes_need_explicit_approval(name):
    api = API()
    assert routine_change(api, OLD, NEW)
    api.comparison["files"][0]["previous_filename"] = name
    assert not routine_change(api, OLD, NEW)


def test_non_forward_and_incomplete_diff_are_blocked():
    api = API()
    api.comparison["status"] = "diverged"
    with pytest.raises(Blocked):
        routine_change(api, OLD, NEW)
    api.comparison["status"] = "ahead"
    api.comparison["files"] *= 300
    with pytest.raises(Blocked, match="diff-incomplete"):
        routine_change(api, OLD, NEW)


def test_direct_push_and_partial_commit_history_cannot_deploy():
    api = API()
    api.pulls = []
    with pytest.raises(Blocked, match="merged-pull-request-required"):
        routine_change(api, OLD, NEW)
    api = API()
    api.comparison["total_commits"] = 2
    with pytest.raises(Blocked, match="commit-history-incomplete"):
        routine_change(api, OLD, NEW)


def metadata(commit=NEW, image=NEW_IMAGE):
    return {"commit": commit, "image_id": image, "revision": REVISION, "protocol": 1, "architecture": "arm64"}


class FakeHost:
    def __init__(self, directory):
        self.state = directory / "state"
        self.control = directory / "control"
        self.state.mkdir()
        self.control.mkdir()
        self.config = {"app_container": "app"}
        self.events = []
        self.fail_target = False
        self.fail_rollback = False
        self.schema = REVISION

    def command(self, *args):
        assert (self.control / "paused").exists()
        return json.dumps({"protocol": 1, "revision": REVISION})

    def probe(self, image):
        self.events.append(("probe", image))
        assert (self.control / "paused").exists()
        return {"protocol": 1, "revision": self.schema}

    def replace(self, image):
        self.events.append(("replace", image))
        assert (self.control / "paused").exists()
        assert (self.state / "pending.json").is_file()

    def smoke(self, release):
        self.events.append(("smoke", release["image_id"]))
        assert (self.control / "paused").exists()
        if (release["commit"] == NEW and self.fail_target) or (release["commit"] == OLD and self.fail_rollback):
            raise Blocked("synthetic-startup-failure")


def test_success_records_previous_exact_commit_and_opens_gate_after_smoke(tmp_path):
    host = FakeHost(tmp_path)
    deploy(host, metadata(), metadata(OLD, OLD_IMAGE), lambda: NEW)
    assert json.loads((host.state / "current.json").read_text())["commit"] == NEW
    assert json.loads((host.state / "previous.json").read_text())["image_id"] == OLD_IMAGE
    assert not (host.control / "paused").exists()
    assert not (host.state / "pending.json").exists()


def test_failed_startup_restores_previous_image_before_opening_gate(tmp_path):
    host = FakeHost(tmp_path)
    host.fail_target = True
    with pytest.raises(Blocked, match="previous-image-restored"):
        deploy(host, metadata(), metadata(OLD, OLD_IMAGE), lambda: NEW)
    assert host.events[-2:] == [("replace", OLD_IMAGE), ("smoke", OLD_IMAGE)]
    assert not (host.control / "paused").exists()
    assert not (host.state / "current.json").exists()


def test_failed_rollback_preserves_pause_and_pending_evidence(tmp_path):
    host = FakeHost(tmp_path)
    host.fail_target = host.fail_rollback = True
    with pytest.raises(Blocked):
        deploy(host, metadata(), metadata(OLD, OLD_IMAGE), lambda: NEW)
    assert (host.control / "paused").is_file()
    assert json.loads((host.state / "pending.json").read_text())["previous"]["commit"] == OLD


@pytest.mark.parametrize("revision,head,exception", [("new-schema", NEW, Blocked), (REVISION, OLD, Deferred)])
def test_migration_or_superseded_commit_never_replaces_running_service(tmp_path, revision, head, exception):
    host = FakeHost(tmp_path)
    host.schema = revision
    with pytest.raises(exception):
        deploy(host, metadata(), metadata(OLD, OLD_IMAGE), lambda: head)
    assert not any(event[0] == "replace" for event in host.events)
    assert not (host.control / "paused").exists()


def test_interrupted_maintenance_never_clears_marker_implicitly(tmp_path):
    host = FakeHost(tmp_path)
    (host.control / "paused").touch()
    with pytest.raises(Blocked, match="previous-maintenance-unresolved"):
        deploy(host, metadata(), metadata(OLD, OLD_IMAGE), lambda: NEW)
    assert (host.control / "paused").exists()


def test_artifact_validates_members_commit_architecture_and_digest(tmp_path):
    archive = tmp_path / "bundle.zip"
    release = dict(metadata(), tar_sha256=hashlib.sha256(b"synthetic-image").hexdigest())

    def write(extra=None):
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("release.json", json.dumps(release))
            bundle.writestr("image.tar", b"synthetic-image")
            if extra:
                bundle.writestr(extra, "arbitrary-code")

    write()
    assert unpack(archive, tmp_path, NEW)["commit"] == NEW
    release["tar_sha256"] = "0" * 64
    write()
    with pytest.raises(Blocked, match="image-digest-mismatch"):
        unpack(archive, tmp_path, NEW)
    write("../escape.py")
    with pytest.raises(Blocked, match="unexpected-artifact-members"):
        unpack(archive, tmp_path, NEW)
    assert not (tmp_path.parent / "escape.py").exists()


def test_github_token_only_goes_to_fixed_repository_api():
    api = GitHub("synthetic-token")
    assert api.request("/git/ref/heads/main").full_url == "https://api.github.com/repos/paezagustin/arca_dys/git/ref/heads/main"
    with pytest.raises(Blocked):
        api.request("https://attacker.invalid")


@pytest.fixture
def configured_host(tmp_path, monkeypatch):
    from copy import deepcopy
    config = {"state_directory": str(tmp_path / "state"), "control_directory": str(tmp_path / "control"),
              "checkout": str(tmp_path / "checkout"), "env_file": str(tmp_path / "env"), "compose_file": str(tmp_path / "compose.yml"),
              "project": "existing", "ssd_mount": str(tmp_path), "ssd_uuid": "synthetic-uuid", "postgres_container": "pg_dys",
              "app_container": "fastapi_app", "postgres_data": str(tmp_path / "postgres"), "certificates": str(tmp_path / "certs"),
              "logs": str(tmp_path / "logs")}
    for key in ("state_directory", "control_directory", "postgres_data", "certificates", "logs"):
        Path(config[key]).mkdir()
    (Path(config["control_directory"]) / "protocol-v1").touch()
    app_mounts = [{"Destination": target, "Source": config[key], "RW": False} for target, key in
                  [("/run/arca", "certificates"), ("/app/logs", "logs"), ("/run/arca-deploy", "control_directory")]]
    containers = {
        "pg_dys": {"State": {"Running": True}, "Mounts": [{"Destination": "/var/lib/postgresql/data", "Source": config["postgres_data"]}],
                   "Config": {"Labels": {"com.docker.compose.project": "existing", "com.docker.compose.service": "postgres"}}},
        "fastapi_app": {"State": {"Running": True}, "Mounts": app_mounts,
                        "Config": {"Labels": {"com.docker.compose.project": "existing", "com.docker.compose.service": "fastapi"}}}}
    host = Host(config)
    original = Path.is_file
    monkeypatch.setattr(Path, "is_file", lambda path: True if str(path) == "/usr/local/sbin/arca-dys-deploy-notify" else original(path))
    monkeypatch.setattr("os.access", lambda *args: True)
    host.calls = []

    def command(*args, **kwargs):
        host.calls.append(args)
        if args[0] == "uname":
            return "aarch64\n"
        if args[0] == "findmnt":
            return config["ssd_uuid"] + "\n"
        if args[:2] == ("docker", "inspect"):
            return json.dumps([deepcopy(containers[args[2]])])
        return ""

    monkeypatch.setattr(host, "command", command)
    return host, containers


def test_preflight_reuses_existing_stack_and_checks_mounts(configured_host):
    host, _ = configured_host
    host.preflight()
    assert all(call[0] in {"uname", "findmnt", "mountpoint", "docker"} for call in host.calls)
    assert not any("up" in call for call in host.calls)


@pytest.mark.parametrize("drift", ["project", "postgres", "readonly", "stopped"])
def test_mount_project_and_container_drift_block_before_mutation(configured_host, drift):
    host, containers = configured_host
    if drift == "project":
        containers["pg_dys"]["Config"]["Labels"]["com.docker.compose.project"] = "other-stack"
    elif drift == "postgres":
        containers["pg_dys"]["Mounts"][0]["Source"] = "/wrong-database"
    elif drift == "readonly":
        containers["fastapi_app"]["Mounts"][-1]["RW"] = True
    else:
        containers["fastapi_app"]["State"]["Running"] = False
    with pytest.raises(Blocked):
        host.preflight()
    if drift == "stopped":
        host.preflight(recovery=True)


def test_missing_ssd_and_protocol_fail_closed(configured_host, monkeypatch):
    host, _ = configured_host
    original = host.command
    monkeypatch.setattr(host, "command", lambda *args, **kwargs: "wrong-uuid" if args[0] == "findmnt" else original(*args, **kwargs))
    with pytest.raises(Blocked, match="ssd-mismatch"):
        host.preflight()
    monkeypatch.setattr(host, "command", original)
    (host.control / "protocol-v1").unlink()
    with pytest.raises(Blocked, match="bootstrap-required"):
        host.preflight()
