#!/usr/bin/env python3
import sys, os, sqlite3, re, base64, socket, json, time, threading, random, urllib.parse
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "anime.db")
ANSLAYER_BASE = "https://anslayer.com/anime/public/"
WIT = "https://witanime.you"
YONA_KEY = "23a97133-caf3-4eb4-9466-93d0a4ff8198"
CLIENT_ID = "android-app2"
CLIENT_SEC = "7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

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

def make_request(url, method="GET", data=None, retries=5):
    headers = {"User-Agent": UA}
    if "anslayer.com" in url:
        headers["Client-Id"] = CLIENT_ID
        headers["Client-Secret"] = CLIENT_SEC
        headers["Accept"] = "application/json"
    
    for attempt in range(1, retries + 1):
        try:
            if method == "POST":
                r = requests.post(url, data=data, headers=headers, impersonate="chrome124", timeout=20)
            else:
                r = requests.get(url, headers=headers, impersonate="chrome124", timeout=20)
            
            if r.status_code in (200, 404):
                return r
            elif r.status_code == 429:
                time.sleep(1)
                continue
        except Exception:
            time.sleep(0.5)
    return None

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
        qg = "FHD" if any(x in ql for x in ("FHD","خارقة")) else "HD" if any(x in ql for x in ("HD","عالية")) else "SD" if any(x in ql for x in ("SD","متوسطة")) else "4K" if "4K" in ql else "SD"
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

def resolve_anime3rb_episode(anime_name, ep_num):
    tkn = str(int(ep_num)) if ep_num.is_integer() else str(ep_num)
    slug = generate_slug(anime_name)
    return [("Multi-quality", f"https://anime3rb.com/episode/{slug}/{tkn}")]

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

def scrape_wit_servers(conn, aid, slug, ep_num):
    tkn = str(int(ep_num)) if ep_num.is_integer() else str(ep_num)
    candidates = [
        f"{WIT}/episode/{slug}-%D8%A7%D9%84%D8%AD%D9%84%D9%82%D8%A9-{tkn}/",
        f"{WIT}/episode/{slug}-{tkn}/",
    ]
    cur = conn.cursor()
    names = cur.execute("SELECT anime_name, anime_english_title FROM animes WHERE anime_id = ?", (aid,)).fetchone()
    if names:
        for name in names:
            if name:
                alt_slug = generate_slug(name)
                if alt_slug and alt_slug != slug:
                    candidates.append(f"{WIT}/episode/{alt_slug}-%D8%A7%D9%84%D8%AD%D9%84%D9%82%D8%A9-{tkn}/")
            
    for url in candidates:
        r = fetch(url, retries=1)
        if r and r.status_code == 200:
            if re.search(r'(?:var\s+)?_z[HX]\s*=\s*"[^"]+"', r.text):
                return r.text
    return None

