#!/usr/bin/env python3
import sqlite3
import json
import os
import re
import html
import time
import sys
import socket
import subprocess
import urllib.parse
import xml.etree.ElementTree as ET
import httpx
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Config ---
DB_PATH = "/home/ubuntu/Projects/reverse-slayer/anime-next/data/anime.db"
LOCK_DIR = "/tmp/anime_sync.lock"
WIT = "https://witanime.you"
A3RB_SITEMAP = "https://anime3rb.com/sitemap.xml"
ANSLAYER_BASE = "https://anslayer.com/anime/public/"
CLIENT_ID = "android-app2"
CLIENT_SECRET = "7befba6263cc14c90d2f1d6da2c5cf9b251bfbbd"
CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BACKFILL_LIMIT = int(os.getenv("SYNC_BACKFILL_LIMIT", "120"))
BACKFILL_MAX_SECONDS = int(os.getenv("SYNC_BACKFILL_MAX_SECONDS", "600"))
BACKFILL_LOG_EVERY = int(os.getenv("SYNC_BACKFILL_LOG_EVERY", "10"))
BACKFILL_EARLY_ABORT_STREAK = int(os.getenv("SYNC_BACKFILL_EARLY_ABORT_STREAK", "30"))

# --- Directory-based lock to prevent concurrent runs ---
if os.path.isdir(LOCK_DIR):
    pid_file = os.path.join(LOCK_DIR, "pid")
    if os.path.isfile(pid_file):
        try:
            with open(pid_file) as pf:
                old_pid = int(pf.read().strip())
            # Check if process is alive via /proc (Linux)
            if os.path.isdir(f"/proc/{old_pid}"):
                print(f"[FATAL] Sync lock {LOCK_DIR} held by PID {old_pid}. Another sync is running. Exiting.")
                sys.exit(1)
        except (ValueError, OSError):
            pass
    # Stale lock, remove it
    try:
        if os.path.isfile(pid_file):
            os.unlink(pid_file)
        os.rmdir(LOCK_DIR)
    except OSError:
        pass

# Create fresh lock
try:
    os.makedirs(LOCK_DIR, 0o755)
except FileExistsError:
    print(f"[FATAL] Lock race condition. Another sync just started. Exiting.")
    sys.exit(1)
except OSError as e:
    print(f"[FATAL] Cannot create lock directory: {e}")
    sys.exit(1)
with open(os.path.join(LOCK_DIR, "pid"), "w") as f:
    f.write(str(os.getpid()))
    
    import atexit
    def _release_lock():
        try:
            if os.path.isdir(LOCK_DIR):
                pid_file = os.path.join(LOCK_DIR, "pid")
                if os.path.isfile(pid_file):
                    with open(pid_file) as pf:
                        my_pid = pf.read().strip()
                    if my_pid == str(os.getpid()):
                        os.unlink(pid_file)
                os.rmdir(LOCK_DIR)
        except OSError:
            pass
    atexit.register(_release_lock)

TOR_PORTS = [9050, 9051, 9052, 9053, 9054, 9055, 9056, 9058, 9059]
good_ports = []
current_tor_idx = 0

# --- Global run_id for log association ---
_current_run_id = None

