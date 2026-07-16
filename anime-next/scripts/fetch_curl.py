#!/usr/bin/env python3
import sys
import json
import argparse
from curl_cffi import requests

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--port', type=int)
    parser.add_argument('--post', action='store_true')
    parser.add_argument('--body', default='')
    args = parser.parse_args()

    proxies = {}
    if args.port:
        proxies = {
            "http": f"socks5://127.0.0.1:{args.port}",
            "https": f"socks5://127.0.0.1:{args.port}"
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    try:
        if args.post:
            # Anslayer expects form data for POST
            data = {}
            if args.body:
                data = {"json": args.body}
            r = requests.post(
                args.url,
                data=data,
                headers=headers,
                proxies=proxies,
                impersonate="chrome124",
                timeout=15
            )
        else:
            r = requests.get(
                args.url,
                headers=headers,
                proxies=proxies,
                impersonate="chrome124",
                timeout=15
            )

        print(json.dumps({
            "status": r.status_code,
            "text": r.text
        }))
    except Exception as e:
        print(json.dumps({
            "status": 500,
            "error": str(e)
        }))

if __name__ == "__main__":
    main()
