#!/usr/bin/env python3
import sys, os, sqlite3, re, base64, socket, json, time, threading, random, urllib.parse
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "anime.db")
WIT = "https://witanime.you"
YONA_KEY = "23a97133-caf3-4eb4-9466-93d0a4ff8198"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

TOR_PORTS = [9050, 9051, 9052, 9053, 9054, 9055, 9056, 9057, 9058, 9059]
good_ports = [p for p in TOR_PORTS if socket.socket().connect_ex(('127.0.0.1', p)) == 0]

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
    return random.choice(good_ports) if good_ports else TOR_PORTS[0]

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

def scrape_wit_servers(conn, aid, slug, ep_num, verbose=False):
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
                    break
    for url in candidates:
        r = fetch(url, retries=2)
        if r is None:
            if verbose: print(f"      -> {url.split('/')[-2][:45]} | TIMEOUT")
            continue
        if r.status_code == 404:
            if verbose: print(f"      -> {url.split('/')[-2][:45]} | 404")
            continue
        if r.status_code == 200:
            if re.search(r'(?:var\s+)?_z[HX]\s*=\s*"[^"]+"', r.text):
                if verbose: print(f"      -> {url.split('/')[-2][:45]} | 200 OK")
                return r.text
            else:
                if verbose: print(f"      -> {url.split('/')[-2][:45]} | 200 no data")
        else:
            if verbose: print(f"      -> {url.split('/')[-2][:45]} | HTTP {r.status_code}")
    return None

