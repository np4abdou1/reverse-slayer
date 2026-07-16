#!/usr/bin/env python3
import subprocess
import time
import os
import sys
import socket

TOR_PORTS = list(range(9050, 9060))

def is_port_open(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    res = s.connect_ex(("127.0.0.1", port))
    s.close()
    return res == 0

def main():
    print("Checking Tor ports...")
    
    # We want to make sure ports 9050 to 9059 are running.
    # If 9050 is already run by system service, we keep it.
    # For others, we start them.
    for p in TOR_PORTS:
        if is_port_open(p):
            print(f"  Port {p} is already open/active.")
            continue
            
        conf_path = f"/tmp/tor-{p}.conf"
        data_dir = f"/tmp/tor-data-{p}"
        os.makedirs(data_dir, exist_ok=True)
        
        with open(conf_path, "w") as f:
            f.write(f"SocksPort 127.0.0.1:{p}\n")
            f.write(f"DataDirectory {data_dir}\n")
            f.write("CookieAuthentication 0\n")
            f.write("Log notice file /dev/null\n")
            
        print(f"  Starting Tor daemon on SocksPort {p}...")
        try:
            subprocess.Popen(
                ["tor", "-f", conf_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"  Failed to start Tor on port {p}: {e}")

    # Wait a bit for them to initialize
    print("Waiting 6 seconds for Tor proxies to bootstrap...")
    time.sleep(6)
    
    active = [p for p in TOR_PORTS if is_port_open(p)]
    print(f"Tor probe finished. Active SOCKS5 ports: {active}")

if __name__ == "__main__":
    main()
