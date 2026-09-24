"""Startup invariant (#21): every AI endpoint the app talks to must be on this device."""

import ipaddress
import socket
from urllib.parse import urlparse

LOCAL_NAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def is_local(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host in LOCAL_NAMES:
        return True
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror:
        return False
    return bool(addrs) and all(ipaddress.ip_address(a.split("%")[0]).is_loopback for a in addrs)


class CloudEndpointError(RuntimeError):
    pass


def assert_local(urls: list[str]) -> None:
    remote = [u for u in urls if not is_local(u)]
    if remote:
        raise CloudEndpointError(
            f"Refusing to start: AI endpoint(s) {remote} are not on this device. "
            "Recovery Monitor only runs AI inference locally on the ZGX Nano."
        )


def network_reachable() -> bool:
    """For the UI's 'offline and still working' indicator only. Analysis never needs the network."""
    for host in (("8.8.8.8", 53), ("1.1.1.1", 443)):
        try:
            with socket.create_connection(host, timeout=0.8):
                return True
        except OSError:
            continue
    return False
