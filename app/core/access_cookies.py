"""Cookie transport exceptions for explicitly trusted HTTP access only."""
import os
from ipaddress import ip_address, ip_network


def cookie_secure(request, *, production):
    if not production:
        return False
    if request.url.scheme != "http":
        return True
    hosts = {value.strip() for value in os.getenv("ARCA_HTTP_COOKIE_HOSTS", "").split(",") if value.strip()}
    if not hosts or request.url.hostname not in hosts or request.client is None:
        return True
    try:
        address = ip_address(request.client.host)
        networks = [
            ip_network(value.strip(), strict=True)
            for value in os.getenv("ARCA_HTTP_COOKIE_CLIENT_NETWORKS", "").split(",")
            if value.strip()
        ]
    except ValueError:
        return True
    return not any(address in network for network in networks)