# --- DB & Logging Helpers ---
def init_logging_tables(db):
    cur = db.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sync_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        level TEXT,
        module TEXT,
        message TEXT,
        run_id INTEGER
    )""")
    # Add run_id column if it doesn't exist (migration for existing DBs)
    try:
        cur.execute("ALTER TABLE sync_logs ADD COLUMN run_id INTEGER")
    except Exception:
        pass  # Column already exists
    cur.execute("""CREATE TABLE IF NOT EXISTS api_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        url TEXT,
        status_code INTEGER,
        duration REAL,
        run_id INTEGER
    )""")
    try:
        cur.execute("ALTER TABLE api_logs ADD COLUMN run_id INTEGER")
    except Exception:
        pass
    cur.execute("""CREATE TABLE IF NOT EXISTS sync_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        finished_at DATETIME,
        status TEXT,
        summary TEXT
    )""")
    db.commit()

def log(db, level, module, msg):
    global _current_run_id
    ts = time.strftime('%H:%M:%S')
    print(f"[{ts}] [{level}] [{module}] {msg}", flush=True)
    try:
        db.execute(
            "INSERT INTO sync_logs (level, module, message, run_id) VALUES (?, ?, ?, ?)",
            (level, module, msg, _current_run_id)
        )
        db.commit()
    except Exception as e:
        print(f"Logging error: {e}", flush=True)

def progress(db, module, msg):
    """Emit a PROGRESS-level log for stage/phase tracking."""
    log(db, "PROGRESS", module, msg)

def log_api_call(db, url, status_code, duration):
    global _current_run_id
    try:
        clean_url = url.replace(CLIENT_SECRET, "HIDDEN").replace(CLIENT_ID, "HIDDEN")
        db.execute(
            "INSERT INTO api_logs (url, status_code, duration, run_id) VALUES (?, ?, ?, ?)",
            (clean_url, status_code, duration, _current_run_id)
        )
        db.commit()
    except Exception:
        pass

# --- Tor Probe ---
def probe_ports(db):
    global good_ports
    progress(db, "Network", "▶ Probing Tor SOCKS5 proxy ports...")
    active_ports = []
    for p in TOR_PORTS:
        try:
            transport = httpx.HTTPTransport(proxy=f"socks5://127.0.0.1:{p}")
            with httpx.Client(transport=transport, headers={"User-Agent": CHROME_UA}, timeout=5) as client:
                r = client.get(f"{ANSLAYER_BASE}animes/get-anime-dropdowns", headers={'Client-Id': CLIENT_ID, 'Client-Secret': CLIENT_SECRET})
                if r.status_code == 200:
                    active_ports.append(p)
                    log(db, "DEBUG", "Network", f"  ✓ Port {p}: active (HTTP {r.status_code})")
                else:
                    log(db, "DEBUG", "Network", f"  ✗ Port {p}: HTTP {r.status_code}")
        except Exception as e:
            log(db, "DEBUG", "Network", f"  ✗ Port {p}: unreachable ({type(e).__name__})")
    if active_ports:
        good_ports = active_ports
        log(db, "INFO", "Network", f"Active Tor ports: {good_ports} ({len(good_ports)}/{len(TOR_PORTS)} responsive)")
    else:
        good_ports = [TOR_PORTS[0]]
        log(db, "WARNING", "Network", f"No active Tor ports found. Falling back to port {good_ports[0]}")

# --- Network Clients ---
def fetch_episode_page(url):
    """Fetch a WitAnime episode page using Tor with proper referer.

    Try available Tor ports from good_ports and accept any non-empty 200 response.
    """
    try:
        headers = {"User-Agent": CHROME_UA, "Referer": "https://www.google.com/"}
        ports = good_ports if isinstance(good_ports, list) and good_ports else TOR_PORTS
        for p in ports:
            try:
                transport = httpx.HTTPTransport(proxy=f"socks5://127.0.0.1:{p}")
                with httpx.Client(transport=transport, headers=headers, timeout=12, follow_redirects=True) as client:
                    r = client.get(url)
                    if r.status_code == 200 and r.text:
                        return r.text
            except Exception:
                continue
    except Exception:
        pass
    return None

def renew_tor_circuit():
    """Send NEWNYM signal to Tor to get a fresh exit node."""
    try:
        s = socket.socket(); s.settimeout(3)
        s.connect(("127.0.0.1", 9050))
        s.sendall(b"AUTHENTICATE\r\nSIGNAL NEWNYM\r\nQUIT\r\n")
        s.close()
        time.sleep(2)  # Wait for new circuit
        return True
    except Exception:
        return False

def get_tor_client(referer=None):
    global current_tor_idx
    ports_list = good_ports if good_ports else TOR_PORTS
    port = ports_list[current_tor_idx]
    current_tor_idx = (current_tor_idx + 1) % len(ports_list)
    transport = httpx.HTTPTransport(proxy=f"socks5://127.0.0.1:{port}")
    headers = {"User-Agent": CHROME_UA}
    if referer:
        headers["Referer"] = referer
    return httpx.Client(transport=transport, headers=headers, timeout=20, follow_redirects=True)

def api_get(db, client, path):
    url = f"{ANSLAYER_BASE}{path}"
    headers = {'Client-Id': CLIENT_ID, 'Client-Secret': CLIENT_SECRET, 'Accept': 'application/json', 'User-Agent': CHROME_UA}
    
    t0 = time.time()
    try:
        r = client.get(url, headers=headers)
        status_code = r.status_code
        duration = time.time() - t0
        log_api_call(db, url, status_code, duration)
        log(db, "DEBUG", "Anslayer", f"  GET {path.split('?')[0]} → HTTP {status_code} ({duration:.2f}s)")
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 429:
            log(db, "WARNING", "Network", f"Rate limited on {path.split('?')[0]}. Rotating Tor circuit...")
            client = get_tor_client()
            r = client.get(url, headers=headers)
            status_code = r.status_code
            duration = time.time() - t0
            log_api_call(db, url, status_code, duration)
            log(db, "DEBUG", "Anslayer", f"  GET {path.split('?')[0]} → HTTP {status_code} ({duration:.2f}s) [retry]")
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        duration = time.time() - t0
        log_api_call(db, url, 500, duration)
        log(db, "ERROR", "Network", f"API Request failed: {path.split('?')[0]} | Error: {e}")
    return None

def fetch_direct(db, client, url):
    t0 = time.time()
    try:
        r = client.get(url)
        status_code = r.status_code
        duration = time.time() - t0
        log_api_call(db, url, status_code, duration)
        log(db, "DEBUG", "HTTP", f"  GET {url.split('?')[0]} → HTTP {status_code} ({duration:.2f}s)")
        return r
    except Exception as e:
        duration = time.time() - t0
        log_api_call(db, url, 500, duration)
        log(db, "ERROR", "Network", f"Direct fetch failed: {url.split('?')[0]} | Error: {e}")
    return None

# --- Parsing Helpers ---
def parse_ep_num(s):
    if s is None: return 0
    s = str(s).strip()
    try:
        if '.' in s:
            val = float(s)
            return int(val) if val.is_integer() else val
        return int(s)
    except ValueError:
        m = re.search(r'(\d+(?:\.\d+)?)', s)
        if m:
            val = float(m.group(1))
            return int(val) if val.is_integer() else val
        return 0

def decode_html(s): return html.unescape(s).strip() if s else ""

def ep_token(ep_num):
    try:
        val = float(ep_num)
        return str(int(val)) if val.is_integer() else str(val).rstrip('0').rstrip('.')
    except Exception:
        return str(ep_num).strip()

def clean_title(s):
    if not s: return ""
    s = decode_html(s).lower().replace('-', ' ').strip()
    s = s.replace('½','1/2').replace('ou','o').replace('oo','o').replace('uu','u').replace('gotoubun','5toubun')
    
    synonyms = {
        'gedo senki': 'ged senki',
        'k-project': 'k',
        'chiyu mahou no machigatta tsukaikata: senjou wo kakeru kaifuku youin': 'chiyu mahou no machigatta tsukaikata',
        'buchigire reijou wa houfuku wo chikaimashita. madousho no chikara de sokoku wo tatakitsubushimasu': 'buchigire reijou wa houfuku wo chikaimashita',
        'long zu': 'dragon raja',
        'dungeon ni deai o motomeru no wa machigatte irou darouka': 'dungeon ni deai wo motomeru no wa machigatteiru darou ka',
        'familia myth iv': 'iv',
        'kabushikigaisha magi-lumière': 'kabushikigaisha magi lumiere',
        'magilumiere': 'magi lumiere',
        'otome kaijuu caraméliser': 'otome kaijuu carameliser',
        'shuumatsu no walküre': 'shuumatsu no walkure',
        'ranma ½': 'ranma 1/2',
        'ranma-11708': 'ranma 1/2',
        'sekai saikyou no kouei: meikyuukoku no shinjin tansakusha': 'sekai saikyou no kouei',
        'shiguang dailiren: yingdu pian': 'link click yingdu',
        'akiba meido sensou': 'akiba maid sensou',
        'fuyu no sonata': 'winter sonata',
        'prelude to dawn': 'reimei zensou',
        'hiiro no kakera dai ni shou': 'hiiro no kakera 2nd season',
        'lets & go': 'lets and go',
        'lets &amp; go': 'lets and go'
    }
    for old, new in synonyms.items():
        if old in s: s = s.replace(old, new)
        
    s = re.sub(r'\s*\([^)]*\)\s*$','',s)
    s = re.sub(r'\s+(part|season)\s+\d+\s*$','',s,flags=re.I)
    s = re.sub(r'\s+\d+(nd|rd{1,2}|th|st)?\s+season\s*$','',s,flags=re.I)
    return re.sub(r'[^a-z0-9\u0600-\u06FF]', '', s)

# --- 1. ANSLAYER SYNC ---
def sync_anslayer(db, client):
    phase_start = time.time()
    log(db, "INFO", "Anslayer", "════════════════════════════════════")
    progress(db, "Anslayer", "▶ PHASE 1/5 — Anslayer Incremental Sync")
    log(db, "INFO", "Anslayer", "════════════════════════════════════")
    cur = db.cursor()
    
    # 1a. Refresh Dropdowns (Filters)
    progress(db, "Anslayer", "[1/3] Fetching filter dropdowns (genres, studios, years)...")
    dd_res = api_get(db, client, "animes/get-anime-dropdowns")
    if dd_res and 'response' in dd_res:
        cur.execute("DELETE FROM dropdowns")
        counts = {'anime_genres': 0, 'anime_studio_ids': 0, 'anime_release_years': 0}
        for key in counts:
            items = dd_res['response'].get(key, {}).get('data', [])
            for item in items:
                cur.execute("INSERT INTO dropdowns (id, type, label, option) VALUES (?,?,?,?)", 
                           (str(item.get('value')), key, str(item.get('option')), str(item.get('option'))))
                counts[key] += 1
        log(db, "INFO", "Anslayer", f"  ↳ Genres: {counts['anime_genres']}, Studios: {counts['anime_studio_ids']}, Years: {counts['anime_release_years']}")
        db.commit()
    else:
        log(db, "WARNING", "Anslayer", "  ↳ Could not fetch dropdowns (API unavailable?)")

    # 1b. Shallow Sweep Catalog
    progress(db, "Anslayer", "[2/3] Shallow catalog sweep — scanning all pages...")
    offset = 0
    page_num = 0
    status_updates = 0
    existing_animes = {int(row[0]): row for row in cur.execute("SELECT anime_id, anime_status, anime_rating FROM animes").fetchall()}
    new_animes_queue = []
    
    while True:
        page_num += 1
        params = {"list_type": "anime_list", "_limit": 100, "_offset": offset}
        data = api_get(db, client, f"animes/get-published-animes?json={urllib.parse.quote(json.dumps(params))}")
        if not data or 'response' not in data or not data['response'].get('data'):
            log(db, "WARNING", "Anslayer", f"  ↳ Empty page at offset {offset}, ending sweep")
            break
        
        batch = data['response']['data']
        log(db, "INFO", "Anslayer", f"  ↳ Page {page_num}: offset={offset}, got {len(batch)} animes")
        
        new_in_batch = 0
        status_updates_in_batch = 0
        for a in batch:
            if not a.get('anime_id'): continue
            aid = int(a['anime_id'])
            if aid in existing_animes:
                old = existing_animes[aid]
                if old[1] != a.get('anime_status') or old[2] != str(a.get('anime_rating')):
                    cur.execute("UPDATE animes SET anime_status=?, anime_rating=?, anime_release_year=?, anime_type=? WHERE anime_id=?",
                                (a.get('anime_status'), a.get('anime_rating'), a.get('anime_release_year'), a.get('anime_type'), aid))
                    status_updates += 1
                    status_updates_in_batch += 1
            else:
                new_animes_queue.append((aid, a.get('anime_name')))
                new_in_batch += 1
                
        if new_in_batch > 0:
            log(db, "INFO", "Anslayer", f"  ↳ Found {new_in_batch} new animes in page {page_num}")
        if status_updates_in_batch > 0:
            log(db, "DEBUG", "Anslayer", f"  ↳ Updated {status_updates_in_batch} statuses/ratings in page {page_num}")
                
        if len(batch) < 100:
            log(db, "INFO", "Anslayer", f"  ↳ Reached last page ({page_num})")
            break
        offset += 100
        
    db.commit()
    log(db, "INFO", "Anslayer", f"  ↳ Sweep complete: {status_updates} statuses updated, {len(new_animes_queue)} new animes queued")
    progress(db, "Anslayer", f"  ✓ Catalog sweep done — {len(new_animes_queue)} new anime to deep-sync, {status_updates} updates")

    # Concurrently deep sync new animes
    if new_animes_queue:
        progress(db, "Anslayer", f"[3/3] Deep-syncing {len(new_animes_queue)} new anime (3 parallel workers)...")
        log(db, "INFO", "Anslayer", f"[3/3] Deep-syncing {len(new_animes_queue)} new animes (parallel: 3 workers)...")
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(deep_sync_anime_worker, aid, get_tor_client()): aid for aid, _ in new_animes_queue}
            success_count = 0
            fail_count = 0
            for fut in as_completed(futures):
                aid = futures[fut]
                try:
                    res = fut.result()
                    if res:
                        success_count += 1
                        log(db, "INFO", "Anslayer", f"  ↳ Deep-synced anime ID {aid}")
                    else:
                        fail_count += 1
                except Exception as e:
                    fail_count += 1
                    log(db, "ERROR", "Anslayer", f"  ↳ Failed deep sync ID {aid}: {e}")
            log(db, "INFO", "Anslayer", f"  ↳ Deep sync complete: {success_count} success, {fail_count} fail")
            progress(db, "Anslayer", f"  ✓ Deep sync finished — {success_count} ok, {fail_count} failed")

    # 1c. Pull recently updated episodes feed
    log(db, "INFO", "Anslayer", "Checking latest updated episodes feed...")
    params = {"list_type": "latest_updated_episode_new", "_limit": 100, "_offset": 0}
    data = api_get(db, client, f"animes/get-published-animes?json={urllib.parse.quote(json.dumps(params))}")
    
    if data and 'response' in data and data['response'].get('data'):
        new_ep_count = 0
        new_ep_deep_syncs = []
        items = data['response']['data']
        log(db, "DEBUG", "Anslayer", f"  ↳ Feed returned {len(items)} items")
        for item in items:
            if not item.get('anime_id') or not item.get('episode_id'): continue
            aid = int(item.get('anime_id'))
            ep_id = int(item.get('episode_id'))
            
            if aid not in existing_animes:
                new_animes_queue.append((aid, ""))
                continue
                
            exists = cur.execute("SELECT 1 FROM episodes WHERE episode_id=?", (ep_id,)).fetchone()
            if not exists:
                ep_num = parse_ep_num(item.get('episode_number'))
                ep_name = item.get('episode_name') or f"الحلقة {ep_num}"
                cur.execute("INSERT OR REPLACE INTO episodes (episode_id, anime_id, episode_name, episode_number, episode_rating, episode_created_at) VALUES (?,?,?,?,'','')",
                            (ep_id, aid, ep_name, ep_num))
                cur.execute("UPDATE animes SET anime_updated_at = datetime('now') WHERE anime_id = ?", (aid,))
                new_ep_count += 1
                new_ep_deep_syncs.append((aid, ep_id))
                
        db.commit()
        
        if new_ep_deep_syncs:
            log(db, "INFO", "Anslayer", f"  ↳ Fetching servers for {len(new_ep_deep_syncs)} new episodes (parallel: 3 workers)...")
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(sync_episode_servers_worker, aid, ep_id, get_tor_client()): (aid, ep_id) for aid, ep_id in new_ep_deep_syncs}
                srv_count = 0
                for fut in as_completed(futures):
                    aid, ep_id = futures[fut]
                    try:
                        fut.result()
                        srv_count += 1
                    except Exception as e:
                        log(db, "ERROR", "Anslayer", f"  ↳ Failed servers for ep {ep_id}: {e}")
                log(db, "INFO", "Anslayer", f"  ↳ Server sync complete for {srv_count}/{len(new_ep_deep_syncs)} episodes")
                        
        log(db, "INFO", "Anslayer", f"  ↳ Added {new_ep_count} new episodes from feed")

def deep_sync_anime_worker(aid, client):
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    try:
        det = api_get(db, client, f"anime/get-anime-details?anime_id={aid}&fetch_episodes=Yes&more_info=Yes")
        r = det.get('response') if det else None
        if not r:
            return False
        
        # Generate slug if missing
        slug = r.get('anime_slug')
        if not slug:
            slug_src = r.get('anime_english_title') or r.get('anime_name') or ''
            slug = re.sub(r'[^a-z0-9\u0600-\u06ff\s-]', '', slug_src.lower())
            slug = re.sub(r'[\s_]+', '-', slug)
            slug = re.sub(r'-+', '-', slug).strip('-')
            if not slug or len(slug) < 2:
                slug = f'anime-{aid}'
        
        cur.execute("""INSERT OR REPLACE INTO animes (
            anime_id, anime_name, anime_english_title, anime_slug, anime_type, anime_status, 
            anime_season, anime_release_year, anime_age_rating, anime_rating, anime_rating_user_count, 
            anime_description, anime_cover_image_url, anime_cover_image_full_url, anime_banner_image_url, 
            anime_trailer_url, anime_release_day, anime_updated_at, anime_created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            aid, r.get('anime_name'), r.get('anime_english_title'), slug, r.get('anime_type'),
            r.get('anime_status'), r.get('anime_season'), r.get('anime_release_year'), r.get('anime_age_rating'),
            r.get('anime_rating'), r.get('anime_rating_user_count'), r.get('anime_description'),
            r.get('anime_cover_image_url'), r.get('anime_cover_image_full_url'), r.get('anime_banner_image_url'),
            r.get('anime_trailer_url'), r.get('anime_release_day'), r.get('anime_updated_at'), r.get('anime_created_at')
        ))
        
        if r.get('anime_genre_ids'):
            genre_ids = str(r['anime_genre_ids']).split(',')
            genre_names = str(r.get('anime_genres', '')).split(',')
            for gi in range(len(genre_ids)):
                g_id = genre_ids[gi].strip()
                g_name = genre_names[gi].strip() if gi < len(genre_names) else ""
                if g_id: cur.execute("INSERT OR IGNORE INTO anime_genres (anime_id, genre_id, genre_name) VALUES (?,?,?)", (aid, g_id, g_name))
                
        more_info = r.get('more_info_result', {}) or {}
        if more_info.get('anime_studio_ids'):
            studio_ids = str(more_info['anime_studio_ids']).split(',')
            studio_names = str(more_info.get('anime_studios', '')).split(',')
            for si in range(len(studio_ids)):
                s_id = studio_ids[si].strip()
                s_name = studio_names[si].strip() if si < len(studio_names) else ""
                if s_id: cur.execute("INSERT OR IGNORE INTO anime_studios (anime_id, studio_id, studio_name) VALUES (?,?,?)", (aid, s_id, s_name))
                
        eps_data = r.get('episodes', {}).get('data', []) if isinstance(r.get('episodes'), dict) else r.get('episodes', [])
        log(db, "DEBUG", "Anslayer", f"  ↳ Deep syncing anime {aid} '{r.get('anime_name')}' with {len(eps_data)} episodes")
        for ep in eps_data:
            ep_id = ep.get('episode_id')
            ep_num = parse_ep_num(ep.get('episode_number'))
            cur.execute("INSERT OR REPLACE INTO episodes (episode_id, anime_id, episode_name, episode_number, episode_rating, episode_created_at) VALUES (?,?,?,?,?,'')",
                        (ep_id, aid, ep.get('episode_name'), ep_num, ep.get('episode_rating')))
            for srv in ep.get('episode_urls', []):
                cur.execute("INSERT OR REPLACE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                            (srv.get('episode_url_id'), ep_id, f"ans_{srv.get('episode_server_id')}", srv.get('episode_server_name'), srv.get('episode_url'), 'active'))
        db.commit()
        db.close()
        return True
    except Exception as e:
        db.close()
        raise e

def sync_episode_servers_worker(aid, ep_id, client):
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    try:
        det = api_get(db, client, f"anime/get-anime-details?anime_id={aid}&fetch_episodes=Yes&more_info=No")
        r = det.get('response') if det else None
        if r:
            eps_data = r.get('episodes', {}).get('data', []) if isinstance(r.get('episodes'), dict) else r.get('episodes', [])
            for ep in eps_data:
                if ep.get('episode_id') == ep_id:
                    for srv in ep.get('episode_urls', []):
                        cur.execute("INSERT OR REPLACE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)",
                                    (srv.get('episode_url_id'), ep_id, f"ans_{srv.get('episode_server_id')}", srv.get('episode_server_name'), srv.get('episode_url'), 'active'))
            db.commit()
        db.close()
    except Exception as e:
        db.close()
        raise e

# --- 2. WITANIME SYNC ---
def sync_witanime(db, client):
    log(db, "INFO", "WitAnime", "════════════════════════════════════")
    progress(db, "WitAnime", "▶ PHASE 2/5 — WitAnime Homepage Scrape")
    log(db, "INFO", "WitAnime", "════════════════════════════════════")
    cur = db.cursor()
    name_map = {clean_title(t): aid for aid, name, eng, slug in cur.execute("SELECT anime_id, anime_name, anime_english_title, anime_slug FROM animes").fetchall() for t in [name, eng, slug] if t}
    
    r = fetch_direct(db, client, WIT)
    if not r or r.status_code != 200:
        log(db, "ERROR", "WitAnime", "Failed to retrieve WitAnime homepage feed.")
        progress(db, "WitAnime", "  ✗ Failed to reach WitAnime homepage")
        return
        
    soup = BeautifulSoup(r.text, 'lxml')
    links = [a['href'] for a in soup.find_all('a', href=True) if '/episode/' in a['href']]
    seen = set(); ep_links = [x for x in links if not (x in seen or seen.add(x))]
    log(db, "INFO", "WitAnime", f"Found {len(ep_links)} recent episode links on homepage")
    progress(db, "WitAnime", f"  ↳ Found {len(ep_links)} episode links — processing up to 35...")
    
    matched = 0
    skipped = 0
    created = 0
    servers_added = 0
    
    for url in ep_links[:35]:
        path = urllib.parse.unquote(url).rstrip('/').split('/')[-1]
        m = re.match(r'^(.*?)-(?:الحلقة|الفيلم|الأونا|الأوفا|خاصة|الحلقة-الخاصة)-(\d+(?:\.\d+)?)$', path)
        if not m:
            skipped += 1
            continue
        w_slug, w_ep_num = m.group(1), parse_ep_num(m.group(2))
        
        aid = name_map.get(clean_title(w_slug))
        if not aid:
            log(db, "DEBUG", "WitAnime", f"  ↳ Skipped '{w_slug}' Ep {w_ep_num} (no Anslayer match)")
            skipped += 1
            continue
        matched += 1
        
        # Get or create the episode if it doesn't exist
        ep_row = cur.execute("SELECT episode_id FROM episodes WHERE anime_id=? AND episode_number=?", (aid, w_ep_num)).fetchone()
        if ep_row:
            ep_id = ep_row[0]
        else:
            max_ep = cur.execute("SELECT COALESCE(MAX(episode_id), 0) FROM episodes").fetchone()[0]
            ep_id = max_ep + 1
            cur.execute("INSERT INTO episodes (episode_id, anime_id, episode_name, episode_number, episode_rating, episode_created_at) VALUES (?,?,?,?,'','')",
                        (ep_id, aid, f"الحلقة {w_ep_num}", w_ep_num))
            cur.execute("UPDATE animes SET anime_updated_at = datetime('now') WHERE anime_id = ?", (aid,))
            db.commit()
            created += 1
            log(db, "INFO", "WitAnime", f"  ↳ Created ep '{w_slug}' #{w_ep_num} → ID {ep_id}")
        
        if cur.execute("SELECT 1 FROM episode_servers WHERE episode_id=? AND episode_server_id LIKE 'wit_%' LIMIT 1", (ep_id,)).fetchone():
            continue
            
        try:
            # Use curl_cffi to bypass Cloudflare
            html_text = fetch_episode_page(url)
            if not html_text:
                log(db, "WARNING", "WitAnime", f"  ↳ Failed to fetch '{w_slug}' Ep {w_ep_num}")
                continue
            
            import base64
            # Find encryption variables (WitAnime changes names periodically)
            zx = re.search(r'(?:var\s+)?_z[HX]\s*=\s*"([^"]+)"', html_text)
            zk = re.search(r'(?:var\s+)?_z[WK]\s*=\s*"([^"]+)"', html_text)
            
            if not zx or not zk:
                log(db, "WARNING", "WitAnime", f"  ↳ No decryption data found for '{w_slug}' Ep {w_ep_num}")
                continue
            
            rr = json.loads(base64.b64decode(zx.group(1)).decode())
            cr = json.loads(base64.b64decode(zk.group(1)).decode())
            names = dict(re.findall(r'<a[^>]*data-server-id="(\d+)"[^>]*>([\s\S]*?)</a>', html_text))
            
            max_srv = cur.execute("SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers").fetchone()[0]
            
            episode_servers = []
            for i, e in enumerate(rr):
                raw = re.sub(r'[^A-Za-z0-9+/=]', "", e[::-1])
                u = base64.b64decode(raw).decode()
                idx = int(base64.b64decode(cr[i]["k"]).decode())
                off = cr[i]["d"][idx]
                if off > 0: u = u[:-off]
                if u.strip().lstrip("/").startswith("//"): u = "https:" + u.strip().lstrip("/")
                n = re.sub(r'<[^>]+>', "", names.get(str(i), "")).strip()
                t = "yonaplay" if "yonaplay" in u.lower() else "direct"
                
                if t == "yonaplay":
                    yona_url = u + "&apiKey=23a97133-caf3-4eb4-9466-93d0a4ff8198" if "embed.php?id=" in u else u
                    yona_html = fetch_episode_page(yona_url)
                    if yona_html:
                        for m_sub in re.finditer(r'\{[^}]*?\"file\"[^}]*?\}', yona_html):
                            try:
                                d = json.loads(m_sub.group(0))
                                if d.get("file"):
                                    episode_servers.append((max_srv + 1, ep_id, f"wit_{i}", f"{d.get('label','')} {d.get('type','')}", d["file"]))
                                    max_srv += 1
                            except Exception:
                                pass
                else:
                    episode_servers.append((max_srv + 1, ep_id, f"wit_{i}", n, u))
                    max_srv += 1
            
            for srv in episode_servers:
                cur.execute("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,'active')", srv)
            
            db.commit()
            servers_added += len(episode_servers)
            if episode_servers:
                log(db, "INFO", "WitAnime", f"  ↳ Imported {len(episode_servers)} servers for '{w_slug}' Ep {w_ep_num}")
        except Exception as e:
            log(db, "ERROR", "WitAnime", f"Scrape failed for {w_slug} Ep {w_ep_num}: {e}")
            
    log(db, "INFO", "WitAnime", f"Done. Matched: {matched} | Created: {created} eps | Servers: {servers_added} | Skipped: {skipped}")
    progress(db, "WitAnime", f"  ✓ WitAnime done — {matched} matched, {created} new eps, {servers_added} servers imported")

# --- Anime3RB Sync ---
def sync_anime3rb(db, client):
    log(db, "INFO", "Anime3RB", "════════════════════════════════════")
    progress(db, "Anime3RB", "▶ PHASE 3/5 — Anime3RB Sitemap Sync")
    log(db, "INFO", "Anime3RB", "════════════════════════════════════")
    cur = db.cursor()
    name_map = {clean_title(t): aid for aid, name, eng, slug in cur.execute("SELECT anime_id, anime_name, anime_english_title, anime_slug FROM animes").fetchall() for t in [name, eng, slug] if t}
    
    r = fetch_direct(db, client, A3RB_SITEMAP)
    if not r or r.status_code != 200:
        log(db, "ERROR", "Anime3RB", "Failed to retrieve sitemap index.")
        return
        
    try:
        root = ET.fromstring(r.text)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemaps = [sm.text for sm in root.findall(".//s:sitemap/s:loc", ns) if sm.text and "videos_" in sm.text]
        if not sitemaps:
            log(db, "WARNING", "Anime3RB", "No video sitemaps found in index.")
            return
        log(db, "INFO", "Anime3RB", f"Found {len(sitemaps)} video sitemaps. Using: {sitemaps[-1].split('/')[-1]}")
        
        r_sm = fetch_direct(db, client, sitemaps[-1])
        if not r_sm or r_sm.status_code != 200: return
        sm_root = ET.fromstring(r_sm.text)
        urls = [u.text for u in sm_root.findall(".//s:url/s:loc", ns) if u.text and "/episode/" in u.text]
        log(db, "INFO", "Anime3RB", f"Sitemap contains {len(urls)} episode URLs")
    except Exception as e:
        log(db, "ERROR", "Anime3RB", f"Failed to parse sitemaps: {e}")
        return
        
    servers_added = 0
    skipped = 0
    matched = 0
    created = 0
    
    for page_url in urls[-60:]:
        parts = page_url.rstrip('/').split('/')
        if len(parts) < 5:
            skipped += 1
            continue
        a3rb_slug, ep_num_str = parts[-2], parts[-1]
        ep_num = parse_ep_num(ep_num_str)
        
        aid = name_map.get(clean_title(a3rb_slug))
        if not aid:
            skipped += 1
            continue
        matched += 1
        
        # Get or create the episode
        ep_row = cur.execute("SELECT episode_id FROM episodes WHERE anime_id=? AND episode_number=?", (aid, ep_num)).fetchone()
        if ep_row:
            ep_id = ep_row[0]
        else:
            max_ep = cur.execute("SELECT COALESCE(MAX(episode_id), 0) FROM episodes").fetchone()[0]
            ep_id = max_ep + 1
            cur.execute("INSERT INTO episodes (episode_id, anime_id, episode_name, episode_number, episode_rating, episode_created_at) VALUES (?,?,?,?,'','')",
                        (ep_id, aid, f"الحلقة {ep_num_str}", ep_num))
            cur.execute("UPDATE animes SET anime_updated_at = datetime('now') WHERE anime_id = ?", (aid,))
            db.commit()
            created += 1
        
        if cur.execute("SELECT 1 FROM episode_servers WHERE episode_id=? AND episode_server_id LIKE 'a3rb_%' LIMIT 1", (ep_id,)).fetchone():
            continue
            
        max_srv = cur.execute("SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers").fetchone()[0]
        cur.execute("INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,'active')",
                     (max_srv + 1, ep_id, f"a3rb_{a3rb_slug}_{ep_num_str}", f"anime3rb - {ep_num_str}", page_url, 'active'))
        db.commit()
        servers_added += 1
        log(db, "INFO", "Anime3RB", f"  ↳ Imported '{a3rb_slug}' Ep {ep_num} → ID {ep_id}")
        
    log(db, "INFO", "Anime3RB", f"Done. Matched: {matched} | Created eps: {created} | Servers: {servers_added} | Skipped: {skipped}")
    progress(db, "Anime3RB", f"  ✓ Anime3RB done — {matched} matched, {created} new eps, {servers_added} servers")

# --- Backfill Missing WitAnime Servers ---
def backfill_witanime(db, client):
    import base64

    log(db, "INFO", "WitBackfill", "════════════════════════════════════")
    progress(db, "WitBackfill", "▶ PHASE 4/5 — Backfill Missing WitAnime Servers")
    log(db, "INFO", "WitBackfill", "════════════════════════════════════")
    cur = db.cursor()

    # Find episodes missing WitAnime servers (including those with 0 servers)
    missing = cur.execute("""
        SELECT a.anime_id, a.anime_slug, e.episode_id, e.episode_number
        FROM animes a
        JOIN episodes e ON e.anime_id = a.anime_id
        WHERE a.anime_slug IS NOT NULL AND a.anime_slug != ''
          AND e.episode_number > 0
          AND NOT EXISTS (
              SELECT 1 FROM episode_servers es
              WHERE es.episode_id = e.episode_id AND es.episode_server_id LIKE 'wit_%'
          )
        ORDER BY e.episode_id DESC
        LIMIT ?
    """, (BACKFILL_LIMIT,)).fetchall()

    log(db, "INFO", "WitBackfill", f"Found {len(missing)} episodes missing WitAnime servers")
    if missing:
        progress(db, "WitBackfill", f"  ↳ Found {len(missing)} episodes to backfill — fetching (limit={BACKFILL_LIMIT}, max={BACKFILL_MAX_SECONDS}s)...")

    found = 0
    processed = 0
    skipped_fetch = 0
    consecutive_miss = 0
    phase_start = time.time()
    for aid, slug, ep_id, ep_num in missing:
        processed += 1
        if (processed % BACKFILL_LOG_EVERY == 0) or (processed == len(missing)):
            elapsed = time.time() - phase_start
            progress(db, "WitBackfill", f"  ↳ Progress {processed}/{len(missing)} | backfilled={found} | fetch_miss={skipped_fetch} | elapsed={elapsed:.1f}s")
        if time.time() - phase_start > BACKFILL_MAX_SECONDS:
            log(db, "WARNING", "WitBackfill", f"Time budget reached ({BACKFILL_MAX_SECONDS}s). Stopping this phase early.")
            break

        tkn = ep_token(ep_num)

        # Primary URL patterns based on stored slug
        candidates = [
            f"https://witanime.you/episode/{slug}-%D8%A7%D9%84%D8%AD%D9%84%D9%82%D8%A9-{tkn}/",
            f"https://witanime.you/episode/{slug}-{tkn}/",
            f"https://witanime.you/episode/{slug}/{tkn}/",
            f"https://witanime.you/{slug}/episode-{tkn}/",
        ]

        # Build additional search queries from anime titles
        try:
            title_row = cur.execute('SELECT anime_name, anime_english_title FROM animes WHERE anime_id=?',(aid,)).fetchone()
            eng = title_row[1] if title_row and title_row[1] else None
            name = title_row[0] if title_row and title_row[0] else None
        except Exception:
            eng = None; name = None

        search_terms = []
        if eng:
            search_terms.append(eng)
            search_terms.append(f"{eng} episode {tkn}")
            search_terms.append(f"{eng} ep {tkn}")
        if name:
            search_terms.append(name)
            search_terms.append(f"{name} الحلقة {tkn}")
            search_terms.append(f"{name} حلقة {tkn}")

        # normalize and add search URLs
        for q in search_terms:
            if not q:
                continue
            candidates.append(f"https://witanime.you/?s={urllib.parse.quote_plus(q)}")

        html_text = None
        used_url = None
        for cand in candidates:
            txt = fetch_episode_page(cand)
            if not txt:
                continue
            # If this is a search page, try to find episode links and follow them
            if '/?s=' in cand or cand.endswith('/?s=%s' % urllib.parse.quote_plus(name or '')):
                soup = BeautifulSoup(txt, 'html.parser')
                tried = []
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if href in tried:
                        continue
                    tried.append(href)
                    if '/episode/' not in href and slug not in href:
                        continue
                    txt2 = fetch_episode_page(href)
                    if not txt2:
                        continue
                    zx = re.search(r'(?:var\s+)?_z[HX]\s*=\s*"([^\"]+)"', txt2)
                    zk = re.search(r'(?:var\s+)?_z[WK]\s*=\s*"([^\"]+)"', txt2)
                    if zx and zk:
                        html_text = txt2
                        used_url = href
                        break
                if html_text:
                    break
                else:
                    continue

            zx = re.search(r'(?:var\s+)?_z[HX]\s*=\s*"([^\"]+)"', txt)
            zk = re.search(r'(?:var\s+)?_z[WK]\s*=\s*"([^\"]+)"', txt)
            if zx and zk:
                html_text = txt
                used_url = cand
                break

        if not html_text:
            skipped_fetch += 1
            consecutive_miss += 1
            if consecutive_miss >= BACKFILL_EARLY_ABORT_STREAK:
                log(db, "WARNING", "WitBackfill", f"Consecutive miss streak {consecutive_miss} reached. Aborting backfill early.")
                break
            continue

        # reset miss streak on success
        consecutive_miss = 0

        try:
            zx = re.search(r'(?:var\s+)?_z[HX]\s*=\s*"([^\"]+)"', html_text)
            zk = re.search(r'(?:var\s+)?_z[WK]\s*=\s*"([^\"]+)"', html_text)
            rr = json.loads(base64.b64decode(zx.group(1)).decode())
            cr = json.loads(base64.b64decode(zk.group(1)).decode())
            names = dict(re.findall(r'<a[^>]*data-server-id="(\d+)"[^>]*>([\s\S]*?)</a>', html_text))
            max_srv = cur.execute("SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers").fetchone()[0]

            added = 0
            for i, e in enumerate(rr):
                raw = re.sub(r'[^A-Za-z0-9+/=]', "", e[::-1])
                u = base64.b64decode(raw).decode()
                idx = int(base64.b64decode(cr[i]["k"]).decode())
                off = cr[i]["d"][idx]
                if off > 0:
                    u = u[:-off]
                if u.strip().lstrip("/").startswith("//"):
                    u = "https:" + u.strip().lstrip("/")
                n = re.sub(r'<[^>]+>', "", names.get(str(i), "")).strip()
                t = "yonaplay" if "yonaplay" in u.lower() else "direct"
                max_srv += 1

                if t == "yonaplay":
                    yona_url = u + "&apiKey=23a97133-caf3-4eb4-9466-93d0a4ff8198" if "embed.php?id=" in u else u
                    yona_html = fetch_episode_page(yona_url)
                    if yona_html:
                        for m_sub in re.finditer(r'\{[^}]*?\\"file\\"[^}]*?\}', yona_html):
                            try:
                                d = json.loads(m_sub.group(0))
                                if d.get("file"):
                                    cur.execute(
                                        "INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,'active')",
                                        (max_srv, ep_id, f"wit_{i}", f"{d.get('label','')} {d.get('type','')}", d["file"])
                                    )
                                    max_srv += 1
                                    added += 1
                            except Exception:
                                pass
                else:
                    cur.execute(
                        "INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,'active')",
                        (max_srv, ep_id, f"wit_{i}", n, u)
                    )
                    added += 1

            if added:
                db.commit()
                found += 1
                log(db, "INFO", "WitBackfill", f"  ↳ Backfilled {slug} Ep {ep_num} → +{added} servers (from {used_url})")
        except Exception as e:
            log(db, "ERROR", "WitBackfill", f"Failed to parse/insert servers for {slug} Ep {ep_num}: {e}")

    log(db, "INFO", "WitBackfill", f"Done. Backfilled {found} episodes (processed={processed}, fetch_miss={skipped_fetch})")
    progress(db, "WitBackfill", f"  ✓ WitAnime backfill done — {found} episodes enriched")


# --- Backfill Missing Anime3RB Servers ---
def backfill_anime3rb(db, client):
    log(db, "INFO", "A3RBBackfill", "════════════════════════════════════")
    progress(db, "A3RBBackfill", "▶ PHASE 5/5 — Backfill Missing Anime3RB Servers")
    log(db, "INFO", "A3RBBackfill", "════════════════════════════════════")
    cur = db.cursor()

    # Find episodes missing Anime3RB servers (including those with 0 servers)
    missing = cur.execute("""
        SELECT a.anime_id, a.anime_slug, e.episode_id, e.episode_number
        FROM animes a
        JOIN episodes e ON e.anime_id = a.anime_id
        WHERE a.anime_slug IS NOT NULL AND a.anime_slug != ''
          AND e.episode_number > 0
          AND NOT EXISTS (
              SELECT 1 FROM episode_servers es
              WHERE es.episode_id = e.episode_id AND es.episode_server_id LIKE 'a3rb_%'
          )
        ORDER BY e.episode_id DESC
        LIMIT ?
    """, (BACKFILL_LIMIT,)).fetchall()

    log(db, "INFO", "A3RBBackfill", f"Found {len(missing)} episodes missing Anime3RB servers")

    # Refresh sitemaps to build a quick lookup map (slug/ep -> url)
    sitemap_urls = set()
    try:
        r = httpx.get(A3RB_SITEMAP, timeout=10)
        if r.status_code == 200:
            root = ET.fromstring(r.text)
            # find sitemap index entries
            for s in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                loc = s.text
                if loc and 'videos_' in loc:
                    try:
                        rr = httpx.get(loc, timeout=10)
                        if rr.status_code == 200:
                            xm = ET.fromstring(rr.text)
                            for u in xm.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                                if u.text:
                                    sitemap_urls.add(u.text)
                    except Exception:
                        log(db, "DEBUG", "A3RBBackfill", f"Failed to fetch sub-sitemap: {loc}")
                        continue
        log(db, "INFO", "A3RBBackfill", f"Loaded {len(sitemap_urls)} URLs from sitemaps for lookup")
    except Exception as e:
        log(db, "WARNING", "A3RBBackfill", f"Failed to refresh sitemaps: {e}")

    found = 0
    processed = 0
    skipped = 0
    phase_start = time.time()
    for aid, slug, ep_id, ep_num in missing:
        processed += 1
        if (processed % BACKFILL_LOG_EVERY == 0) or (processed == len(missing)):
            elapsed = time.time() - phase_start
            progress(db, "A3RBBackfill", f"  ↳ Progress {processed}/{len(missing)} | backfilled={found} | miss={skipped} | elapsed={elapsed:.1f}s")
        if time.time() - phase_start > BACKFILL_MAX_SECONDS:
            log(db, "WARNING", "A3RBBackfill", f"Time budget reached ({BACKFILL_MAX_SECONDS}s). Stopping this phase early.")
            break

        # Try to find episode URL from refreshed sitemap
        found_url = None
        token = f"/{slug}/{ep_num}"
        for u in sitemap_urls:
            if token in u:
                found_url = u
                break

        if found_url:
            try:
                max_srv = cur.execute("SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers").fetchone()[0]
                cur.execute(
                    "INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,'active')",
                    (max_srv + 1, ep_id, f"a3rb_{slug}_{ep_num}", f"anime3rb - {ep_num}", found_url)
                )
                db.commit()
                found += 1
                log(db, "INFO", "A3RBBackfill", f"  ↳ Backfilled {slug} Ep {ep_num} via sitemap → {found_url}")
                continue
            except Exception as e:
                log(db, "ERROR", "A3RBBackfill", f"DB insert failed for {slug} Ep {ep_num} via sitemap: {e}")

        # Fallback: try direct episode URL
        a3rb_url = f"https://anime3rb.com/episode/{slug}/{ep_num}"
        try:
            r = client.get(a3rb_url)
            if r.status_code != 200:
                skipped += 1
                continue

            # A3RB page exists — add it as a server
            max_srv = cur.execute("SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers").fetchone()[0]
            cur.execute(
                "INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,'active')",
                (max_srv + 1, ep_id, f"a3rb_{slug}_{ep_num}", f"anime3rb - {ep_num}", a3rb_url)
            )
            db.commit()
            found += 1
            log(db, "INFO", "A3RBBackfill", f"  ↳ Backfilled {slug} Ep {ep_num}")
        except Exception as e:
            skipped += 1
            log(db, "ERROR", "A3RBBackfill", f"Failed to backfill {slug} Ep {ep_num}: {e}")

    log(db, "INFO", "A3RBBackfill", f"Done. Backfilled {found} episodes (processed={processed}, miss={skipped})")
    progress(db, "A3RBBackfill", f"  ✓ Anime3RB backfill done — {found} episodes enriched")

# --- Auto-update curl_cffi ---
def update_curl_cffi():
    """Update curl_cffi to the latest version for best Cloudflare bypass."""
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "--upgrade", "--quiet",
            "curl_cffi"
        ], capture_output=True, text=True, timeout=30)
        if "Successfully installed" in result.stdout:
            return True
    except Exception:
        pass
    return False

