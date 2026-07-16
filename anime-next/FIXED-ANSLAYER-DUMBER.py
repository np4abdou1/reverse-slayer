#!/usr/bin/env python3
import sys
import os
import time
import json
import sqlite3
import re
import socket
import argparse
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests

# --- COLORS ---
class C:
    green = '\033[92m'
    yellow = '\033[93m'
    red = '\033[91m'
    cyan = '\033[96m'
    bold = '\033[1m'
    dim = '\033[2m'
    reset = '\033[0m'

# --- CONFIG ---
DB_PATH = "/home/ubuntu/Projects/reverse-slayer/anime-next/DATA_LOCAL/data/anime.db"
BASE = "https://anslayer.com/anime/public/"
CLIENT_ID = "android-app2"
CLIENT_SEC = "7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
CONCURRENCY = 15

# All SOCKS5 proxies
PROXY_PORTS = [40000, 9050, 9051, 9052, 9053, 9054, 9055, 9056, 9057, 9058, 9059]
active_ports = [40000, 9050]
current_proxy_idx = 0

def is_port_open(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    res = s.connect_ex(("127.0.0.1", port))
    s.close()
    return res == 0

def setup_tor_pool():
    print(f" {C.dim}➜{C.reset} Syncing and starting Tor proxy pool...")
    try:
        subprocess.run(["python3", "/home/ubuntu/Projects/reverse-slayer/anime-next/scripts/start_tor_pool.py"], check=True)
    except Exception as e:
        print(f" {C.red}✗{C.reset} Failed to start Tor pool: {e}")
        
    global active_ports
    active = []
    for port in PROXY_PORTS:
        if is_port_open(port):
            active.append(port)
    active_ports = active if active else [40000, 9050]
    print(f" {C.green}✓{C.reset} Active proxy ports: {', '.join(map(str, active_ports))}")

def get_next_proxy_port():
    global current_proxy_idx
    port = active_ports[current_proxy_idx]
    current_proxy_idx = (current_proxy_idx + 1) % len(active_ports)
    return port

# --- curl_cffi HTTP requester ---
def api_request(path, body=None, retries=12, use_proxy=True):
    url = path if path.startswith("http") else f"{BASE}{path}"
    port = get_next_proxy_port() if use_proxy else None
    
    headers = {
        "Accept": "application/json" if not ("sitemap" in url or url.endswith(".xml")) else "application/xml, text/xml",
        "User-Agent": UA
    }
    if "anslayer.com" in url or not path.startswith("http"):
        headers["Client-Id"] = CLIENT_ID
        headers["Client-Secret"] = CLIENT_SEC
    
    for attempt in range(1, retries + 1):
        proxies = {}
        if use_proxy and port:
            proxies = {
                "http": f"socks5://127.0.0.1:{port}",
                "https": f"socks5://127.0.0.1:{port}"
            }
        try:
            if body:
                r = requests.post(
                    url,
                    data={"json": json.dumps(body) if isinstance(body, (dict, list)) else body},
                    headers=headers,
                    proxies=proxies,
                    impersonate="chrome124",
                    timeout=20
                )
            else:
                r = requests.get(
                    url,
                    headers=headers,
                    proxies=proxies,
                    impersonate="chrome124",
                    timeout=20
                )
                
            if r.status_code == 429:
                if use_proxy:
                    port = get_next_proxy_port()
                    print(f" {C.yellow}⚠ Rate limited (429). Rotating proxy circuit ➜ Port {port}{C.reset}")
                else:
                    print(f" {C.yellow}⚠ Rate limited (429) on direct request. Retrying...{C.reset}")
                time.sleep(0.2)
                continue
                
            if r.status_code != 200:
                raise Exception(f"HTTP {r.status_code}")
                
            # If it is JSON, parse it, otherwise return plain text
            is_json = "json" in r.headers.get("content-type", "").lower() or (url.endswith("animes") or "get-" in url)
            if is_json and not (url.endswith(".xml") or "sitemap" in url):
                try:
                    data = r.json()
                except:
                    data = r.text
            else:
                data = r.text
                
            return {"data": data, "port": port or "Direct", "status": "SUCCESS"}
        except Exception as e:
            if attempt == retries:
                return {"data": None, "port": port or "Direct", "status": "FAIL", "error": str(e)}
            wait = min(1.0 * (2 ** attempt), 8.0)
            if use_proxy:
                port = get_next_proxy_port()
                print(f" {C.yellow}⚠ Error: {str(e)[:35]} on {url.split('/')[-1][:25]}… Rotate ➜ Port {port} (Retry {attempt}/{retries}){C.reset}")
            else:
                print(f" {C.yellow}⚠ Error: {str(e)[:35]} on {url.split('/')[-1][:25]}… Retrying direct (Retry {attempt}/{retries}){C.reset}")
            time.sleep(wait)
            
    return {"data": None, "port": port or "Direct", "status": "FAIL", "error": "Max retries reached"}

# --- HELPERS ---
def step(msg):
    print(f"\n {C.bold}{C.cyan}▶{C.reset}  {C.bold}{msg}{C.reset}")

def ok(msg):
    print(f"  {C.green}✓{C.reset}  {C.dim}{msg}{C.reset}")

def info(msg):
    print(f"  {C.cyan}•{C.reset} {msg}")

def generate_slug(name):
    if not name: return ""
    s = name.lower()
    # Transliterate basic characters
    s = s.replace('ä', 'a').replace('æ', 'a').replace('ë', 'e').replace('é', 'e').replace('è', 'e').replace('ê', 'e')
    s = s.replace('ï', 'i').replace('í', 'i').replace('ì', 'i').replace('î', 'i')
    s = s.replace('ö', 'o').replace('ó', 'o').replace('ò', 'o').replace('ô', 'o').replace('ø', 'o')
    s = s.replace('ü', 'u').replace('ú', 'u').replace('ù', 'u').replace('û', 'u')
    s = s.replace('ñ', 'n').replace('ç', 'c').replace('ß', 'ss').replace('â', 'a')
    # Strip parentheticals
    s = re.sub(r'\s*\([^)]*\)\s*$', '', s)
    # Strip non-alphanumeric/non-space
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s

def run_phase_0(db):
    step("Phase 0 — Syncing weekly release schedule …")
    res = api_request("animes/get-anime-dropdowns")
    if not res.get("data") or "response" not in res["data"]:
        print("Failed to fetch schedule data")
        return
        
    days = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    updated = 0
    cur = db.cursor()
    for day in days:
        params = {"list_type": "anime_list", "anime_release_day": day, "_limit": 100, "_offset": 0}
        url_params = urllib.parse.quote(json.dumps(params))
        data_res = api_request(f"animes/get-published-animes?json={url_params}")
        if data_res.get("data") and "response" in data_res["data"]:
            animes = data_res["data"]["response"].get("data", [])
            for a in animes:
                if a.get("anime_id"):
                    cur.execute("UPDATE animes SET anime_release_day = ? WHERE anime_id = ?", (day, int(a["anime_id"])))
                    updated += cur.rowcount
    db.commit()
    ok(f"Synced release days for {updated} currently airing anime")

def run_phase_1(db):
    step("Phase 1 — Fetching dropdowns (genres, studios, years) …")
    res = api_request("animes/get-anime-dropdowns")
    if not res.get("data") or "response" not in res["data"]:
        print("Failed to fetch dropdowns")
        return
        
    cur = db.cursor()
    cur.execute("DELETE FROM dropdowns")
    counts = {"anime_genres": 0, "anime_studio_ids": 0, "anime_release_years": 0}
    for key in counts:
        items = res["data"]["response"].get(key, {}).get("data", [])
        for item in items:
            cur.execute("INSERT OR REPLACE INTO dropdowns (id, type, label, option) VALUES (?,?,?,?)",
                        (str(item.get("value")), key, str(item.get("option")), str(item.get("option"))))
            counts[key] += 1
        print(f"  [DROPDOWN] [{key}] [Count: {counts[key]}] [SUCCESS]")
    db.commit()
    ok(f"Inserted {sum(counts.values())} dropdown options total")

def run_phase_2(db):
    step("Phase 2 — Fetching shallow anime list …")
    offset = 0
    page = 0
    inserted = 0
    cur = db.cursor()
    
    while True:
        page += 1
        params = {"list_type": "anime_list", "_limit": 100, "_offset": offset}
        url_params = urllib.parse.quote(json.dumps(params))
        res = api_request(f"animes/get-published-animes?json={url_params}")
        
        if not res.get("data") or "response" not in res["data"] or not res["data"]["response"].get("data"):
            break
            
        animes = res["data"]["response"]["data"]
        print(f"  [SHALLOW] [Page: {page}] [Offset: {offset}] [Port: {res['port']}] [Batch: {len(animes)}] [SUCCESS]")
        
        for a in animes:
            aid = int(a["anime_id"])
            slugSrc = a.get("anime_english_title") or a.get("anime_name") or ""
            slug = generate_slug(slugSrc)
            if not slug: slug = f"anime-{aid}"
            
            cur.execute("""INSERT INTO animes (
                anime_id, anime_name, anime_english_title, anime_slug, anime_type, anime_status,
                anime_season, anime_release_year, anime_age_rating, anime_rating, anime_rating_user_count,
                anime_description, anime_cover_image_url, anime_cover_image_full_url, anime_banner_image_url,
                anime_trailer_url, anime_release_day, anime_updated_at, anime_created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'','','','','','','')
            ON CONFLICT(anime_id) DO UPDATE SET
                anime_name = excluded.anime_name,
                anime_rating = excluded.anime_rating,
                anime_status = excluded.anime_status,
                anime_type = excluded.anime_type
            """, (
                aid, a.get("anime_name"), a.get("anime_english_title"), slug, a.get("anime_type"),
                a.get("anime_status"), a.get("anime_season"), a.get("anime_release_year"), a.get("anime_age_rating"),
                a.get("anime_rating"), a.get("anime_rating_user_count"), a.get("anime_description")
            ))
            inserted += 1
            
        db.commit()
        if len(animes) < 100:
            break
        offset += 100
        
    ok(f"Inserted/Updated {inserted} anime (shallow)")

def deep_sync_worker(row_info):
    aid = row_info[0]
    res = api_request(f"anime/get-anime-details?anime_id={aid}&fetch_episodes=Yes&more_info=Yes")
    if not res.get("data") or "response" not in res["data"]:
        return {"id": aid, "status": "FAIL", "error": res.get("error", "Empty response")}
        
    r = res["data"]["response"]
    
    # Save characters
    char_res = api_request(f"animes/get-anime-characters?json={urllib.parse.quote(json.dumps({'anime_id': aid, 'type': 'all'}))}")
    characters = char_res.get("data", {}).get("response", []) if char_res.get("data") else []
    
    return {"id": aid, "status": "OK", "response": r, "characters": characters}

def run_phase_3(db):
    step("Phase 3 — Deep extraction (details, episodes, servers, characters, recommendations) …")
    cur = db.cursor()
    all_animes = cur.execute("SELECT anime_id, anime_status FROM animes ORDER BY anime_id DESC").fetchall()
    info(f"Processing {len(all_animes)} anime for deep details & characters …")
    
    # ThreadPool deep extraction
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(deep_sync_worker, row): row for row in all_animes}
        done = 0
        for fut in as_completed(futures):
            done += 1
            row = futures[fut]
            aid = row[0]
            try:
                res = fut.result()
                if res["status"] == "FAIL":
                    print(f"[{done}/{len(all_animes)}] [COMING] [ID: {aid}] [Details: FAIL] [FAIL]")
                    continue
                    
                r = res["response"]
                chars = res["characters"]
                
                title = r.get("anime_english_title") or ""
                age = r.get("anime_age_rating") or ""
                rating = r.get("anime_rating") or ""
                rating_count = r.get("anime_rating_user_count") or ""
                desc = r.get("anime_description") or ""
                cover_full = r.get("anime_cover_image_full_url") or ""
                banner = r.get("anime_banner_image_url") or ""
                updated = r.get("anime_updated_at") or ""
                created = r.get("anime_created_at") or ""
                release_day = r.get("anime_release_day") or ""
                
                slug_src = r.get("anime_english_title") or r.get("anime_name") or ""
                slug = generate_slug(slug_src)
                if not slug: slug = f"anime-{aid}"
                
                mal_score = None
                more_info = r.get("more_info_result")
                if more_info and more_info.get("score"):
                    try: mal_score = float(more_info["score"])
                    except: pass
                    
                cur.execute("""UPDATE animes SET
                    anime_english_title = ?, anime_age_rating = ?, anime_rating = ?, anime_rating_user_count = ?,
                    anime_description = ?, anime_cover_image_full_url = ?, anime_banner_image_url = ?,
                    anime_updated_at = ?, anime_created_at = ?, anime_slug = ?, anime_release_day = ?, mal_score = ?
                    WHERE anime_id = ?""",
                    (title, age, rating, rating_count, desc, cover_full, banner, updated, created, slug, release_day, mal_score, aid))
                
                # Genres
                if r.get("anime_genre_ids"):
                    gids = str(r["anime_genre_ids"]).split(",")
                    gnames = str(r.get("anime_genres", "")).split(",")
                    for idx, gid in enumerate(gids):
                        gname = gnames[idx].strip() if idx < len(gnames) else ""
                        cur.execute("INSERT OR IGNORE INTO anime_genres (anime_id, genre_id, genre_name) VALUES (?,?,?)", (aid, gid.strip(), gname))
                        
                # Studios
                if more_info and more_info.get("anime_studio_ids"):
                    sids = str(more_info["anime_studio_ids"]).split(",")
                    snames = str(more_info.get("anime_studios", "")).split(",")
                    for idx, sid in enumerate(sids):
                        sname = snames[idx].strip() if idx < len(snames) else ""
                        cur.execute("INSERT OR IGNORE INTO anime_studios (anime_id, studio_id, studio_name) VALUES (?,?,?)", (aid, sid.strip(), sname))
                        
                # Recommendations
                recs = r.get("related_recommendations", {}).get("data", []) if isinstance(r.get("related_recommendations"), dict) else []
                for rec in recs:
                    rec_id = rec.get("recommended_anime_id")
                    if rec_id:
                        cur.execute("""INSERT OR IGNORE INTO recommendations (
                            anime_id, recommended_anime_id, recommended_anime_name, recommended_anime_cover_image_url
                        ) VALUES (?,?,?,?)""", (aid, int(rec_id), rec.get("recommended_anime_name"), rec.get("recommended_anime_image_url")))
                        
                # Characters
                for char in chars:
                    char_id = char.get("character_id")
                    if char_id:
                        cur.execute("""INSERT OR REPLACE INTO anime_characters (
                            character_id, anime_id, character_name, character_image_url, character_role
                        ) VALUES (?,?,?,?,?)""", (int(char_id), aid, char.get("character_name"), char.get("character_image_url"), char.get("character_role")))
                        
                # Episodes & Servers
                def extract_ep_num(name, api_num):
                    """Extract authoritative episode number from the episode name,
                    falling back to API value if name has no clear number."""
                    if not name: return api_num
                    m = re.search(r'الحلقة\s*:?\s*(\d+(?:\.\d+)?)', name)
                    if m:
                        extracted = m.group(1)
                        # If the API number is significantly different, trust the name
                        try:
                            api_f = float(api_num) if api_num else 0
                            ext_f = float(extracted)
                            if abs(api_f - ext_f) >= 3:
                                return extracted
                        except: pass
                    return api_num

                eps = r.get("episodes", {}).get("data", []) if isinstance(r.get("episodes"), dict) else []
                for ep in eps:
                    ep_id = int(ep["episode_id"])
                    ep_num = extract_ep_num(ep.get("episode_name"), ep.get("episode_number") or "0")
                    cur.execute("""INSERT OR REPLACE INTO episodes (
                        episode_id, anime_id, episode_name, episode_number, episode_rating, episode_created_at
                    ) VALUES (?,?,?,?,?,?)""", (ep_id, aid, ep.get("episode_name"), ep_num, ep.get("episode_rating"), ep.get("episode_created_at")))
                    
                    raw_servers = ep.get("episode_urls", [])
                    if isinstance(raw_servers, dict):
                        raw_servers = raw_servers.get("data", [])
                    servers = raw_servers if isinstance(raw_servers, list) else []
                    for srv in servers:
                        cur.execute("""INSERT OR REPLACE INTO episode_servers (
                            episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status
                        ) VALUES (?,?,?,?,?,?)""", (
                            int(srv["episode_url_id"]), ep_id, srv.get("episode_server_id"),
                            srv.get("episode_server_name"), srv.get("episode_url"), srv.get("episode_server_status")
                        ))
                db.commit()
                print(f"[{done}/{len(all_animes)}] [SUCCESS] [{r.get('anime_name')}] [Episodes: {len(eps)}]")
            except Exception as e:
                print(f"[{done}/{len(all_animes)}] Error on deep sync ID {aid}: {e}")

