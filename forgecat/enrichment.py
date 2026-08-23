from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests

from forgecat.config import ENABLE_MANUFACTURER_FETCH

MANUFACTURER_DOMAINS = {
    "Rheem Manufacturing": ["frigidaire.com"],
    "Whirlpool Corporation": ["whirlpool.com", "learnwhirlpool.com"],
    "GE Appliances": ["geappliances.com"],
    "LG Electronics": ["lg.com"],
    "Freud Inc": ["freudtools.com", "diablotools.com"],
    "Milwaukee Electric Tool Corporation": ["milwaukeetool.com"],
    "3M Company": ["3m.com"],
}


def _allowed_domain(url: str, manufacturer: str) -> bool:
    domains = MANUFACTURER_DOMAINS.get(manufacturer, [])
    host = urlparse(url).netloc.lower()
    return any(d in host for d in domains)


def fetch_manufacturer_snippets(
    manufacturer_name: str,
    mpn: str,
    known_url: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "snippets": [],
        "mfr_url": known_url or "",
        "ref_urls": [],
        "source": "none",
    }
    if not ENABLE_MANUFACTURER_FETCH or not enabled:
        return result

    if known_url and _allowed_domain(known_url, manufacturer_name):
        result["mfr_url"] = known_url
        result["source"] = "known_url"
        return result

    domains = MANUFACTURER_DOMAINS.get(manufacturer_name, [])
    for domain in domains[:1]:
        url = f"https://www.{domain}/"
        try:
            resp = requests.get(url, timeout=5, headers={"User-Agent": "ForgeCat/1.0"})
            if resp.status_code == 200:
                text = re.sub(r"<[^>]+>", " ", resp.text)
                text = re.sub(r"\s+", " ", text)[:500]
                result["snippets"].append({"domain": domain, "text": text})
                result["mfr_url"] = url
                result["source"] = "manufacturer_domain"
                break
        except requests.RequestException:
            continue

    return result
