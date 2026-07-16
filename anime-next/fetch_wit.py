#!/usr/bin/env python3
import sys, json, base64, re, urllib.parse
from curl_cffi import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def fetch(url):
    try:
        r = requests.get(url, impersonate="chrome124", headers={"User-Agent": UA, "Referer": "https://www.google.com/"}, timeout=15)
        if r.status_code == 200:
            print(r.text)
            return True
        print("", file=sys.stderr)
        return False
    except Exception as e:
        print(str(e), file=sys.stderr)
        return False

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else ""
    if url:
        success = fetch(url)
        if not success:
            sys.exit(1)
    else:
        print("Usage: fetch_wit.py <url>", file=sys.stderr)
        sys.exit(1)