# --- Phase 4 & Phase 5 Slug Helper ---
def string_hash(s):
    import hashlib
    return hashlib.md5(s.encode("utf8")).hexdigest()

def run_phase_4(db):
    step("Phase 4 — Integrating Anime3rb episode servers from sitemaps …")
    print("  ➜ Fetching main sitemap index from Anime3rb...")
    idx_res = api_request("https://anime3rb.com/sitemap.xml", use_proxy=False)
    if not idx_res.get("data") or idx_res.get("status") != "SUCCESS":
        print(f"  ✗ Failed to fetch Anime3rb main sitemap index: {idx_res}")
        return
        
    sitemaps_dir = "/home/ubuntu/Projects/reverse-slayer/anime-next/DATA_LOCAL/data/sitemaps"
    os.makedirs(sitemaps_dir, exist_ok=True)
    
    root = ET.fromstring(idx_res["data"])
    sitemap_urls = []
    for elem in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
        url = elem.text.strip()
        if "videos_" in url:
            sitemap_urls.append(url)
            
    print(f"  ➜ Found {len(sitemap_urls)} video sitemaps. Downloading/parsing...")
    
    a3rb_slugs = {}
    for s_idx, s_url in enumerate(sitemap_urls, 1):
        filename = s_url.split("/")[-1]
        filepath = os.path.join(sitemaps_dir, filename)
        
        # Download if not present
        if not os.path.exists(filepath):
            print(f"    ├─ Downloading sitemap: {filename}...")
            r_smap = api_request(s_url, use_proxy=False)
            if r_smap.get("data") and r_smap.get("status") == "SUCCESS":
                with open(filepath, "w", encoding="utf8") as f:
                    f.write(r_smap["data"])
                    
        # Parse sitemap to maps
        if os.path.exists(filepath):
            try:
                tree = ET.parse(filepath)
                s_root = tree.getroot()
                for url_el in s_root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
                    loc_el = url_el.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                    if loc_el is not None:
                        loc = loc_el.text.strip()
                        # Match layout: https://anime3rb.com/episode/<slug>/<num>
                        m = re.search(r"/episode/([^/]+)/(\d+)", loc)
                        if m:
                            slug = m.group(1).lower()
                            ep_num = m.group(2)
                            if slug not in a3rb_slugs:
                                a3rb_slugs[slug] = []
                            # Store (ep_num, loc)
                            a3rb_slugs[slug].append((ep_num, loc))
            except Exception as e:
                print(f"    ✗ Error parsing sitemap {filename}: {e}")

    # Now run slug matching
    cur = db.cursor()
    max_id = cur.execute("SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers").fetchone()[0]
    local_animes = cur.execute("SELECT anime_id, anime_name, anime_english_title, anime_slug FROM animes").fetchall()
    
    matched = 0
    inserted_servers = 0
    
    for row in local_animes:
        aid, name, eng_title, db_slug = row
        slug = generate_slug(db_slug or name)
        
        # Exact slug match or lookup
        matched_slug = None
        if slug in a3rb_slugs:
            matched_slug = slug
        elif generate_slug(name) in a3rb_slugs:
            matched_slug = generate_slug(name)
        elif eng_title and generate_slug(eng_title) in a3rb_slugs:
            matched_slug = generate_slug(eng_title)
            
        if matched_slug:
            matched += 1
            eps_to_add = a3rb_slugs[matched_slug]
            for ep_num, url in eps_to_add:
                # Find matching episode in local DB
                local_ep = cur.execute("SELECT episode_id FROM episodes WHERE anime_id = ? AND CAST(episode_number AS REAL) = ?", (aid, float(ep_num))).fetchone()
                if local_ep:
                    ep_id = local_ep[0]
                    # We create Anime3rb servers for this episode
                    # Insert server
                    srv_id = f"a3rb_{ep_id}_1"
                    # Check if already exists by string srv_id to avoid duplicate counts
                    exists = cur.execute("SELECT 1 FROM episode_servers WHERE episode_server_id = ?", (srv_id,)).fetchone()
                    if exists:
                        cur.execute("""UPDATE episode_servers SET episode_url = ? WHERE episode_server_id = ?""", (url, srv_id))
                    else:
                        max_id += 1
                        cur.execute("""INSERT INTO episode_servers (
                            episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status
                        ) VALUES (?,?,?,?,?,?)""", (
                            max_id, ep_id, srv_id, "Anime3RB (Multi-quality)", url, "active"
                        ))
                        inserted_servers += 1
    db.commit()
    ok(f"Anime3rb integration complete: matched {matched}/{len(local_animes)} anime, inserted {inserted_servers} server links.")