def main():
    print("Starting Daily Sync Refresher...")
    
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}. Run GLOBAL.py first.")
        sys.exit(1)
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Phase 0: Sync Weekly Release Schedule
    print("Syncing release schedule...")
    params = {"list_type": "schedule"}
    data = make_request(f"{ANSLAYER_BASE}animes/get-published-animes?json={urllib.parse.quote(json.dumps(params))}")
    if data and data.json().get("response"):
        days_map = {
            'Saturday': 'السبت', 'Sunday': 'الأحد', 'Monday': 'الإثنين',
            'Tuesday': 'الثلاثاء', 'Wednesday': 'الأربعاء',
            'Thursday': 'الخميس', 'Friday': 'الجمعة'
        }
        updated = 0
        schedule_data = data.json()["response"].get("data", {})
        for day_en, day_ar in days_map.items():
            day_anime = schedule_data.get(day_en) or schedule_data.get(day_ar) or []
            for item in day_anime:
                aid = item.get('anime_id')
                if aid:
                    cur.execute("UPDATE animes SET anime_release_day=? WHERE anime_id=?", (day_en, int(aid)))
                    updated += cur.rowcount
        conn.commit()
        print(f"Updated release day for {updated} airing anime entries.")
        
    # Phase 1: Sync filters
    print("Refreshing filters/dropdowns...")
    r = make_request(f"{ANSLAYER_BASE}animes/get-dropdowns")
    if r and r.json().get("response"):
        counts = {"anime_genres": 0, "anime_studio_ids": 0, "anime_release_years": 0}
        for key in counts:
            items = r.json()["response"].get(key, {}).get("data", [])
            for item in items:
                cur.execute("INSERT OR REPLACE INTO dropdowns (id, type, label, option) VALUES (?,?,?,?)",
                            (str(item.get("value")), key, str(item.get("option")), str(item.get("option"))))
        conn.commit()

    # Phase 2: Sweep Catalog for new/updated entries (full sweep)
    print("Sweeping full catalog for new/updated entries...")
    offset = 0
    total_new = 0
    total_updates = 0
    new_aids = []
    while True:
        params = {"list_type": "anime_list", "_limit": 100, "_offset": offset}
        url_params = urllib.parse.quote(json.dumps(params))
        res = make_request(f"{ANSLAYER_BASE}animes/get-published-animes?json={url_params}")
        if not res or not res.json().get("response", {}).get("data"):
            break
        batch = res.json()["response"]["data"]
        for a in batch:
            aid = int(a["anime_id"])
            exists = cur.execute("SELECT anime_id FROM animes WHERE anime_id = ?", (aid,)).fetchone()
            if exists:
                cur.execute("UPDATE animes SET anime_status=?, anime_rating=? WHERE anime_id=?", 
                            (a.get("anime_status"), a.get("anime_rating"), aid))
                total_updates += 1
            else:
                slug = generate_slug(a.get("anime_english_title") or a.get("anime_name")) or f"anime-{aid}"
                cur.execute("""INSERT INTO animes (
                    anime_id, anime_name, anime_english_title, anime_slug, anime_type, anime_status,
                    anime_season, anime_release_year, anime_age_rating, anime_rating, anime_rating_user_count,
                    anime_description, anime_cover_image_url, anime_cover_image_full_url, anime_banner_image_url,
                    anime_trailer_url, anime_release_day, anime_updated_at, anime_created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'','','','','','','')""", (
                    aid, a.get("anime_name"), a.get("anime_english_title"), slug, a.get("anime_type"),
                    a.get("anime_status"), a.get("anime_season"), a.get("anime_release_year"), a.get("anime_age_rating"),
                    a.get("anime_rating"), a.get("anime_rating_user_count"), a.get("anime_description")
                ))
                total_new += 1
                new_aids.append(aid)
        conn.commit()
        if len(batch) < 100: break
        offset += 100
    print(f"  Sweep complete: {total_new} new anime added, {total_updates} statuses updated.")

    # Phase 2b: Deep-sync newly discovered anime
    if total_new > 0:
        print(f"  Deep-syncing {total_new} newly discovered anime for episodes & servers...")
        for aid in new_aids:
            det = make_request(f"{ANSLAYER_BASE}anime/get-anime-details?anime_id={aid}&fetch_episodes=Yes&more_info=No")
            if not det or not det.json().get("response"): continue
            r = det.json()["response"]
            eps = r.get("episodes", {}).get("data", []) if isinstance(r.get("episodes"), dict) else r.get("episodes", [])
            for ep in eps:
                ep_id = ep.get("episode_id")
                ep_num = ep.get("episode_number")
                if ep_id:
                    cur.execute("INSERT OR REPLACE INTO episodes (episode_id, anime_id, episode_name, episode_number, episode_rating, episode_created_at) VALUES (?,?,?,?,'','')",
                                (ep_id, aid, ep.get("episode_name"), ep_num))
                    for srv in ep.get("episode_urls", []):
                        srv_id = f"ans_{srv.get('episode_server_id')}"
                        cur.execute("INSERT OR REPLACE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                                    (srv.get("episode_url_id"), ep_id, srv_id, srv.get("episode_server_name"), srv.get("episode_url"), "active"))
            conn.commit()
        print(f"  Deep-synced {total_new} anime.")

    # Phase 3: Fetch recently updated episodes feed
    print("Syncing recently updated episodes feed...")
    params = {"list_type": "latest_updated_episode_new", "_limit": 100, "_offset": 0}
    data = make_request(f"{ANSLAYER_BASE}animes/get-published-animes?json={urllib.parse.quote(json.dumps(params))}")
    new_episodes_found = []
    if data and data.json().get("response", {}).get("data"):
        for item in data.json()["response"]["data"]:
            ep_id_str = item.get("latest_episode_id") or item.get("episode_id")
            if not item.get("anime_id") or not ep_id_str: continue
            aid = int(item["anime_id"])
            ep_id = int(ep_id_str)
            
            ep_name = item.get("latest_episode_name") or item.get("episode_name") or ""
            num_match = re.search(r'(\d+(?:\.\d+)?)', ep_name)
            ep_num = float(num_match.group(1)) if num_match else 0.0
            
            exists = cur.execute("SELECT 1 FROM episodes WHERE episode_id = ?", (ep_id,)).fetchone()
            if not exists:
                cur.execute("INSERT OR REPLACE INTO episodes (episode_id, anime_id, episode_name, episode_number, episode_rating, episode_created_at) VALUES (?,?,?,?,'','')",
                            (ep_id, aid, ep_name, ep_num))
                cur.execute("UPDATE animes SET anime_updated_at = datetime('now') WHERE anime_id = ?", (aid,))
                new_episodes_found.append((aid, ep_id, ep_num))
        conn.commit()
        print(f"Added {len(new_episodes_found)} new episodes from feed.")

    # Fetch servers for newly found episodes
    max_url_id = cur.execute("SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers").fetchone()[0]
    
    for aid, ep_id, ep_num in new_episodes_found:
        anime_row = cur.execute("SELECT anime_slug, anime_name FROM animes WHERE anime_id=?", (aid,)).fetchone()
        if not anime_row: continue
        slug, name = anime_row
        
        # 1. WitAnime Watch & Download
        html = scrape_wit_servers(conn, aid, slug, ep_num)
        if html:
            # Watch
            for w in decrypt_wit_watch(html):
                if w["t"] == "yonaplay":
                    yona_url = w["u"] + f"&apiKey={YONA_KEY}" if "embed.php?id=" in w["u"] else w["u"]
                    yona_res = make_request(yona_url)
                    if yona_res:
                        for ys in parse_yona_html(yona_res.text):
                            max_url_id += 1
                            cur.execute("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                                        (max_url_id, ep_id, f"wit_{ep_id}_yona_{ys['sn']}_{ys['q']}", f"Yona: {ys['sn']} - {ys['q']}", ys["u"], "active"))
                else:
                    # WitAnime watch names already include quality (e.g. "streamwish - SD", "videa - FHD")
                    # Don't append another quality suffix
                    max_url_id += 1
                    cur.execute("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                                (max_url_id, ep_id, f"wit_{ep_id}_watch_{w['n']}", w["n"], w["u"], "active"))
            # Download
            for d in decrypt_wit_dl(html):
                max_url_id += 1
                cur.execute("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                            (max_url_id, ep_id, f"wit_{ep_id}_dl_{d['n']}_{d['qg']}", f"Download: {d['n']} - {d['qg']}", d["u"], "active"))

        # 2. Anime3RB Resolving
        a3rb_res = resolve_anime3rb_episode(name, ep_num)
        for quality, direct_url in a3rb_res:
            max_url_id += 1
            cur.execute("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                        (max_url_id, ep_id, f"a3rb_{ep_id}_{quality}", f"Anime3RB - {quality}", direct_url, "active"))
                        
        conn.commit()

    # Phase 4: Backfill servers for feed episodes that exist but lack providers
    print("Backfilling servers for feed episodes missing providers...")
    feed_ep_ids = []
    if data and data.json().get("response", {}).get("data"):
        for item in data.json()["response"]["data"]:
            ep_id_str = item.get("latest_episode_id") or item.get("episode_id")
            if ep_id_str:
                feed_ep_ids.append(int(ep_id_str))
    
    if feed_ep_ids:
        placeholders = ",".join("?" * len(feed_ep_ids))
        lacking = cur.execute(f"""
            SELECT e.episode_id, e.episode_number, a.anime_id, a.anime_slug, a.anime_name,
                   CASE WHEN NOT EXISTS (SELECT 1 FROM episode_servers es WHERE es.episode_id = e.episode_id AND es.episode_server_id LIKE 'wit_%') THEN 1 ELSE 0 END as need_wit,
                   CASE WHEN NOT EXISTS (SELECT 1 FROM episode_servers es WHERE es.episode_id = e.episode_id AND es.episode_server_name LIKE 'Anime3RB%') THEN 1 ELSE 0 END as need_a3rb
            FROM episodes e
            JOIN animes a ON e.anime_id = a.anime_id
            WHERE e.episode_id IN ({placeholders})
              AND (NOT EXISTS (SELECT 1 FROM episode_servers es WHERE es.episode_id = e.episode_id AND es.episode_server_id LIKE 'wit_%')
                   OR NOT EXISTS (SELECT 1 FROM episode_servers es WHERE es.episode_id = e.episode_id AND es.episode_server_name LIKE 'Anime3RB%'))
        """, feed_ep_ids).fetchall()
        
        print(f"  Found {len(lacking)} feed episodes needing server backfill")
        for ep_id, ep_num, aid, slug, anime_name, need_wit, need_a3rb in lacking:
            if need_wit:
                html = scrape_wit_servers(conn, aid, slug, ep_num)
                if html:
                    for w in decrypt_wit_watch(html):
                        if w["t"] == "yonaplay":
                            yona_url = w["u"] + f"&apiKey={YONA_KEY}" if "embed.php?id=" in w["u"] else w["u"]
                            yona_res = make_request(yona_url)
                            if yona_res:
                                for ys in parse_yona_html(yona_res.text):
                                    max_url_id += 1
                                    cur.execute("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                                                (max_url_id, ep_id, f"wit_{ep_id}_yona_{ys['sn']}_{ys['q']}", f"Yona: {ys['sn']} - {ys['q']}", ys["u"], "active"))
                        else:
                            max_url_id += 1
                            cur.execute("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                                        (max_url_id, ep_id, f"wit_{ep_id}_watch_{w['n']}", w["n"], w["u"], "active"))
                    for d in decrypt_wit_dl(html):
                        max_url_id += 1
                        cur.execute("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                                    (max_url_id, ep_id, f"wit_{ep_id}_dl_{d['n']}_{d['qg']}", f"Download: {d['n']} - {d['qg']}", d["u"], "active"))
            if need_a3rb:
                a3rb_res = resolve_anime3rb_episode(anime_name, ep_num)
                for quality, direct_url in a3rb_res:
                    max_url_id += 1
                    cur.execute("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                                (max_url_id, ep_id, f"a3rb_{ep_id}_{quality}", f"Anime3RB - {quality}", direct_url, "active"))
            conn.commit()
        print(f"  Backfill complete for {len(lacking)} episodes")

    conn.close()
    print("Daily sync completed successfully.")

if __name__ == "__main__":
    main()
