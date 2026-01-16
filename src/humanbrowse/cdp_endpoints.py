import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

import httpx


@dataclass
class CdpProbeResult:
    base_url: str
    version_info: Optional[dict]


def _get_default_route_ip() -> Optional[str]:
    try:
        proc = subprocess.run(
            "ip route show | grep -i default | awk '{ print $3 }'",
            shell=True,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return None
    if proc.stdout:
        ip = proc.stdout.strip().splitlines()[0].strip()
        return ip or None
    return None


def build_cdp_base_urls(port: int, allow_nat: bool = False) -> List[str]:
    bases = [f"http://127.0.0.1:{port}"]
    if allow_nat:
        host_ip = _get_default_route_ip()
        if host_ip and host_ip != "127.0.0.1":
            bases.append(f"http://{host_ip}:{port}")
    return bases


def probe_cdp(base_url: str, timeout_s: float = 2.0) -> Optional[CdpProbeResult]:
    url = f"{base_url}/json/version"
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                return CdpProbeResult(base_url=base_url, version_info=resp.json())
    except Exception:
        return None
    return None


def select_cdp_endpoint(
    port: int, allow_nat: bool = False, timeout_s: float = 2.0
) -> Tuple[str, Optional[dict]]:
    for base in build_cdp_base_urls(port, allow_nat=allow_nat):
        result = probe_cdp(base, timeout_s=timeout_s)
        if result:
            return result.base_url, result.version_info
    return build_cdp_base_urls(port, allow_nat=False)[0], None