# --- Schedule Sync ---
def sync_schedule(db, client):
    log(db, "INFO", "Schedule", "════════════════════════════════════")
    progress(db, "Schedule", "▶ PHASE 0/5 — Syncing Weekly Schedule")
    log(db, "INFO", "Schedule", "════════════════════════════════════")
    cur = db.cursor()
    params = {"list_type": "schedule"}
    data = api_get(db, client, f"animes/get-published-animes?json={urllib.parse.quote(json.dumps(params))}")
    
    if not data or 'response' not in data or not data['response'].get('data'):
        log(db, "WARNING", "Schedule", "Failed to fetch schedule data.")
        return
        
    schedule_data = data['response']['data']
    days_map = {
        'Saturday': 'السبت', 'Sunday': 'الأحد', 'Monday': 'الإثنين',
        'Tuesday': 'الثلاثاء', 'Wednesday': 'الأربعاء',
        'Thursday': 'الخميس', 'Friday': 'الجمعة'
    }
    
    updated = 0
    for day_en, day_ar in days_map.items():
        day_anime = schedule_data.get(day_en) or schedule_data.get(day_ar) or []
        log(db, "DEBUG", "Schedule", f"  ↳ {day_en}: {len(day_anime)} anime")
        for item in day_anime:
            aid = item.get('anime_id')
            if not aid: continue
            try:
                aid_int = int(aid)
                cur.execute("UPDATE animes SET anime_release_day=? WHERE anime_id=?", (day_en, aid_int))
                if cur.rowcount > 0:
                    updated += 1
            except (ValueError, TypeError):
                pass
                
    db.commit()
    log(db, "INFO", "Schedule", f"Updated release_day for {updated} anime entries")
    progress(db, "Schedule", f"  ✓ Schedule sync done — {updated} anime entries updated")

