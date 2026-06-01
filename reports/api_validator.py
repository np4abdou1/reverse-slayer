#!/usr/bin/env python3
"""Anime Slayer API Validation Script"""
import requests, json, sys, urllib3
urllib3.disable_warnings()

BASE = "https://anslayer.com/anime/public/"
HEADERS = {
    "Client-Id": "android-app2",
    "Client-Secret": "7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Linux; Android 4.4.2; Nexus 4 Build/KOT49H) AppleWebKit/537.36"
}

tests = [
    ("GET", "configs/get-android-config", None, 200),
    ("GET", "configs/check-server", None, 200),
    ("GET", "animes/get-anime-dropdowns", None, 200),
    ("POST", "oauth/login", {"username":"x@x.com","password":"x","device_id":"x"}, 422),
    ("GET", "user/get-top-contributors", None, 200),
    ("GET", "news/get-published-news", {"json": '{"list_type":"all","limit":1}'}, 200),
]

failed = 0
for method, path, data, expected in tests:
    url = BASE + path
    try:
        if method == "GET":
            r = requests.get(url, params=data, headers=HEADERS, timeout=15, verify=False)
        else:
            r = requests.post(url, data=data, headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"}, timeout=15, verify=False)
        status = "PASS" if r.status_code == expected else f"FAIL(expected={expected},got={r.status_code})"
        if "FAIL" in status: failed += 1
        print(f"[{status}] {method} {path} -> {r.status_code}")
    except Exception as e:
        print(f"[ERROR] {method} {path} -> {e}")
        failed += 1

print(f"\n{'='*40}\nResults: {len(tests)-failed}/{len(tests)} passed")
sys.exit(failed)
