#!/usr/bin/env python3
import sys
import os
import time
import json
import sqlite3
import re
import socket
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
import base64
from curl_cffi import requests
import httpx, threading, random

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "anime.db")
ANSLAYER_BASE = "https://anslayer.com/anime/public/"
WIT = "https://witanime.you"
YONA_KEY = "23a97133-caf3-4eb4-9466-93d0a4ff8198"
CLIENT_ID = "android-app2"
CLIENT_SEC = "7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

PROXY_PORTS = [40000, 9050, 9051, 9052, 9053, 9054, 9055, 9056, 9057, 9058, 9059]
active_ports = []
current_proxy_idx = 0

def is_port_open(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    res = s.connect_ex(("127.0.0.1", port))
    s.close()
    return res == 0

def setup_proxies():
    global active_ports
    active = []
    for port in PROXY_PORTS:
        if is_port_open(port):
            active.append(port)
    active_ports = active if active else [40000, 9050]
    print(f"Active proxy ports: {active_ports}")

def get_next_proxy():
    global current_proxy_idx
    if not active_ports:
        return None
    port = active_ports[current_proxy_idx]
    current_proxy_idx = (current_proxy_idx + 1) % len(active_ports)
    return port

# --- Tor / httpx networking ---
TOR_PORTS = [9050, 9051, 9052, 9053, 9054, 9055, 9056, 9057, 9058, 9059]
_ep_clients = {}
_cl_lock = threading.Lock()

def _new_circuit(port):
    try:
        s = socket.socket(); s.settimeout(2)
        s.connect(("127.0.0.1", port))
        s.sendall(b"AUTHENTICATE\r\nSIGNAL NEWNYM\r\nQUIT\r\n")
        s.close()
    except: pass

def _pick():
    good = [p for p in TOR_PORTS if socket.socket().connect_ex(('127.0.0.1', p)) == 0]
    return random.choice(good) if good else TOR_PORTS[0]

def _get_client(referer=None):
    tid = threading.get_ident()
    with _cl_lock:
        if tid not in _ep_clients:
            t = httpx.HTTPTransport(proxy=f"socks5://127.0.0.1:{_pick()}")
            headers = {"User-Agent": UA}
            if referer: headers["Referer"] = referer
            _ep_clients[tid] = httpx.Client(transport=t, headers=headers, timeout=30, follow_redirects=True)
    return _ep_clients[tid]

def _drop():
    tid = threading.get_ident()
    with _cl_lock:
        c = _ep_clients.pop(tid, None)
    if c:
        try: c.close()
        except: pass

def fetch(url, retries=4):
    for attempt in range(retries):
        try:
            r = _get_client().get(url)
            if r.status_code == 200: return r
            if r.status_code == 404: return r
            if r.status_code in (403, 429) or "Just a moment" in (r.text or ""):
                _new_circuit(_pick()); _drop()
                time.sleep(1 + attempt)
                continue
        except:
            _drop(); time.sleep(0.5 + attempt * 0.5)
    return None

def make_request(url, method="GET", data=None, use_proxy=True, retries=5):
    headers = {"User-Agent": UA}
    if "anslayer.com" in url:
        headers["Client-Id"] = CLIENT_ID
        headers["Client-Secret"] = CLIENT_SEC
        headers["Accept"] = "application/json"
    
    for attempt in range(1, retries + 1):
        port = get_next_proxy() if use_proxy else None
        proxies = {}
        if port:
            if port == 40000:
                proxies = {"http": "http://127.0.0.1:40000", "https": "http://127.0.0.1:40000"}
            else:
                proxies = {"http": f"socks5://127.0.0.1:{port}", "https": f"socks5://127.0.0.1:{port}"}
        try:
            if method == "POST":
                r = requests.post(url, data=data, headers=headers, proxies=proxies, impersonate="chrome124", timeout=20)
            else:
                r = requests.get(url, headers=headers, proxies=proxies, impersonate="chrome124", timeout=20)
            
            if r.status_code == 200:
                return r
            elif r.status_code == 429:
                time.sleep(1)
                continue
        except Exception:
            time.sleep(0.5)
    return None

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS dropdowns (id TEXT PRIMARY KEY, type TEXT, label TEXT, option TEXT)")
    cur.execute("""CREATE TABLE IF NOT EXISTS animes (
        anime_id INTEGER PRIMARY KEY, anime_name TEXT, anime_english_title TEXT, anime_slug TEXT,
        anime_type TEXT, anime_status TEXT, anime_season TEXT, anime_release_year TEXT,
        anime_age_rating TEXT, anime_rating TEXT, anime_rating_user_count TEXT, anime_description TEXT,
        anime_cover_image_url TEXT, anime_cover_image_full_url TEXT, anime_banner_image_url TEXT,
        anime_trailer_url TEXT, anime_release_day TEXT, anime_updated_at TEXT, anime_created_at TEXT,
        just_info TEXT, mal_id INTEGER, mal_score REAL, mal_image TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS episodes (
        episode_id INTEGER PRIMARY KEY, anime_id INTEGER NOT NULL, episode_name TEXT, episode_number REAL,
        episode_rating TEXT, episode_created_at TEXT, skip_from INTEGER DEFAULT 0, skip_to INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS episode_servers (
        episode_url_id INTEGER PRIMARY KEY, episode_id INTEGER NOT NULL, episode_server_id TEXT,
        episode_server_name TEXT, episode_url TEXT, episode_server_status TEXT,
        UNIQUE(episode_id, episode_server_id)
    )""")
    cur.execute("CREATE TABLE IF NOT EXISTS anime_genres (anime_id INTEGER, genre_id TEXT, genre_name TEXT, UNIQUE(anime_id, genre_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS anime_studios (anime_id INTEGER, studio_id TEXT, studio_name TEXT, UNIQUE(anime_id, studio_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS recommendations (anime_id INTEGER, recommended_anime_id INTEGER, recommended_anime_name TEXT, recommended_anime_cover_image_url TEXT, UNIQUE(anime_id, recommended_anime_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS anime_characters (character_id INTEGER PRIMARY KEY, anime_id INTEGER, character_name TEXT, character_image_url TEXT, character_role TEXT)")
    conn.commit()
    conn.close()

def generate_slug(name):
    if not name: return ""
    s = name.lower()
    s = s.replace('ä', 'a').replace('æ', 'a').replace('ë', 'e').replace('é', 'e').replace('è', 'e').replace('ê', 'e')
    s = s.replace('ï', 'i').replace('í', 'i').replace('ì', 'i').replace('î', 'i')
    s = s.replace('ö', 'o').replace('ó', 'o').replace('ò', 'o').replace('ô', 'o').replace('ø', 'o')
    s = s.replace('ü', 'u').replace('ú', 'u').replace('ù', 'u').replace('û', 'u')
    s = s.replace('ñ', 'n').replace('ç', 'c').replace('ß', 'ss').replace('â', 'a')
    s = re.sub(r'\s*\([^)]*\)\s*$', '', s)
    s = re.sub(r'[^a-z0-9\u0600-\u06ff\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s

def clean_title(s):
    if not s: return ""
    s = s.lower().replace('-', ' ').strip()
    s = re.sub(r'\s*\([^)]*\)\s*$', '', s)
    return re.sub(r'[^a-z0-9\u0600-\u06ff]', '', s)

# --- SCRAPERS ---
def decrypt_wit_watch(html):
    zx = re.search(r'(?:var\s+)?_z[HX]\s*=\s*"([^"]+)"', html)
    zk = re.search(r'(?:var\s+)?_z[WK]\s*=\s*"([^"]+)"', html)
    if not zx or not zk: return []
    try:
        rr = json.loads(base64.b64decode(zx.group(1)).decode())
        cr = json.loads(base64.b64decode(zk.group(1)).decode())
    except Exception: return []
    names = dict(re.findall(r'<a[^>]*data-server-id="(\d+)"[^>]*>([\s\S]*?)</a>', html))
    out = []
    for i, e in enumerate(rr):
        try:
            raw = re.sub(r'[^A-Za-z0-9+/=]', "", e[::-1])
            u = base64.b64decode(raw).decode()
            idx = int(base64.b64decode(cr[i]["k"]).decode())
            off = cr[i]["d"][idx]
            if off > 0: u = u[:-off]
            if u.strip().lstrip("/").startswith("//"): u = "https:" + u.strip().lstrip("/")
            n = re.sub(r'<[^>]+>', "", names.get(str(i), "")).strip()
            t = "yonaplay" if "yonaplay" in u.lower() else "direct"
            out.append({"i": i, "n": n, "t": t, "u": u})
        except Exception: pass
    return out

def decrypt_wit_dl(html):
    _m = re.search(r'(?:window\.|var\s+)?_m\s*=\s*(.*?);', html)
    _t = re.search(r'(?:window\.|var\s+)?_t\s*=\s*(.*?);', html)
    _s = re.search(r'(?:window\.|var\s+)?_s\s*=\s*(.*?);', html)
    if not _m or not _t or not _s: return []
    try:
        mv = json.loads(_m.group(1))
        tv = json.loads(_t.group(1))
        sv = json.loads(_s.group(1))
        secret = base64.b64decode(mv["r"])
        n = int(tv["l"])
    except Exception: return []
    
    qmap = {}
    for ul in re.findall(r'<ul class="quality-list">(.*?)</ul>', html, re.DOTALL):
        li = re.search(r'<li>(.*?)</li>', ul)
        if not li: continue
        ql = li.group(1).strip()
        qg = "SD" if any(x in ql for x in ("SD","متوسطة")) else "HD" if any(x in ql for x in ("HD","عالية")) else "FHD" if any(x in ql for x in ("FHD","خارقة")) else "4K" if "4K" in ql else "SD"
        for a in re.findall(r'<a[^>]*data-index="(\d+)"[^>]*>.*?<span class="notice">(.*?)</span>', ul, re.DOTALL):
            qmap[int(a[0])] = (a[1].strip(), qg)
            
    out = []
    for i in range(n):
        pm = re.search(rf'(?:window\.|var\s+)?_p{i}\s*=\s*(.*?);', html)
        if not pm: continue
        try:
            pd = json.loads(pm.group(1))
            sb = bytes.fromhex(sv[i])
            sd = bytearray(sb[j] ^ secret[j % len(secret)] for j in range(len(sb)))
            seq = json.loads(sd.decode("utf-8", errors="ignore"))
            chunks = [bytes.fromhex(h) for h in pd]
            dec = [bytearray(chunks[j][k] ^ secret[k % len(secret)] for k in range(len(chunks[j]))) for j in range(len(chunks))]
            arr = [None] * len(seq)
            for p2, v in enumerate(seq): arr[v] = dec[p2].decode("utf-8", errors="ignore")
            u = "".join(arr)
            if u.strip().lstrip("/").startswith("//"): u = "https:" + u.strip().lstrip("/")
            q = qmap.get(i, ("unknown", "SD"))
            out.append({"i": i, "n": q[0], "qg": q[1], "u": u})
        except Exception: pass
    return out

def parse_yona_html(html):
    _OD_RE = re.compile(r'<div class="OD([^"]*)">([\s\S]*?)</div>\s*(?=<div class="OD|</div>|$)', re.DOTALL)
    _LI_RE = re.compile(r"go_to_player\('([^']+)'\)[\s\S]*?<span>([\s\S]*?)</span>[\s\S]*?<p>([\s\S]*?)</p>", re.DOTALL)
    out = []
    for od_m in _OD_RE.finditer(html):
        cls, body = od_m.group(1), od_m.group(2)
        lang = "SUB2" if "OD_SUB2" in cls else "DUB" if "OD_DUB" in cls else "SUB"
        for li in _LI_RE.finditer(body):
            b64, sn = li.group(1), re.sub(r'<[^>]+>', '', li.group(2)).strip()
            qr = re.sub(r'<[^>]+>', '', li.group(3)).strip().rstrip("- ").strip()
            qr = {"1080p":"FHD","720p":"HD","480p":"SD","360p":"SD"}.get(qr, qr)
            try:
                pad = b64 + "=" * ((4 - len(b64) % 4) % 4)
                inner = base64.urlsafe_b64decode(pad).decode()
                out.append({"sn": sn, "q": qr, "l": lang, "u": inner})
            except Exception: continue
    return out

def resolve_anime3rb_episode(page_url):
    sess = requests.Session(impersonate='chrome')
    sess.proxies = {'https': 'http://127.0.0.1:40000', 'http': 'http://127.0.0.1:40000'}
    try:
        r = sess.get(page_url, timeout=15)
        player_url = None
        for m in re.finditer(r'wire:snapshot=(["\'])([^"\']+?)\1', r.text):
            decoded = m.group(2).replace('&quot;', '"').replace('&amp;', '&')
            if 'video_url' in decoded:
                player_url = json.loads(decoded)['data']['video_url']
                break
        if not player_url: return []
        
        sess2 = requests.Session(impersonate='chrome')
        sess2.proxies = {'https': 'socks5://127.0.0.1:9050', 'http': 'socks5://127.0.0.1:9050'}
        rp = sess2.get(player_url, headers={'Referer': player_url.split('?')[0]}, timeout=15)
        
        sources = []
        for vs in re.findall(r'var video_sources = (\[.*?\]);', rp.text, re.DOTALL):
            sources = json.loads(vs.replace('\\/', '/'))
            break
            
        results = []
        for src in sources:
            if src.get('premium') or not src.get('src'): continue
            redir = sess2.get(src['src'], allow_redirects=False, timeout=10)
            loc = redir.headers.get('location')
            if loc:
                label = src.get('label', 'unknown')
                quality = re.sub(r'[^\dp]', '', label) or 'FHD'
                results.append((quality, loc))
        return results
    except Exception:
        return []

# --- MAIN RUNNER ---
def run_global():
    print("Starting Global Extraction from scratch...")
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. Dropdowns
    print("Fetching dropdown filters...")
    r = make_request(f"{ANSLAYER_BASE}animes/get-anime-dropdowns")
    if r and r.json().get("response"):
        counts = {"anime_genres": 0, "anime_studio_ids": 0, "anime_release_years": 0}
        for key in counts:
            items = r.json()["response"].get(key, {}).get("data", [])
            for item in items:
                cur.execute("INSERT OR REPLACE INTO dropdowns (id, type, label, option) VALUES (?,?,?,?)",
                            (str(item.get("value")), key, str(item.get("option")), str(item.get("option"))))
        conn.commit()
        
    # 2. Shallow crawl
    print("Crawling shallow catalog...")
    offset = 0
    while True:
        params = {"list_type": "anime_list", "_limit": 100, "_offset": offset}
        url_params = urllib.parse.quote(json.dumps(params))
        res = make_request(f"{ANSLAYER_BASE}animes/get-published-animes?json={url_params}")
        if not res or not res.json().get("response", {}).get("data"):
            break
        animes = res.json()["response"]["data"]
        print(f"  Batch offset: {offset}, count: {len(animes)}")
        for a in animes:
            aid = int(a["anime_id"])
            slug = generate_slug(a.get("anime_english_title") or a.get("anime_name")) or f"anime-{aid}"
            cur.execute("""INSERT OR REPLACE INTO animes (
                anime_id, anime_name, anime_english_title, anime_slug, anime_type, anime_status,
                anime_season, anime_release_year, anime_age_rating, anime_rating, anime_rating_user_count,
                anime_description, anime_cover_image_url, anime_cover_image_full_url, anime_banner_image_url,
                anime_trailer_url, anime_release_day, anime_updated_at, anime_created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'','','','','','','')""", (
                aid, a.get("anime_name"), a.get("anime_english_title"), slug, a.get("anime_type"),
                a.get("anime_status"), a.get("anime_season"), a.get("anime_release_year"), a.get("anime_age_rating"),
                a.get("anime_rating"), a.get("anime_rating_user_count"), a.get("anime_description")
            ))
        conn.commit()
        if len(animes) < 100: break
        offset += 100

    # 3. Deep extraction (episodes & servers)
    all_animes = cur.execute("SELECT anime_id, anime_slug, anime_name, anime_english_title FROM animes ORDER BY anime_id DESC").fetchall()
    print(f"Deep syncing {len(all_animes)} animes...")
    
    max_url_id = 1
    
    def sync_anime_worker(aid, slug, name, eng_title):
        nonlocal max_url_id
        res = make_request(f"{ANSLAYER_BASE}anime/get-anime-details?anime_id={aid}&fetch_episodes=Yes&more_info=Yes")
        if not res or not res.json().get("response"): return False
        r = res.json()["response"]
        
        # Insert genres/studios
        gids = str(r.get("anime_genre_ids", "")).split(",")
        gnames = str(r.get("anime_genres", "")).split(",")
        for idx, gid in enumerate(gids):
            if gid.strip():
                gname = gnames[idx].strip() if idx < len(gnames) else ""
                cur.execute("INSERT OR IGNORE INTO anime_genres (anime_id, genre_id, genre_name) VALUES (?,?,?)", (aid, gid.strip(), gname))
        
        more_info = r.get("more_info_result") or {}
        if more_info.get("anime_studio_ids"):
            sids = str(more_info["anime_studio_ids"]).split(",")
            snames = str(more_info.get("anime_studios", "")).split(",")
            for idx, sid in enumerate(sids):
                if sid.strip():
                    sname = snames[idx].strip() if idx < len(snames) else ""
                    cur.execute("INSERT OR IGNORE INTO anime_studios (anime_id, studio_id, studio_name) VALUES (?,?,?)", (aid, sid.strip(), sname))
                    
        # Update details
        cur.execute("""UPDATE animes SET
            anime_english_title = ?, anime_age_rating = ?, anime_rating = ?, anime_rating_user_count = ?,
            anime_description = ?, anime_cover_image_full_url = ?, anime_banner_image_url = ?,
            anime_updated_at = ?, anime_created_at = ?, anime_release_day = ?, mal_score = ?
            WHERE anime_id = ?""",
            (r.get("anime_english_title"), r.get("anime_age_rating"), r.get("anime_rating"), r.get("anime_rating_user_count"),
             r.get("anime_description"), r.get("anime_cover_image_full_url"), r.get("anime_banner_image_url"),
             r.get("anime_updated_at"), r.get("anime_created_at"), r.get("anime_release_day"),
             float(more_info.get("score")) if more_info.get("score") else None, aid))
             
        eps = r.get("episodes", {}).get("data", []) if isinstance(r.get("episodes"), dict) else []
        for ep in eps:
            ep_id = int(ep["episode_id"])
            ep_num = float(ep.get("episode_number") or 0)
            cur.execute("""INSERT OR REPLACE INTO episodes (
                episode_id, anime_id, episode_name, episode_number, episode_rating, episode_created_at
            ) VALUES (?,?,?,?,?,?)""", (ep_id, aid, ep.get("episode_name"), ep_num, ep.get("episode_rating"), ep.get("episode_created_at")))
            
            # Anslayer default servers
            raw_servers = ep.get("episode_urls", [])
            if isinstance(raw_servers, dict):
                raw_servers = raw_servers.get("data", [])
            servers = raw_servers if isinstance(raw_servers, list) else []
            for srv in servers:
                srv_id = f"ans_{srv.get('episode_server_id')}"
                cur.execute("""INSERT OR REPLACE INTO episode_servers (
                    episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status
                ) VALUES (?,?,?,?,?,?)""", (
                    int(srv["episode_url_id"]), ep_id, srv_id, srv.get("episode_server_name"), srv.get("episode_url"), "active"
                ))
                max_url_id = max(max_url_id, int(srv["episode_url_id"]))
        return True

    # Multi-threaded deep sync
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(sync_anime_worker, row[0], row[1], row[2], row[3]): row for row in all_animes}
        for done, fut in enumerate(as_completed(futures), 1):
            if done % 100 == 0:
                conn.commit()
                print(f"  Processed {done}/{len(all_animes)} details")
    conn.commit()
    print("Global crawl completed. Base DB constructed.")
    conn.close()

if __name__ == "__main__":
    run_global()