def main():
    global _current_run_id
    db = sqlite3.connect(DB_PATH)
    init_logging_tables(db)
    
    run_id = None
    try:
        cur = db.cursor()
        # Clean up any stale 'running' entries (from crashed previous runs)
        cur.execute("UPDATE sync_runs SET status='failed', summary='Crashed' WHERE status='running'")
        cur.execute("INSERT INTO sync_runs (status) VALUES ('running')")
        run_id = cur.lastrowid
        _current_run_id = run_id
        db.commit()
    except Exception:
        pass
    
    print(f"\n{'═'*50}", flush=True)
    print(f"  AnimeBind Daily Sync — Run #{run_id}", flush=True)
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S UTC')}", flush=True)
    print(f"{'═'*50}\n", flush=True)
    
    log(db, "INFO", "System", f"═══ Daily Sync Started (Run #{run_id}) ═══")
    log(db, "INFO", "System", f"DB: {DB_PATH}")
    log(db, "INFO", "System", f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    log(db, "INFO", "System", f"PID: {os.getpid()}")
    
    start = time.time()
    
    tor_client = get_tor_client()
    direct_client = httpx.Client(headers={"User-Agent": CHROME_UA}, timeout=20, follow_redirects=True)
    
    probe_ports(db)
    global current_tor_idx
    current_tor_idx = 0
    
    sync_schedule(db, tor_client)
    sync_anslayer(db, tor_client)
    
    # WitAnime and Anime3RB servers are now fetched dynamically on-demand
    # via src/lib/dynamic-servers.ts when a user visits a watch page.
    # No bulk scraping needed — each episode gets its servers once, cached in DB.
    
    duration = time.time() - start
    
    # Final DB stats
    try:
        cur2 = db.cursor()
        total_animes    = cur2.execute("SELECT COUNT(*) FROM animes").fetchone()[0]
        total_episodes  = cur2.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        total_servers   = cur2.execute("SELECT COUNT(*) FROM episode_servers").fetchone()[0]
        ans_servers     = cur2.execute("SELECT COUNT(*) FROM episode_servers WHERE episode_server_id LIKE 'ans_%'").fetchone()[0]
        wit_servers     = cur2.execute("SELECT COUNT(*) FROM episode_servers WHERE episode_server_id LIKE 'wit_%'").fetchone()[0]
        a3rb_servers    = cur2.execute("SELECT COUNT(*) FROM episode_servers WHERE episode_server_id LIKE 'a3rb_%'").fetchone()[0]

        summary_str = (f"Duration: {duration:.1f}s | "
                       f"Anime: {total_animes:,} | Episodes: {total_episodes:,} | Servers: {total_servers:,} | "
                       f"Anslayer: {ans_servers:,} | WitAnime: {wit_servers:,} (dynamic) | Anime3RB: {a3rb_servers:,} (dynamic)")
        log(db, "INFO", "System", f"  Final DB state: {summary_str}")
        log(db, "INFO", "System", f"  Servers by provider — Anslayer: {ans_servers:,} | WitAnime: {wit_servers:,} (on-demand) | Anime3RB: {a3rb_servers:,} (on-demand)")
    except Exception:
        summary_str = f"Duration: {duration:.1f}s"

    print(f"\n{'═'*50}", flush=True)
    print(f"  Sync Complete in {duration:.1f}s", flush=True)
    print(f"{'═'*50}\n", flush=True)
    
    log(db, "INFO", "System", f"═══ Daily Sync Completed Successfully in {duration:.1f}s ═══")
    progress(db, "System", f"✓ ALL PHASES COMPLETE — {duration:.1f}s total runtime")
    
    if run_id:
        try:
            cur = db.cursor()
            cur.execute("UPDATE sync_runs SET finished_at=datetime('now'), status='completed', summary=? WHERE id=?",
                        (summary_str, run_id))
            db.commit()
        except Exception:
            pass
    
    direct_client.close()
    db.close()

if __name__ == "__main__":
    main()