def run_phase_5(db):
    step("Phase 5 — Integrating WitAnime episode servers …")
    wit_db_path = "/home/ubuntu/Projects/reverse-slayer/anime-next/DATA_LOCAL/scrapping/wit/wit_dumb.db"
    if not os.path.exists(wit_db_path):
        print(f"  ✗ WitAnime DB not found at: {wit_db_path}")
        return
        
    print(f"  • Opened WitAnime database: {wit_db_path}")
    wdb = sqlite3.connect(wit_db_path)
    wcur = wdb.cursor()
    
    # Read wit_anime entries
    wit_animes = wcur.execute("SELECT id, slug, name FROM wit_anime").fetchall()
    
    cur = db.cursor()
    local_animes = cur.execute("SELECT anime_id, anime_name, anime_english_title, anime_slug FROM animes").fetchall()
    
    # Build match map
    local_slug_map = {}
    for row in local_animes:
        aid, name, eng, db_slug = row
        for term in [db_slug, name, eng]:
            if term:
                slug_norm = generate_slug(term)
                if slug_norm:
                    local_slug_map[slug_norm] = aid
                    
    matched_map = {} # wit_id -> local_aid
    for wid, wslug, wname in wit_animes:
        w_norm = generate_slug(wslug or wname)
        if w_norm in local_slug_map:
            matched_map[wid] = local_slug_map[w_norm]
            
    print(f"  ➜ Matched {len(matched_map)}/{len(wit_animes)} WitAnime entries")
    
    cur = db.cursor()
    max_id = cur.execute("SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers").fetchone()[0]
    
    # Import servers
    total_imported = 0
    for wid, aid in matched_map.items():
        # Get wit episodes for this anime
        wit_eps = wcur.execute("SELECT id, number FROM wit_episodes WHERE anime_id = ?", (wid,)).fetchall()
        for wep_id, ep_num in wit_eps:
            try:
                ep_num_float = float(ep_num)
            except:
                continue
                
            local_ep = cur.execute("SELECT episode_id FROM episodes WHERE anime_id = ? AND CAST(episode_number AS REAL) = ?", (aid, ep_num_float)).fetchone()
            if local_ep:
                ep_id = local_ep[0]
                # Get watch servers for this episode
                wit_servers = wcur.execute("""SELECT server_name, embed_url 
                    FROM wit_watch_servers WHERE episode_row_id = ? 
                    AND embed_type IN ('yonaplay_sub', 'direct')""", (wep_id,)).fetchall()
                
                for s_name, embed_url in wit_servers:
                    srv_id = f"wit_{ep_id}_{string_hash(embed_url)[:8]}"
                    exists = cur.execute("SELECT 1 FROM episode_servers WHERE episode_server_id = ?", (srv_id,)).fetchone()
                    if exists:
                        cur.execute("""UPDATE episode_servers SET episode_url = ? WHERE episode_server_id = ?""", (embed_url, srv_id))
                    else:
                        max_id += 1
                        cur.execute("""INSERT INTO episode_servers (
                            episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status
                        ) VALUES (?,?,?,?,?,?)""", (
                            max_id, ep_id, srv_id, f"WitAnime - {s_name}", embed_url, "active"
                        ))
                        total_imported += 1
                    
    db.commit()
    wdb.close()
    ok(f"WitAnime integration complete: imported {total_imported} server links.")

