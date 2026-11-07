from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


def test_pwa_assets_are_available_without_creating_a_session():
    with TestClient(app) as browser:
        response = browser.get("/assets/manifest.json")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert "set-cookie" not in response.headers

        manifest = response.json()
        assert manifest["name"] == manifest["short_name"] == "ARCA DYS"
        assert manifest["start_url"] == "/page/invoice"
        assert manifest["scope"] == "/"
        assert manifest["display"] == "standalone"
        icons = {int(icon["sizes"].split("x")[0]): icon["src"] for icon in manifest["icons"]}
        assert icons.keys() == {192, 512}
        icons[180] = "/assets/pwa/icon-180.png"
        for size, path in icons.items():
            icon = browser.get(path)
            assert icon.status_code == 200
            assert icon.headers["content-type"] == "image/png"
            assert "set-cookie" not in icon.headers
            with Image.open(BytesIO(icon.content)) as png:
                assert png.format == "PNG"
                assert png.size == (size, size)
                png.verify()


def test_pwa_launch_keeps_anonymous_access_and_private_responses():
    with TestClient(app) as browser:
        page = browser.get("/page/invoice", follow_redirects=False)
        assert page.status_code == 200
        assert 'rel="manifest" href="/assets/manifest.json"' in page.text
        assert 'rel="apple-touch-icon" sizes="180x180" href="/assets/pwa/icon-180.png"' in page.text
        assert page.headers["cache-control"] == "no-store"

        assert browser.get("/business").status_code == 200
        settings = browser.get("/settings", follow_redirects=False)
        assert settings.status_code == 303
        assert settings.headers["location"] == "/login"