def main():
    print("Initializing Database Fixer...")
    if not os.path.exists(DB_PATH):
        print(f"Error: Database file not found at {DB_PATH}.")
        sys.exit(1)
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 0. Add indexes for performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_es_ep ON episode_servers(episode_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ep_aid ON episodes(anime_id)")
    conn.commit()
    
    # 1. Deduplicate table entries using temp tables for subsecond speed
    print("Deduplicating episodes...")
    cur.execute("SELECT MIN(rowid) FROM episodes GROUP BY episode_id")
    valid_ep_rids = [r[0] for r in cur.fetchall()]
    cur.execute("CREATE TEMP TABLE keep_ep_rowids(rid INTEGER PRIMARY KEY)")
    cur.executemany("INSERT INTO keep_ep_rowids VALUES (?)", [(r,) for r in valid_ep_rids])
    cur.execute("DELETE FROM episodes WHERE rowid NOT IN (SELECT rid FROM keep_ep_rowids)")
    print(f"Removed duplicate episodes. Rowcount: {cur.rowcount}")
    
    print("Deduplicating episode_servers...")
    cur.execute("SELECT MIN(rowid) FROM episode_servers GROUP BY episode_id, episode_server_id")
    valid_srv_rids = [r[0] for r in cur.fetchall()]
    cur.execute("CREATE TEMP TABLE keep_srv_rowids(rid INTEGER PRIMARY KEY)")
    cur.executemany("INSERT INTO keep_srv_rowids VALUES (?)", [(r,) for r in valid_srv_rids])
    cur.execute("DELETE FROM episode_servers WHERE rowid NOT IN (SELECT rid FROM keep_srv_rowids)")
    print(f"Removed duplicate servers. Rowcount: {cur.rowcount}")
    conn.commit()

    # 2. Find and Group/Prefix-group malformed server names
    print("Standardizing and formatting server name groupings...")
    cur.execute("""
        UPDATE episode_servers
        SET episode_server_name = 'Download: ' || episode_server_name || ' - HD'
        WHERE ((episode_url LIKE '%gofile.io%' OR episode_url LIKE '%workupload.com%' OR episode_url LIKE '%mega.nz/file%' OR episode_url LIKE '%mediafire.com%') 
          AND episode_server_name NOT LIKE 'Download:%')
    """)
    downloads_updated = cur.rowcount
    
    cur.execute("""
        UPDATE episode_servers
        SET episode_server_name = 'Yona: ' || episode_server_name || ' - FHD'
        WHERE ((episode_url LIKE '%yonaplay.net%' OR episode_server_id LIKE '%yona%')
          AND episode_server_name NOT LIKE 'Yona:%')
    """)
    yona_updated = cur.rowcount
    conn.commit()
    print(f"Standardized server name categories: {downloads_updated} downloads and {yona_updated} Yona servers updated.")

    # 2b. Fix corrupted double-quality watch server names (e.g. "streamwish - SD - FHD" -> "streamwish - SD")
    print("Fixing corrupted double-quality watch server names...")
    cur.execute("""
        UPDATE episode_servers
        SET episode_server_name = substr(episode_server_name, 1, length(episode_server_name) - 5)
        WHERE episode_server_id LIKE 'wit_%watch_%'
          AND episode_server_name LIKE '% - SD - FHD'
    """)
    sd_fixed = cur.rowcount
    cur.execute("""
        UPDATE episode_servers
        SET episode_server_name = substr(episode_server_name, 1, length(episode_server_name) - 5)
        WHERE episode_server_id LIKE 'wit_%watch_%'
          AND episode_server_name LIKE '% - HD - FHD'
    """)
    hd_fixed = cur.rowcount
    cur.execute("""
        UPDATE episode_servers
        SET episode_server_name = substr(episode_server_name, 1, length(episode_server_name) - 5)
        WHERE episode_server_id LIKE 'wit_%watch_%'
          AND episode_server_name LIKE '% - FHD - FHD'
    """)
    fhd_fixed = cur.rowcount
    # Catch Arabic-pattern names like "mega - FHD ياباني - FHD"
    cur.execute("""
        UPDATE episode_servers
        SET episode_server_name = substr(episode_server_name, 1, length(episode_server_name) - 5)
        WHERE episode_server_id LIKE 'wit_%watch_%'
          AND episode_server_name LIKE '% - % - FHD'
          AND episode_server_name NOT LIKE '% - SD - FHD'
          AND episode_server_name NOT LIKE '% - HD - FHD'
          AND episode_server_name NOT LIKE '% - FHD - FHD'
    """)
    arabic_fixed = cur.rowcount
    # Trim trailing spaces
    cur.execute("""
        UPDATE episode_servers
        SET episode_server_name = rtrim(episode_server_name)
        WHERE episode_server_name LIKE '% '
    """)
    spaces_fixed = cur.rowcount
    # Fix Yona: Anime3RB - {num} - FHD -> Yona: Anime3RB - {num}
    cur.execute("""
        UPDATE episode_servers
        SET episode_server_name = substr(episode_server_name, 1, length(episode_server_name) - 5)
        WHERE episode_server_name LIKE 'Yona: Anime3RB - % - FHD'
    """)
    yona_a3rb_fixed = cur.rowcount
    conn.commit()
    print(f"  Fixed corrupted names: {sd_fixed} SD, {hd_fixed} HD, {fhd_fixed} FHD, {arabic_fixed} Arabic, {spaces_fixed} trailing spaces, {yona_a3rb_fixed} Yona-A3RB")

    # 3. Backfill using WitAnime WP API for accurate matching
    print(f"Fetching WitAnime catalog via WP API...")
    wit_anime = {}
    page = 1
    while True:
        r = fetch(f'{WIT}/wp-json/wp/v2/anime?per_page=100&page={page}&_fields=id,slug,name,count')
        if not r or r.status_code != 200: break
        data = r.json()
        if not data: break
        for item in data:
            wit_anime[item['slug']] = {'id': item['id'], 'name': item['name'], 'count': item.get('count', 0)}
        page += 1
        time.sleep(0.3)
    
    print(f"  Fetched {len(wit_anime)} WitAnime anime")

    # Build match map: local_aid → wit_anime_data
    local_anime = cur.execute('SELECT anime_id, anime_name, anime_english_title, anime_slug FROM animes WHERE length(anime_slug) > 2').fetchall()
    
    matched = {}  # aid -> wit_data
    for aid, name, eng, slug in local_anime:
        for wslug, wdata in wit_anime.items():
            if wslug == slug or wslug == generate_slug(slug) or wslug == generate_slug(name) or (eng and wslug == generate_slug(eng)):
                matched[aid] = wdata
                break
    
    print(f"  Matched {len(matched)} local anime to WitAnime")

    # Fetch episode lists for matched anime via WP API
    print(f"  Fetching episode lists...")
    anime_ep_map = {}  # aid -> {ep_num: ep_url}
    
    def fetch_eps(aid, wit_id):
        ep_map = {}
        page = 1
        max_pages = 999
        while page <= max_pages:
            r = fetch(f'{WIT}/wp-json/wp/v2/episode?anime={wit_id}&per_page=100&page={page}&_fields=id,slug,title,link')
            if not r or r.status_code != 200: break
            if page == 1:
                max_pages = int(r.headers.get('X-WP-TotalPages', 1))
            for ep in r.json():
                title = ep.get('title', {}).get('rendered', '')
                link = ep.get('link', '')
                m = re.search(r'الحلقة\s*:?\s*(\d+(?:\.\d+)?)', title)
                if m:
                    try: ep_map[float(m.group(1))] = link
                    except: pass
            if page >= max_pages: break
            page += 1
        return (aid, ep_map if ep_map else None)
    
    futures = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        for aid, wdata in matched.items():
            futures[executor.submit(fetch_eps, aid, wdata['id'])] = aid
        done = 0
        for fut in as_completed(futures):
            aid, ep_map = fut.result()
            done += 1
            if ep_map: anime_ep_map[aid] = ep_map
            if done % 100 == 0: print(f"    Fetched episodes for {done}/{len(matched)} anime")
    
    print(f"  Built episode maps for {len(anime_ep_map)}/{len(matched)} anime")

    # Find episodes needing backfill that are in matched list
    matched_ids = ','.join(str(aid) for aid in anime_ep_map.keys())
    if not matched_ids:
        print("  No matched anime with episodes. Skipping backfill.")
    else:
        lacking = cur.execute(f'''
            SELECT e.episode_id, e.episode_number, e.anime_id
            FROM episodes e
            WHERE e.anime_id IN ({matched_ids})
              AND NOT EXISTS (SELECT 1 FROM episode_servers es WHERE es.episode_id = e.episode_id AND es.episode_server_id LIKE 'wit_%')
            ORDER BY e.episode_id DESC
            LIMIT 5000
        ''').fetchall()
        
        print(f"  Episodes to backfill: {len(lacking)}")
        print(f"  Resolving with 20 workers...")
        
        db_lock = threading.Lock()
        max_id = [cur.execute('SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers').fetchone()[0]]
        ok = [0]; fail = [0]; total = [0]
        
        def worker(row):
            ep_id, ep_num, aid = row
            ep_map = anime_ep_map.get(aid)
            if not ep_map: return (ep_id, aid, ep_num, False, 0, 'no_ep_map')
            
            ep_url = ep_map.get(ep_num)
            if not ep_url: return (ep_id, aid, ep_num, False, 0, 'ep_not_in_list')
            
            r = fetch(ep_url, retries=2)
            if not r or r.status_code != 200: return (ep_id, aid, ep_num, False, 0, f'fetch_{r.status_code if r else "fail"}')
            
            html = r.text
            if not re.search(r'_z[HX]', html): return (ep_id, aid, ep_num, False, 0, 'no_watch_data')
            
            results = []
            for w in decrypt_wit_watch(html):
                if w['t'] == 'yonaplay':
                    yu = w['u'] + f'&apiKey={YONA_KEY}' if 'embed.php?id=' in w['u'] else w['u']
                    yr = fetch(yu, retries=1)
                    if yr:
                        for ys in parse_yona_html(yr.text):
                            results.append((ep_id, f"wit_{ep_id}_yona_{ys['sn']}_{ys['q']}", f"Yona: {ys['sn']} - {ys['q']}", ys['u']))
                else:
                    results.append((ep_id, f"wit_{ep_id}_watch_{w['n']}", w['n'], w['u']))
            for d in decrypt_wit_dl(html):
                results.append((ep_id, f"wit_{ep_id}_dl_{d['n']}_{d['qg']}", f"Download: {d['n']} - {d['qg']}", d['u']))
            
            return (ep_id, aid, ep_num, True, len(results), 'ok', results)
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(worker, row): row for row in lacking}
            for fut in as_completed(futures):
                try:
                    result = fut.result()
                    ep_id, aid, ep_num, success, count, reason, *rest = result
                    with db_lock:
                        if success and rest:
                            for ep_id2, srv_id, srv_name, srv_url in rest[0]:
                                max_id[0] += 1
                                cur.execute("INSERT OR REPLACE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                                            (max_id[0], ep_id2, srv_id, srv_name, srv_url, "active"))
                            ok[0] += 1
                            print(f"  [{ok[0]+fail[0]}/{len(lacking)}] OK   | aid={aid} Ep {ep_num} | +{count} servers")
                        else:
                            fail[0] += 1
                            print(f"  [{ok[0]+fail[0]}/{len(lacking)}] FAIL | aid={aid} Ep {ep_num} | {reason}")
                        total[0] += 1
                        if total[0] % 100 == 0:
                            conn.commit()
                            print(f"  --- {ok[0]} ok, {fail[0]} fail, {total[0]}/{len(lacking)} ---")
                except Exception as e:
                    with db_lock:
                        fail[0] += 1; total[0] += 1
                        print(f"  [{total[0]}/{len(lacking)}] CRASH | {str(e)[:80]}")
        
        conn.commit()
        print(f"  Backfill complete: {ok[0]} ok, {fail[0]} fail")
        
        cur.execute('SELECT count(*) FROM episode_servers WHERE episode_server_name LIKE "%FHD%"')
        print(f'  FHD servers: {cur.fetchone()[0]}')
        cur.execute('SELECT count(*) FROM episode_servers WHERE episode_server_id LIKE "wit_%"')
        print(f'  Wit servers: {cur.fetchone()[0]}')
    
    # 4. Catalog integrity sweep — fix stale statuses from remote API
    print("Sweeping catalog for stale statuses...")
    import urllib.parse as ulib
    offset = 0
    status_fixes = 0
    while True:
        params = {"list_type": "anime_list", "_limit": 100, "_offset": offset}
        url_params = ulib.quote(json.dumps(params))
        port = _pick()
        t = httpx.HTTPTransport(proxy=f"socks5://127.0.0.1:{port}")
        with httpx.Client(transport=t, headers={"User-Agent": UA, "Client-Id": "android-app2", "Client-Secret": "7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd", "Accept": "application/json"}, timeout=20) as c:
            r = c.get(f"https://anslayer.com/anime/public/animes/get-published-animes?json={url_params}")
        if not r or not r.json().get("response", {}).get("data"):
            break
        batch = r.json()["response"]["data"]
        for a in batch:
            aid = int(a.get("anime_id", 0))
            remote_status = a.get("anime_status", "")
            if not aid or not remote_status: continue
            local = cur.execute("SELECT anime_status FROM animes WHERE anime_id = ?", (aid,)).fetchone()
            if local and local[0] != remote_status:
                cur.execute("UPDATE animes SET anime_status = ?, anime_rating = ? WHERE anime_id = ?",
                            (remote_status, a.get("anime_rating"), aid))
                status_fixes += 1
        conn.commit()
        if len(batch) < 100: break
        offset += 100
    print(f"  Fixed {status_fixes} stale anime statuses from remote catalog.")
    
    conn.close()
    print("Database Fixer run completed.")

if __name__ == "__main__":
    main()