def main():
    parser = argparse.ArgumentParser(description="Anslayer Python Standalone Dumper")
    parser.add_argument("--phase-0", action="store_true")
    parser.add_argument("--phase-1", action="store_true")
    parser.add_argument("--phase-2", action="store_true")
    parser.add_argument("--phase-3", action="store_true")
    parser.add_argument("--phase-4", action="store_true")
    parser.add_argument("--phase-5", action="store_true")
    args = parser.parse_args()

    print(f"\n {C.bold}{C.green}╔══════════════════════════════════════╗{C.reset}")
    print(f" {C.bold}{C.green}║  FIXED PYTHON ANSLAYER DUMBER        ║{C.reset}")
    print(f" {C.bold}{C.green}╚══════════════════════════════════════╝{C.reset}\n")

    setup_tor_pool()

    db = sqlite3.connect(DB_PATH)
    # migrations
    cur = db.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS dropdowns (id TEXT PRIMARY KEY, type TEXT, label TEXT, option TEXT)")
    cur.execute("""CREATE TABLE IF NOT EXISTS animes (
        anime_id INTEGER PRIMARY KEY, anime_name TEXT, anime_english_title TEXT, anime_slug TEXT,
        anime_type TEXT, anime_status TEXT, anime_season TEXT, anime_release_year TEXT,
        anime_age_rating TEXT, anime_rating TEXT, anime_rating_user_count TEXT, anime_description TEXT,
        anime_cover_image_url TEXT, anime_cover_image_full_url TEXT, anime_banner_image_url TEXT,
        anime_trailer_url TEXT, anime_release_day TEXT, anime_updated_at TEXT, anime_created_at TEXT,
        mal_id INTEGER, mal_score REAL, mal_image TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS episodes (
        episode_id INTEGER PRIMARY KEY, anime_id INTEGER, episode_name TEXT, episode_number TEXT,
        episode_rating TEXT, episode_created_at TEXT, skip_from TEXT, skip_to TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS episode_servers (
        episode_url_id TEXT PRIMARY KEY, episode_id INTEGER, episode_server_id TEXT,
        episode_server_name TEXT, episode_url TEXT, episode_server_status TEXT
    )""")
    cur.execute("CREATE TABLE IF NOT EXISTS anime_genres (anime_id INTEGER, genre_id TEXT, genre_name TEXT, UNIQUE(anime_id, genre_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS anime_studios (anime_id INTEGER, studio_id TEXT, studio_name TEXT, UNIQUE(anime_id, studio_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS recommendations (anime_id INTEGER, recommended_anime_id INTEGER, recommended_anime_name TEXT, recommended_anime_cover_image_url TEXT, UNIQUE(anime_id, recommended_anime_id))")
    cur.execute("CREATE TABLE IF NOT EXISTS anime_characters (character_id INTEGER PRIMARY KEY, anime_id INTEGER, character_name TEXT, character_image_url TEXT, character_role TEXT)")
    db.commit()

    run_all = not (args.phase_0 or args.phase_1 or args.phase_2 or args.phase_3 or args.phase_4 or args.phase_5)

    if args.phase_0 or run_all: run_phase_0(db)
    if args.phase_1 or run_all: run_phase_1(db)
    if args.phase_2 or run_all: run_phase_2(db)
    if args.phase_3 or run_all: run_phase_3(db)
    if args.phase_4 or run_all: run_phase_4(db)
    if args.phase_5 or run_all: run_phase_5(db)

    db.close()

if __name__ == "__main__":
    main()
