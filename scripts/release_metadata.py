"""Metadatos de imagen exacta; no carga configuración de aplicación ni secretos."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def main(commit, directory):
    if not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("Commit completo requerido")
    directory = Path(directory)
    image = json.loads(subprocess.check_output(["docker", "image", "inspect", "arca-dys:" + commit]))[0]
    if image["Architecture"] != "arm64" or image["Config"]["Labels"]["org.opencontainers.image.revision"] != commit:
        raise ValueError("Imagen incompatible")
    # Leer solo la revisión dentro de la imagen, sin importar app ni abrir DB.
    revision = subprocess.check_output(["docker", "run", "--rm", "--network", "none", "--platform", "linux/arm64",
        image["Id"], "python", "-c", "from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config('alembic.ini')).get_current_head())"], text=True).strip()
    with (directory / "image.tar").open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    (directory / "release.json").write_text(json.dumps({"commit": commit, "architecture": "arm64", "protocol": 1,
        "revision": revision, "image_id": image["Id"], "tar_sha256": digest}, sort_keys=True) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
