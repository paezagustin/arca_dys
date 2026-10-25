import os, unittest
from unittest.mock import patch
from starlette.requests import Request
from starlette.responses import Response

from app.core.access_cookies import cookie_secure

def request(host="192.168.0.10:8001", client="192.168.0.20", scheme="http", extra=()):
    return Request({"type":"http","method":"GET","scheme":scheme,"path":"/login",
        "root_path":"","query_string":b"","headers":[(b"host",host.encode()),*extra],
        "client":(client,12345) if client else None,"server":("192.168.0.10",8000)})

class CookieTransportTests(unittest.TestCase):
    config = {"ARCA_HTTP_COOKIE_HOSTS":"127.0.0.1,192.168.0.10,100.64.0.10",
        "ARCA_HTTP_COOKIE_CLIENT_NETWORKS":"127.0.0.0/8,192.168.0.0/24,100.64.0.0/10,172.19.0.1/32"}

    def test_production_defaults_to_secure_without_explicit_exception(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertTrue(cookie_secure(request(),production=True))

    def test_private_http_clients_receive_usable_httponly_samesite_cookies(self):
        with patch.dict(os.environ,self.config,clear=True):
            for host,client in [("192.168.0.10:8001","192.168.0.20"),
                                ("100.64.0.10:8001","100.64.0.20"),
                                ("127.0.0.1:8001","172.19.0.1")]:
                with self.subTest(host=host,client=client):
                    secure=cookie_secure(request(host,client),production=True)
                    response=Response();response.set_cookie("session","test-only",secure=secure,httponly=True,samesite="lax")
                    header=response.headers["set-cookie"].lower()
                    self.assertNotIn("; secure",header)
                    self.assertIn("httponly",header);self.assertIn("samesite=lax",header)

    def test_https_retains_secure_on_private_and_public_hosts(self):
        with patch.dict(os.environ,self.config,clear=True):
            for host in ["192.168.0.10:8001","example.invalid"]:
                self.assertTrue(cookie_secure(request(host,scheme="https"),production=True))

    def test_public_origin_and_untrusted_sources_never_get_http_exception(self):
        with patch.dict(os.environ,self.config,clear=True):
            for host,client in [("public.example","192.168.0.20"),("192.168.0.10","203.0.113.9"),
                                ("192.168.0.10","172.19.0.6"),("192.168.0.10",None),
                                ("192.168.0.10","not-an-ip"),("192.168.0.81","192.168.0.20")]:
                self.assertTrue(cookie_secure(request(host,client),production=True))

    def test_forwarded_headers_do_not_override_connection_identity(self):
        with patch.dict(os.environ,self.config,clear=True):
            req=request(client="203.0.113.9",extra=[(b"x-forwarded-for",b"192.168.0.20"),(b"x-forwarded-host",b"192.168.0.10")])
            self.assertTrue(cookie_secure(req,production=True))

    def test_invalid_allowlist_fails_closed(self):
        with patch.dict(os.environ,{**self.config,"ARCA_HTTP_COOKIE_CLIENT_NETWORKS":"invalid"},clear=True):
            self.assertTrue(cookie_secure(request(),production=True))

    def test_development_behavior_is_preserved(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(cookie_secure(request(),production=False))

if __name__ == "__main__":
    unittest.main(verbosity=2)
