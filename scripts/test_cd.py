"""Ensayo Docker REAL, solo Linux/CI: app mock, DB tmpfs y proyecto efímero.

Ejercita el mismo reemplazo, sonda, health y recuperación del agente; no usa su
token ni preflight de producción. Los SHA de las tres imágenes son ficticios.
"""
import json
from pathlib import Path
import io
import subprocess
import tempfile
from uuid import uuid4
from urllib.parse import urlparse
from scripts.deploy_agent import Host, Blocked, atomic_json, deploy


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


class FixtureHost(Host):
    def open_url(self, url):
        # Red Docker internal:true no publica puertos al host. Mismo smoke HTTP,
        # con transporte loopback DENTRO de la app y sin abrir salida a Internet.
        path = urlparse(url).path
        body = self.command("docker", "exec", self.config["app_container"], "python", "-c",
                            "import sys,urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000'+sys.argv[1],timeout=5).read().decode(),end='')", path)
        response = io.BytesIO(body.encode())
        response.status = 200
        return response


def main():
    project = "arca-dys-cd-qa-" + uuid4().hex[:8]
    with tempfile.TemporaryDirectory(prefix=project) as temporary:
        root = Path(temporary)
        for directory in ("control", "state", "certs", "logs"):
            (root / directory).mkdir()
        (root / "control" / "protocol-v1").touch()
        releases = []
        for index, char in enumerate("abc"):
            commit = char * 40
            tag = project + ":" + char
            if index < 2:
                run("docker", "build", "--target", "production", "--build-arg", "APP_COMMIT=" + commit, "-t", tag, ".")
            else:
                # Candidata del mismo esquema con arranque intencionalmente fallido.
                dockerfile = f'FROM {project}:b\nENV APP_COMMIT={commit}\nLABEL org.opencontainers.image.revision={commit}\nCMD ["python", "-c", "raise SystemExit(42)"]\n'
                run("docker", "build", "-t", tag, "-", input=dockerfile)
            image_id = json.loads(run("docker", "image", "inspect", tag))[0]["Id"]
            releases.append({"commit": commit, "image_id": image_id, "protocol": 1, "revision": "0013_mp_identity"})
        fake_env = {"ENV": "development", "INTEGRATIONS_MODE": "mock", "ALLOW_LIVE_OPERATIONS": "false",
                    "DATABASE_URL": "postgresql://arca_test:local-test-only@postgres:5432/arca_dys_test",
                    "DEPLOY_CONTROL_PATH": "/run/arca-deploy"}
        compose = {"services": {
            "postgres": {"image": "postgres:17.8-alpine", "environment": {"POSTGRES_DB": "arca_dys_test", "POSTGRES_USER": "arca_test", "POSTGRES_PASSWORD": "local-test-only"},
                         "tmpfs": ["/var/lib/postgresql/data"], "networks": ["isolated"],
                         "healthcheck": {"test": ["CMD-SHELL", "pg_isready -U arca_test -d arca_dys_test"], "interval": "1s", "timeout": "3s", "retries": 30}},
            "fastapi": {"container_name": project + "-app", "image": releases[0]["image_id"], "environment": fake_env,
                        "networks": ["isolated"],
                        "volumes": [{"type": "bind", "source": str(root / source), "target": target, "read_only": source != "logs"}
                                    for source, target in [("control", "/run/arca-deploy"), ("certs", "/run/arca"), ("logs", "/app/logs")]]}},
            "networks": {"isolated": {"internal": True}}}
        (root / "compose.json").write_text(json.dumps(compose))
        (root / "fake.env").write_text("")
        config = {"state_directory": str(root / "state"), "control_directory": str(root / "control"), "checkout": str(root),
                  "env_file": str(root / "fake.env"), "compose_file": str(root / "compose.json"), "project": project,
                  "app_container": project + "-app", "certificates": str(root / "certs"), "logs": str(root / "logs"),
                  "health_url": "http://127.0.0.1:8000/health", "smoke_attempts": 4}
        host = FixtureHost(config)
        atomic_json(host.state / "current.json", releases[0])
        host.use_image(releases[0]["image_id"])
        try:
            host.command(*host.compose, "up", "-d", "--wait", "postgres")
            host.command(*host.compose, "run", "--rm", "--no-deps", "-T", "--entrypoint", "alembic", "fastapi", "upgrade", "head")
            (host.control / "paused").touch()
            host.replace(releases[0]["image_id"])
            host.smoke(releases[0])
            (host.control / "paused").unlink()
            pg = host.command(*host.compose, "ps", "-q", "postgres").strip()
            host.command("docker", "exec", pg, "psql", "-U", "arca_test", "-d", "arca_dys_test", "-c",
                         "INSERT INTO customer_credits (entry_key,customer,amount,observation,entry_date,paid,version) VALUES ('cd-sentinel','Cliente ficticio',12345.67,'CD fixture',CURRENT_DATE,false,1)")
            deploy(host, releases[1], releases[0], lambda: releases[1]["commit"])
            assert host.inspect(config["app_container"])["Image"] == releases[1]["image_id"]
            try:
                deploy(host, releases[2], releases[1], lambda: releases[2]["commit"])
            except Blocked as error:
                assert str(error) == "release-failed-previous-image-restored"
            else:
                raise AssertionError("La imagen fallida no disparó recuperación")
            assert host.inspect(config["app_container"])["Image"] == releases[1]["image_id"]
            assert not (host.control / "paused").exists()
            assert json.loads((host.state / "current.json").read_text())["commit"] == releases[1]["commit"]
            assert host.command(*host.compose, "ps", "-q", "postgres").strip() == pg
            assert host.command("docker", "exec", pg, "psql", "-U", "arca_test", "-d", "arca_dys_test", "-Atc",
                                "SELECT amount FROM customer_credits WHERE entry_key='cd-sentinel'").strip() == "12345.67"
            print("Docker CD aislado: reemplazo real, arranque fallido, recuperación verificada, mismo PostgreSQL/datos: OK")
        except Exception:
            # Solo fixtures de ESTE proyecto: no se admite configuración productiva.
            app = host.inspect(config["app_container"])
            print("CD fixture container state:", app["State"], flush=True)
            subprocess.run(["docker", "logs", "--tail", "60", config["app_container"]], check=False)
            subprocess.run(["docker", "exec", config["app_container"], "python", "-c",
                            "from scripts.deploy_guard import probe; print(probe(drain=True))"], check=False)
            raise
        finally:
            # Solo proyecto generado por este ensayo y PostgreSQL tmpfs ficticio.
            host.command(*host.compose, "down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
