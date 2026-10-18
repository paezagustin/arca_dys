"""Validación de manifiestos con valores ficticios, nunca .env.prod real."""
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    # Copia únicamente manifiestos; evita que Compose lea configuración privada local.
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary)
        for name in ("docker-compose.prod.yml", "docker-compose.ngrok.yml", "docker-compose.test.yml", "docker-compose.arm64-test.yml"):
            (target / name).write_bytes(Path(name).read_bytes())
        (target / ".env.prod").write_text("ENV=production\nINTEGRATIONS_MODE=production\nALLOW_LIVE_OPERATIONS=false\n")
        environment = dict(os.environ, POSTGRES_PASSWORD="compose-validation-only", ALLOW_LIVE_OPERATIONS="false",
                           NGROK_URL="https://example.invalid")
        for files in [("docker-compose.prod.yml",), ("docker-compose.prod.yml", "docker-compose.ngrok.yml"),
                      ("docker-compose.test.yml",), ("docker-compose.arm64-test.yml",)]:
            command = ["docker", "compose", "--project-directory", temporary]
            for name in files:
                command.extend(["-f", str(target / name)])
            subprocess.run(command + ["config", "--quiet"], env=environment, check=True)


if __name__ == "__main__":
    main()
