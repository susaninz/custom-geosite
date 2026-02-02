#!/usr/bin/env python3
"""
Конвертер VPN-подписок (base64 VLESS URL) в Clash YAML proxy-provider формат.

Использование:
  python3 convert_vless_to_clash.py <subscription_url> <output_file>
  python3 convert_vless_to_clash.py --file <raw_file> <output_file>

Формат входа: base64-encoded список VLESS URL (по одной на строку)
Формат выхода: Clash YAML proxy-provider (список proxies)
"""

import sys
import base64
import yaml
import re
from urllib.parse import urlparse, parse_qs, unquote


def parse_vless_url(url: str) -> dict | None:
    """Парсит VLESS URL в Clash proxy dict."""
    if not url.startswith("vless://"):
        return None

    # Отделяем фрагмент (имя сервера)
    if "#" in url:
        url_part, fragment = url.rsplit("#", 1)
        name = unquote(fragment).strip()
    else:
        url_part = url
        name = "unnamed"

    # Парсим основную часть
    # vless://uuid@host:port?params
    without_scheme = url_part[len("vless://"):]
    uuid_part, rest = without_scheme.split("@", 1)

    if "?" in rest:
        host_port, query_string = rest.split("?", 1)
    else:
        host_port = rest
        query_string = ""

    host, port = host_port.rsplit(":", 1)
    port = int(port)
    params = parse_qs(query_string)

    def get_param(key, default=""):
        values = params.get(key, [default])
        return values[0] if values else default

    security = get_param("security", "")
    net_type = get_param("type", "tcp")
    flow = get_param("flow", "")
    sni = get_param("sni", "")
    fp = get_param("fp", "")
    pbk = get_param("pbk", "")
    sid = get_param("sid", "")
    mode = get_param("mode", "")
    extra = get_param("extra", "")

    proxy = {
        "name": name,
        "type": "vless",
        "server": host,
        "port": port,
        "uuid": uuid_part,
        "udp": True,
        "tls": security == "reality" or security == "tls",
    }

    if flow:
        proxy["flow"] = flow
        proxy["network"] = "tcp"

    if net_type == "xhttp":
        proxy["network"] = "xhttp"
        proxy["xhttp-opts"] = {"mode": mode or "auto"}
        if extra:
            import json
            try:
                extra_dict = json.loads(unquote(extra))
                xhttp_opts = proxy["xhttp-opts"]
                if "scMaxEachPostBytes" in extra_dict:
                    xhttp_opts["scMaxEachPostBytes"] = extra_dict["scMaxEachPostBytes"]
                if "scMaxConcurrentPosts" in extra_dict:
                    xhttp_opts["scMaxConcurrentPosts"] = extra_dict["scMaxConcurrentPosts"]
                if "scMinPostsIntervalMs" in extra_dict:
                    xhttp_opts["scMinPostsIntervalMs"] = extra_dict["scMinPostsIntervalMs"]
                if "xPaddingBytes" in extra_dict:
                    xhttp_opts["xPaddingBytes"] = extra_dict["xPaddingBytes"]
                if "noGRPCHeader" in extra_dict:
                    xhttp_opts["noGRPCHeader"] = extra_dict["noGRPCHeader"]
            except (json.JSONDecodeError, ValueError):
                pass
    elif net_type == "tcp":
        proxy["network"] = "tcp"

    if security == "reality":
        proxy["reality-opts"] = {}
        if pbk:
            proxy["reality-opts"]["public-key"] = pbk
        if sid:
            proxy["reality-opts"]["short-id"] = str(sid)
        if sni:
            proxy["servername"] = sni

    if fp:
        proxy["client-fingerprint"] = fp

    proxy["packet-encoding"] = "xudp"

    return proxy


def decode_subscription(data: str) -> list[str]:
    """Декодирует base64 подписку в список VLESS URL."""
    decoded = base64.b64decode(data.strip()).decode("utf-8")
    lines = [line.strip() for line in decoded.strip().split("\n") if line.strip()]
    return lines


def convert(input_data: str) -> dict:
    """Конвертирует base64 подписку в Clash proxy-provider формат."""
    urls = decode_subscription(input_data)
    proxies = []
    for url in urls:
        proxy = parse_vless_url(url)
        if proxy:
            proxies.append(proxy)
    return {"proxies": proxies}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Convert VLESS subscription to Clash YAML")
    parser.add_argument("output", help="Output YAML file path")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Subscription URL to download")
    group.add_argument("--file", help="Local file with raw base64 subscription data")
    args = parser.parse_args()

    if args.url:
        import urllib.request
        req = urllib.request.Request(args.url, headers={"User-Agent": "clash.meta"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_data = resp.read().decode("utf-8")
    else:
        with open(args.file) as f:
            raw_data = f.read()

    result = convert(raw_data)

    with open(args.output, "w") as f:
        yaml.dump(result, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"Converted {len(result['proxies'])} proxies → {args.output}")
    for p in result["proxies"]:
        print(f"  - {p['name']} ({p['server']}:{p['port']})")


if __name__ == "__main__":
    main()
