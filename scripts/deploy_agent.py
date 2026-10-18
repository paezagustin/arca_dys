"""Agente pull instalado por root. Solo stdlib; jamás ejecuta scripts descargados.

Configuración y estado FUERA del checkout. No importar la aplicación en el host.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from urllib.request import Request, build_opener, HTTPRedirectHandler, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse
import zipfile

REPOSITORY = "paezagustin/arca_dys"
REQUIRED_JOBS = {"tests", "security", "arm64", "ci-required"}
# Política positiva, instalada por root. Todo lo desconocido exige aprobación SHA.
ROUTINE_PREFIXES = ("app/templates/", "app/assets/", "tests/")
ROUTINE_FILES = {"app/api/business.py", "app/api/dashboard.py", "app/api/registers.py",
                 "app/services/business.py", "app/services/metrics.py", "app/services/registers.py",
                 "app/services/day_closing.py", "app/services/excel_export.py", "app/services/listings.py"}


class Blocked(RuntimeError):
    pass


class Deferred(RuntimeError):
    """Estado normal mientras CI corre o main cambia; reintentar en el próximo tick."""


def require(condition, code):
    if not condition:
        raise Blocked(code)


def sha(value):
    require(isinstance(value, str) and re.fullmatch("[0-9a-f]{40}", value), "invalid-commit")
    return value


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as output:
        output.write(json.dumps(value, sort_keys=True) + "\n")
        output.flush()
        os.fsync(output.fileno())
    temporary.chmod(0o600)
    temporary.replace(path)
    sync_directory(path.parent)


def sync_directory(path):
    descriptor = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_json(path):
    return json.loads(path.read_text())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, token):
        self.token = token

    def request(self, path):
        require(path.startswith("/") and not path.startswith("//"), "invalid-api-path")
        return Request("https://api.github.com/repos/" + REPOSITORY + path,
                       headers={"Authorization": "Bearer " + self.token,
                                "Accept": "application/vnd.github+json", "User-Agent": "arca-dys-deployer",
                                "X-GitHub-Api-Version": "2022-11-28"})

    def get(self, path):
        with build_opener(NoRedirect()).open(self.request(path), timeout=30) as response:
            return json.load(response)

    def download(self, artifact, target):
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", artifact.get("digest", "")), "artifact-digest-required")
        try:
            response = build_opener(NoRedirect()).open(self.request(f"/actions/artifacts/{int(artifact['id'])}/zip"), timeout=30)
        except HTTPError as error:
            require(error.code == 302, "artifact-download-failed")
            location = error.headers["Location"]
            parsed = urlparse(location)
            require(parsed.scheme == "https" and parsed.hostname and (
                parsed.hostname.endswith(".blob.core.windows.net") or
                parsed.hostname.endswith(".actions.githubusercontent.com")), "artifact-redirect-denied")
            # Nunca reenviar Authorization a almacenamiento de artefactos.
            response = build_opener(NoRedirect()).open(Request(location), timeout=120)
        total, digest = 0, hashlib.sha256()
        with response, target.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                require(total <= 2_000_000_000, "artifact-too-large")
                digest.update(chunk)
                output.write(chunk)
        require("sha256:" + digest.hexdigest() == artifact["digest"], "artifact-digest-mismatch")


def verified_run(api, commit):
    runs = api.get(f"/actions/workflows/tests.yml/runs?event=push&branch=main&head_sha={sha(commit)}&per_page=100")
    require(runs["total_count"] <= 100, "too-many-runs")
    candidates = [r for r in runs["workflow_runs"] if r["head_sha"] == commit and r["head_branch"] == "main" and r["event"] == "push"]
    if not candidates:
        raise Deferred("ci-not-found")
    run = max(candidates, key=lambda r: (r["id"], r.get("run_attempt", 1)))
    if run["status"] != "completed":
        raise Deferred("ci-in-progress")
    require(run["conclusion"] == "success", "ci-not-successful")
    jobs = api.get(f"/actions/runs/{run['id']}/jobs?filter=latest&per_page=100")
    require(jobs["total_count"] <= 100, "too-many-jobs")
    for name in REQUIRED_JOBS:
        matches = [j for j in jobs["jobs"] if j["name"] == name]
        require(len(matches) == 1 and matches[0]["status"] == "completed" and matches[0]["conclusion"] == "success", "required-job-not-successful")
    artifacts = api.get(f"/actions/runs/{run['id']}/artifacts?per_page=100")
    require(artifacts["total_count"] <= 100, "too-many-artifacts")
    matches = [a for a in artifacts["artifacts"] if a["name"] == "production-arm64-" + commit and not a["expired"]]
    require(len(matches) == 1, "release-artifact-not-found")
    return matches[0]


def routine_change(api, previous, target):
    comparison = api.get(f"/compare/{sha(previous)}...{sha(target)}")
    require(comparison["status"] == "ahead" and comparison["merge_base_commit"]["sha"] == previous,
            "non-fast-forward-release")
    # GitHub compare devuelve como máximo 300 archivos: en el límite falla cerrada.
    files = comparison.get("files", [])
    require(bool(files) and len(files) < 300, "diff-incomplete")
    commits = comparison.get("commits", [])
    require(0 < comparison["total_commits"] == len(commits) <= 50, "commit-history-incomplete-or-too-large")
    # Incluso sin protección administrativa, el agente rechaza pushes directos:
    # cada commit nuevo en main debe corresponder al squash de un PR integrado.
    for commit in commits:
        pulls = api.get(f"/commits/{sha(commit['sha'])}/pulls?per_page=100")
        require(len(pulls) < 100, "pull-request-history-incomplete")
        matches = [p for p in pulls if p.get("merged_at") and p["merge_commit_sha"] == commit["sha"]
                   and p["base"]["ref"] == "main" and p["base"]["repo"]["full_name"] == REPOSITORY]
        require(len(matches) == 1, "merged-pull-request-required")
    names = [name for f in files for name in (f["filename"], f.get("previous_filename", f["filename"]))]
    return all(name.startswith(ROUTINE_PREFIXES) or name in ROUTINE_FILES for name in names)


def unpack(archive, directory, commit):
    with zipfile.ZipFile(archive) as bundle:
        require(sorted(bundle.namelist()) == ["image.tar", "release.json"], "unexpected-artifact-members")
        require(all(f.file_size <= 2_000_000_000 for f in bundle.infolist()), "artifact-too-large")
        require(bundle.getinfo("release.json").file_size < 16384, "metadata-too-large")
        metadata = json.loads(bundle.read("release.json"))
        require(metadata["commit"] == sha(commit) and metadata["protocol"] == 1 and metadata["architecture"] == "arm64", "release-metadata-mismatch")
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", metadata["image_id"]), "invalid-image-id")
        require(re.fullmatch(r"[0-9a-f]{64}", metadata["tar_sha256"]), "invalid-tar-digest")
        with bundle.open("image.tar") as source, (directory / "image.tar").open("wb") as target:
            shutil.copyfileobj(source, target)
    with (directory / "image.tar").open("rb") as source:
        require(hashlib.file_digest(source, "sha256").hexdigest() == metadata["tar_sha256"], "image-digest-mismatch")
    return metadata


class Host:
    def __init__(self, config):
        self.config = config
        self.state = Path(config["state_directory"])
        self.control = Path(config["control_directory"])
        self.compose = ["docker", "compose", "--project-directory", config["checkout"], "--env-file", config["env_file"],
                        "-p", config["project"], "-f", config["compose_file"], "-f", str(self.state / "image.json")]

    def command(self, *args, timeout=180):
        # No imprimir stdout/stderr que podrían contener configuración/secretos.
        try:
            return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout).stdout
        except (subprocess.SubprocessError, OSError):
            raise Blocked("host-command-failed") from None

    def inspect(self, container):
        return json.loads(self.command("docker", "inspect", container))[0]

    def preflight(self, recovery=False):
        cfg = self.config
        require(self.command("uname", "-m").strip() == "aarch64", "arm64-host-required")
        require(self.command("findmnt", "-n", "-o", "UUID", "--target", cfg["ssd_mount"]).strip() == cfg["ssd_uuid"], "ssd-mismatch")
        self.command("mountpoint", "-q", cfg["ssd_mount"])
        require((self.control / "protocol-v1").is_file(), "bootstrap-required")
        notifier = Path("/usr/local/sbin/arca-dys-deploy-notify")
        require(notifier.is_file() and os.access(notifier, os.X_OK), "notification-hook-required")
        for path in [cfg["postgres_data"], cfg["certificates"], cfg["logs"], str(self.state), str(self.control)]:
            require(Path(path).is_dir(), "required-directory-missing")
            require(self.command("findmnt", "-n", "-o", "UUID", "--target", path).strip() == cfg["ssd_uuid"], "volume-not-on-ssd")
        pg, app = self.inspect(cfg["postgres_container"]), self.inspect(cfg["app_container"])
        for container, service in [(pg, "postgres"), (app, "fastapi")]:
            require((container["State"]["Running"] or (recovery and service == "fastapi")) and container["Config"]["Labels"].get("com.docker.compose.project") == cfg["project"]
                    and container["Config"]["Labels"].get("com.docker.compose.service") == service, "existing-stack-mismatch")
        mounts = {m["Destination"]: m for m in pg["Mounts"]}
        require(mounts["/var/lib/postgresql/data"]["Source"] == cfg["postgres_data"], "postgres-mount-mismatch")
        mounts = {m["Destination"]: m for m in app["Mounts"]}
        for destination, source in [("/run/arca", cfg["certificates"]), ("/app/logs", cfg["logs"]), ("/run/arca-deploy", str(self.control))]:
            require(mounts.get(destination, {}).get("Source") == source, "app-mount-mismatch")
        require(mounts["/run/arca-deploy"]["RW"] is False, "control-must-be-readonly")
        return app

    def use_image(self, image):
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", image), "invalid-image-id")
        atomic_json(self.state / "image.json", {"services": {"fastapi": {"image": image}}})
        self.command(*self.compose, "config", "--quiet")
        # Se captura el JSON local (contiene secretos) pero nunca se imprime.
        effective = json.loads(self.command(*self.compose, "config", "--format", "json"))
        service = effective["services"]["fastapi"]
        require(service["container_name"] == self.config["app_container"], "compose-container-drift")
        require(service["environment"].get("DEPLOY_CONTROL_PATH") == "/run/arca-deploy", "compose-control-drift")
        mounts = {m["target"]: m for m in service["volumes"]}
        for destination, source in [("/run/arca", self.config["certificates"]), ("/app/logs", self.config["logs"]),
                                    ("/run/arca-deploy", str(self.control))]:
            require(mounts.get(destination, {}).get("source") == source, "compose-mount-drift")
        require(mounts["/run/arca-deploy"].get("read_only") is True, "compose-control-must-be-readonly")

    def probe(self, image):
        self.use_image(image)
        return json.loads(self.command(*self.compose, "run", "--rm", "--no-deps", "-T", "--entrypoint", "python", "fastapi",
                                       "-m", "scripts.deploy_guard", "--drain"))

    def replace(self, image):
        self.use_image(image)
        self.command(*self.compose, "up", "-d", "--no-deps", "--no-build", "--pull", "never", "fastapi", timeout=360)

    def open_url(self, url):
        parsed = urlparse(url)
        require(parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1"}, "loopback-smoke-required")
        return urlopen(url, timeout=5)

    def smoke(self, metadata):
        cfg = self.config
        stage = "health"
        for _ in range(min(60, max(1, self.config.get("smoke_attempts", 60)))):
            try:
                stage = "health"
                with self.open_url(cfg["health_url"]) as response:
                    health = json.load(response)
                if (health["status"] == "ok" and health["commit"] == metadata["commit"] and health["paused"] is True
                        and health["deployment_protocol"] == 1 and health["revision"] == metadata["revision"]
                        and health["worker_alive"] is True):
                    stage = "database-guard"
                    self.command("docker", "exec", cfg["app_container"], "python", "-m", "scripts.deploy_guard", "--drain")
                    # GET sin sesión/escrituras, sin consultar proveedores ni crear cookies.
                    stage = "login-page"
                    with self.open_url(cfg["health_url"].removesuffix("/health") + "/login") as page:
                        require(page.status == 200 and b"<form" in page.read(), "web-smoke-failed")
                    return
            except Exception:
                pass
            time.sleep(2)
        raise Blocked("post-deploy-smoke-failed-" + stage)


def deploy(host, metadata, previous, current_head):
    marker = host.control / "paused"
    require(not marker.exists(), "previous-maintenance-unresolved")
    with marker.open("x") as output:
        output.write("deployment\n")
        output.flush()
        os.fsync(output.fileno())
    sync_directory(host.control)
    try:
        old_probe = json.loads(host.command("docker", "exec", host.config["app_container"], "python", "-m", "scripts.deploy_guard", "--drain"))
        require(old_probe["protocol"] == 1 and old_probe["revision"] == previous["revision"] == metadata["revision"], "maintenance-required")
        require(host.probe(metadata["image_id"]) == old_probe, "candidate-schema-incompatible")
        # Volver a mirar main después de descargar y drenar: nunca publicar un SHA atrasado.
        if current_head() != metadata["commit"]:
            raise Deferred("superseded-commit")
    except Exception:
        marker.unlink()  # La aplicación antigua no se reemplazó; reabrir operaciones.
        raise
    atomic_json(host.state / "pending.json", {"previous": previous, "target": metadata})
    try:
        host.replace(metadata["image_id"])
        host.smoke(metadata)
    except Exception:
        # El marcador sigue puesto en ambas versiones durante recuperación.
        require(host.probe(previous["image_id"])["revision"] == previous["revision"], "rollback-schema-mismatch")
        host.replace(previous["image_id"])
        host.smoke(previous)
        (host.state / "pending.json").unlink()
        marker.unlink()
        raise Blocked("release-failed-previous-image-restored") from None
    atomic_json(host.state / "previous.json", previous)
    atomic_json(host.state / "current.json", metadata)
    (host.state / "pending.json").unlink()
    marker.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/arca-dys-deploy/config.json")
    parser.add_argument("--retry", action="store_true", help="Después de revisar un bloqueo local")
    parser.add_argument("--recover", action="store_true", help="Restaurar imagen previa guardada; no restaura datos")
    parser.add_argument("--record-bootstrap", action="store_true", help="Registrar la app protocolo 1 instalada y pausada; no la reemplaza")
    args = parser.parse_args()
    require(os.geteuid() == 0, "root-owned-agent-required")
    config = read_json(Path(args.config))
    host = Host(config)
    with (host.state / "lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        commit = "unknown"
        try:
            if not args.record_bootstrap and not (host.state / "enabled").is_file():
                return
            if not args.retry and not args.recover and not args.record_bootstrap and (host.state / "failed.json").exists():
                return  # El primer fallo ya notificó; requiere revisión explícita.
            app = host.preflight(recovery=args.recover)
            if args.record_bootstrap:
                require(not (host.state / "current.json").exists() and not (host.state / "pending.json").exists(), "bootstrap-state-already-exists")
                require((host.control / "paused").is_file(), "pause-marker-required")
                image = json.loads(host.command("docker", "image", "inspect", app["Image"]))[0]
                commit = sha(image["Config"]["Labels"]["org.opencontainers.image.revision"])
                require(image["Architecture"] == "arm64", "arm64-image-required")
                snapshot = json.loads(host.command("docker", "exec", config["app_container"], "python", "-m", "scripts.deploy_guard", "--drain"))
                metadata = {"commit": commit, "image_id": app["Image"], "revision": snapshot["revision"], "protocol": 1, "architecture": "arm64"}
                host.smoke(metadata)
                host.command("docker", "image", "tag", app["Image"], "arca-dys:rollback-" + commit)
                atomic_json(host.state / "current.json", metadata)
                (host.state / "failed.json").unlink(missing_ok=True)
                print("Bootstrap recorded; paused remains set; timer was not enabled", flush=True)
                return
            previous = read_json(host.state / "current.json")
            if args.recover:
                pending = read_json(host.state / "pending.json")
                old = pending["previous"]
                commit = old["commit"]
                require((host.control / "paused").is_file(), "pause-marker-required")
                require(host.probe(old["image_id"])["revision"] == old["revision"], "rollback-schema-mismatch")
                host.replace(old["image_id"])
                host.smoke(old)
                atomic_json(host.state / "current.json", old)
                (host.control / "paused").unlink()
                (host.state / "pending.json").unlink()
                result = "recovered-manually"
            else:
                require(app["Image"] == previous["image_id"], "running-image-drift")
                require(not (host.state / "pending.json").exists(), "interrupted-deployment-review-required")
                api = GitHub(Path(config["token_file"]).read_text().strip())
                head = lambda: api.get("/git/ref/heads/main")["object"]["sha"]
                commit = sha(head())
                if commit == previous["commit"]:
                    return
                artifact = verified_run(api, commit)
                routine = routine_change(api, previous["commit"], commit)
                if not routine:
                    approval = host.state / "approved-sha"
                    require(approval.is_file() and approval.read_text().strip() == commit, "explicit-sha-approval-required")
                with tempfile.TemporaryDirectory(dir=host.state) as temporary:
                    directory = Path(temporary)
                    api.download(artifact, directory / "artifact.zip")
                    metadata = unpack(directory / "artifact.zip", directory, commit)
                    host.command("docker", "load", "-i", str(directory / "image.tar"), timeout=300)
                    image = json.loads(host.command("docker", "image", "inspect", metadata["image_id"]))[0]
                    require(image["Architecture"] == "arm64" and image["Config"]["Labels"]["org.opencontainers.image.revision"] == commit, "loaded-image-mismatch")
                    deploy(host, metadata, previous, head)
                result = "deployed"
            if not args.recover:
                (host.state / "failed.json").unlink(missing_ok=True)
            event = {"date": datetime.now(timezone.utc).isoformat(), "commit": commit, "result": result}
        except Deferred:
            return  # CI pendiente: reintentar sin notificaciones repetitivas.
        except Exception as error:
            event = {"date": datetime.now(timezone.utc).isoformat(), "commit": commit, "result": "blocked",
                     "error": str(error) if isinstance(error, Blocked) else type(error).__name__}
            atomic_json(host.state / "failed.json", event)
        with (host.state / "events.jsonl").open("a") as output:
            output.write(json.dumps(event) + "\n")
        print(json.dumps(event), flush=True)
        if event["result"] == "blocked":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
