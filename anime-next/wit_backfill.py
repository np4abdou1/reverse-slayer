#!/usr/bin/env python3
"""Scrape WitAnime full catalog via WP API, build slug map, match to Anslayer DB, backfill servers."""
import sqlite3, json, re, base64, socket, time, sys, threading, random
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from colorama import init, Fore, Style
init(autoreset=True)

DB = '/home/ubuntu/Projects/reverse-slayer/anime-next/data/anime.db'
WIT = 'https://witanime.you'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
YONA_KEY = '23a97133-caf3-4eb4-9466-93d0a4ff8198'
TOR_PORTS = [9050, 9051, 9052, 9053, 9054, 9055, 9056, 9057, 9058, 9059]
WORKERS = int(sys.argv[1]) if len(sys.argv) > 1 else 5

good_ports = [p for p in TOR_PORTS if socket.socket().connect_ex(('127.0.0.1', p)) == 0]
_ep_clients: dict[int, httpx.Client] = {}
_cl_lock = threading.Lock()

def _new_circuit(port: int):
    try:
        s = socket.socket(); s.settimeout(2)
        s.connect(("127.0.0.1", port))
        s.sendall(b"AUTHENTICATE\r\nSIGNAL NEWNYM\r\nQUIT\r\n")
        s.close()
    except Exception: pass

def _pick() -> int:
    return random.choice(good_ports) if good_ports else TOR_PORTS[0]

def _get_client() -> httpx.Client:
    tid = threading.get_ident()
    with _cl_lock:
        if tid not in _ep_clients:
            t = httpx.HTTPTransport(proxy=f"socks5://127.0.0.1:{_pick()}")
            _ep_clients[tid] = httpx.Client(
                transport=t,
                headers={"User-Agent": UA, "Referer": "https://www.google.com/"},
                timeout=30, follow_redirects=True)
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
        except Exception:
            _drop()
            time.sleep(0.5 + attempt * 0.5)
    return None

def gen_slug(s):
    if not s: return ''
    s = s.lower()
    for a,b in [('ä','a'),('æ','a'),('ë','e'),('é','e'),('ö','o'),('ü','u'),('ñ','n'),('ç','c'),('ß','ss')]:
        s = s.replace(a,b)
    s = re.sub(r'\s*\([^)]*\)\s*$', '', s)
    s = re.sub(r'[^a-z0-9\u0600-\u06ff\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s).strip('-')
    return s

def decrypt_watch(html):
    zx = re.search(r'(?:var\s+)?_z[HX]\s*="([^"]+)"', html)
    zk = re.search(r'(?:var\s+)?_z[WK]\s*="([^"]+)"', html)
    if not zx or not zk: return []
    try:
        rr = json.loads(base64.b64decode(zx.group(1)).decode())
        cr = json.loads(base64.b64decode(zk.group(1)).decode())
    except: return []
    names = dict(re.findall(r'<a[^>]*data-server-id="(\d+)"[^>]*>([\s\S]*?)</a>', html))
    out = []
    for i, e in enumerate(rr):
        try:
            raw = re.sub(r'[^A-Za-z0-9+/=]', '', e[::-1])
            u = base64.b64decode(raw).decode()
            idx2 = int(base64.b64decode(cr[i]['k']).decode())
            off = cr[i]['d'][idx2]
            if off > 0: u = u[:-off]
            if u.strip().lstrip('/').startswith('//'): u = 'https:' + u.strip().lstrip('/')
            n = re.sub(r'<[^>]+>', '', names.get(str(i), '')).strip()
            t = 'yonaplay' if 'yonaplay' in u.lower() else 'direct'
            out.append({'n': n, 't': t, 'u': u})
        except: pass
    return out

def decrypt_dl(html):
    _m = re.search(r'(?:window\.|var\s+)?_m\s*=\s*(.*?);', html)
    _t = re.search(r'(?:window\.|var\s+)?_t\s*=\s*(.*?);', html)
    _s = re.search(r'(?:window\.|var\s+)?_s\s*=\s*(.*?);', html)
    if not _m or not _t or not _s: return []
    try:
        mv = json.loads(_m.group(1)); tv = json.loads(_t.group(1)); sv = json.loads(_s.group(1))
        secret = base64.b64decode(mv['r']); n = int(tv['l'])
    except: return []
    qmap = {}
    for ul in re.findall(r'<ul class="quality-list">(.*?)</ul>', html, re.DOTALL):
        li = re.search(r'<li>(.*?)</li>', ul)
        if not li: continue
        ql = li.group(1).strip()
        qg = 'FHD' if any(x in ql for x in ('FHD','خارقة')) else 'HD' if any(x in ql for x in ('HD','عالية')) else 'SD' if any(x in ql for x in ('SD','متوسطة')) else '?'
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
            seq = json.loads(sd.decode('utf-8', errors='ignore'))
            chunks = [bytes.fromhex(h) for h in pd]
            dec = [bytearray(chunks[j][k] ^ secret[k % len(secret)] for k in range(len(chunks[j]))) for j in range(len(chunks))]
            arr = [None] * len(seq)
            for p2, v in enumerate(seq): arr[v] = dec[p2].decode('utf-8', errors='ignore')
            u = ''.join(arr)
            if u.strip().lstrip('/').startswith('//'): u = 'https:' + u.strip().lstrip('/')
            q = qmap.get(i, ('unknown', 'SD'))
            out.append({'n': q[0], 'qg': q[1], 'u': u})
        except: pass
    return out

def parse_yona(html):
    _OD_RE = re.compile(r'<div class="OD([^"]*)">([\s\S]*?)</div>\s*(?=<div class="OD|</div>|$)', re.DOTALL)
    _LI_RE = re.compile(r"go_to_player\('([^']+)'\)[\s\S]*?<span>([\s\S]*?)</span>[\s\S]*?<p>([\s\S]*?)</p>", re.DOTALL)
    out = []
    for od_m in _OD_RE.finditer(html):
        cls, body = od_m.group(1), od_m.group(2)
        lang = 'SUB2' if 'OD_SUB2' in cls else 'DUB' if 'OD_DUB' in cls else 'SUB'
        for li in _LI_RE.finditer(body):
            b64, sn = li.group(1), re.sub(r'<[^>]+>', '', li.group(2)).strip()
            qr = re.sub(r'<[^>]+>', '', li.group(3)).strip().rstrip('- ').strip()
            qr = {'1080p':'FHD','720p':'HD','480p':'SD','360p':'SD'}.get(qr, qr)
            try:
                pad = b64 + '=' * ((4 - len(b64) % 4) % 4)
                inner = base64.urlsafe_b64decode(pad).decode()
                out.append({'sn': sn, 'q': qr, 'l': lang, 'u': inner})
            except: continue
    return out

def decrypt_eps(html):
    """Decrypt processedEpisodeData from anime page to get episode list with URLs."""
    m = re.search(r"processedEpisodeData\s*=\s*'([^']+)'", html)
    if not m: return []
    parts = m.group(1).split(".")
    if len(parts) != 2: return []
    try:
        d = base64.b64decode(parts[0]); k = base64.b64decode(parts[1])
        return json.loads(bytearray(d[i] ^ k[i % len(k)] for i in range(len(d))).decode())
    except: return []

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Step 1: Fetch all WitAnime slugs
    print(f'{Fore.CYAN}=== Step 1: Fetching WitAnime catalog ==={Style.RESET_ALL}')
    wit_slugs = {}
    page = 1
    while True:
        r = fetch(f'{WIT}/wp-json/wp/v2/anime?per_page=100&page={page}&_fields=id,slug,name')
        if not r or r.status_code != 200: break
        data = r.json()
        if not data: break
        for item in data:
            slug = item.get('slug', '')
            name = item.get('name', '')
            if slug:
                wit_slugs[slug] = {'id': item['id'], 'name': name}
        total_pages = int(r.headers.get('X-WP-TotalPages', 0))
        print(f'  Page {page}/{total_pages} | {len(wit_slugs)} slugs so far')
        if page >= total_pages: break
        page += 1
        time.sleep(0.3)
    print(f'  {Fore.GREEN}Total WitAnime slugs: {len(wit_slugs)}{Style.RESET_ALL}')

    # Step 2: Match WitAnime → Anslayer (only match what actually exists on WitAnime)
    print(f'\n{Fore.CYAN}=== Step 2: Matching WitAnime → Anslayer ==={Style.RESET_ALL}')
    anslayer_animes = cur.execute('SELECT anime_id, anime_name, anime_english_title, anime_slug FROM animes WHERE length(anime_slug) > 2').fetchall()
    
    # Build Anslayer lookup: normalized slug → aid
    local_lookup = {}
    for aid, name, eng, slug in anslayer_animes:
        local_lookup[slug] = aid
        local_lookup[gen_slug(slug)] = aid
        if name: local_lookup[gen_slug(name)] = aid
        if eng: local_lookup[gen_slug(eng)] = aid
    
    # For each WitAnime anime, find matching Anslayer anime
    matched = {}  # aid -> wit_data
    unmatched_wit = 0
    for wslug, wdata in wit_slugs.items():
        # Try direct match
        if wslug in local_lookup:
            matched[local_lookup[wslug]] = wdata
            continue
        # Try normalized WitAnime slug
        nw = gen_slug(wslug)
        if nw in local_lookup:
            matched[local_lookup[nw]] = wdata
            continue
        # Try base match (strip season/movie/ova suffixes)
        base = re.sub(r'-\d+(nd|rd|th|st)?-season.*$', '', wslug)
        base = re.sub(r'-part-\d+.*$', '', base)
        base = re.sub(r'-movie-\d+.*$', '', base)
        base = re.sub(r'-ova.*$', '', base)
        base = re.sub(r'-special.*$', '', base)
        base = re.sub(r'-\d{4}$', '', base)
        if base != wslug and base in local_lookup:
            matched[local_lookup[base]] = wdata
            continue
        unmatched_wit += 1
    
    print(f'  {Fore.GREEN}Matched {len(matched)} WitAnime → Anslayer anime{Style.RESET_ALL}')
    print(f'  {Fore.YELLOW}Unmatched WitAnime: {unmatched_wit}/{len(wit_slugs)}{Style.RESET_ALL}')

    # Step 3: Find episodes needing backfill
    print(f'\n{Fore.CYAN}=== Step 3: Finding episodes to backfill ==={Style.RESET_ALL}')
    lacking = cur.execute('''
        SELECT e.episode_id, e.episode_number, e.anime_id
        FROM episodes e
        WHERE e.anime_id IN ({})
          AND NOT EXISTS (SELECT 1 FROM episode_servers es WHERE es.episode_id = e.episode_id AND es.episode_server_id LIKE 'wit_%')
        ORDER BY e.episode_id DESC
        LIMIT 5000
    '''.format(','.join(str(aid) for aid in matched.keys()))).fetchall()
    
    print(f'  Episodes to backfill: {len(lacking)}')

    # Step 3.5: Pre-fetch anime pages and build episode URL maps (parallel)
    print(f'\n{Fore.CYAN}=== Step 3.5: Building episode URL maps from anime pages ==={Style.RESET_ALL}')
    anime_ep_map = {}  # aid -> {ep_num: url}
    anime_slugs = {}   # aid -> wit_slug
    
    # Group by anime_id
    anime_ids = set(aid for _, _, aid in lacking)
    for aid in anime_ids:
        wit = matched.get(aid)
        if not wit: continue
        wit_slug = None
        for s, v in wit_slugs.items():
            if v['id'] == wit['id']:
                wit_slug = s
                break
        if not wit_slug: continue
        anime_slugs[aid] = wit_slug
    
    # Fetch anime pages in parallel
    def fetch_anime_page(aid, wit_slug):
        r = fetch(f'{WIT}/anime/{wit_slug}/', retries=3)
        if not r or r.status_code != 200: return (aid, None)
        eps = decrypt_eps(r.text)
        if not eps: return (aid, None)
        ep_map = {}
        for ep in eps:
            ep_num = ep.get('number', '')
            ep_url = ep.get('url', '')
            if ep_num and ep_url:
                try: ep_map[float(ep_num)] = ep_url
                except: pass
        return (aid, ep_map if ep_map else None)
    
    done = [0]
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_anime_page, aid, slug): aid for aid, slug in anime_slugs.items()}
        for fut in as_completed(futures):
            aid, ep_map = fut.result()
            done[0] += 1
            if ep_map:
                anime_ep_map[aid] = ep_map
            if done[0] % 50 == 0:
                print(f'  Fetched {done[0]}/{len(anime_slugs)} anime pages ({len(anime_ep_map)} with episodes)')
    
    print(f'  Built episode maps for {len(anime_ep_map)}/{len(anime_slugs)} anime')

    # Step 4: Backfill in parallel
    print(f'\n{Fore.CYAN}=== Step 4: Backfilling with {WORKERS} workers ==={Style.RESET_ALL}')
    
    db_lock = threading.Lock()
    max_id = [cur.execute('SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers').fetchone()[0]]
    ok = [0]; fail = [0]; total = [0]
    fail_reasons = {}
    
    def worker(row):
        ep_id, ep_num, aid = row
        ep_map = anime_ep_map.get(aid)
        if not ep_map: return (ep_id, aid, ep_num, False, 0, 'no_anime_page')
        
        # Find matching episode URL by number
        ep_url = None
        if ep_num in ep_map:
            ep_url = ep_map[ep_num]
        else:
            # Try integer match
            try:
                ep_int = int(ep_num)
                if ep_int in ep_map:
                    ep_url = ep_map[ep_int]
            except: pass
        
        if not ep_url: return (ep_id, aid, ep_num, False, 0, 'ep_not_in_list')
        
        r = fetch(ep_url, retries=2)
        if not r: return (ep_id, aid, ep_num, False, 0, 'fetch_fail')
        if r.status_code == 404: return (ep_id, aid, ep_num, False, 0, '404')
        if r.status_code == 403: return (ep_id, aid, ep_num, False, 0, '403_blocked')
        if r.status_code != 200: return (ep_id, aid, ep_num, False, 0, f'http_{r.status_code}')
        
        html = r.text
        if not re.search(r'_z[HX]', html): return (ep_id, aid, ep_num, False, 0, 'no_watch_data')
        
        results = []
        for w in decrypt_watch(html):
            if w['t'] == 'yonaplay':
                yu = w['u'] + f'&apiKey={YONA_KEY}' if 'embed.php?id=' in w['u'] else w['u']
                yr = fetch(yu, retries=1)
                if yr:
                    for ys in parse_yona(yr.text):
                        results.append((ep_id, f"wit_{ep_id}_yona_{ys['sn']}_{ys['q']}", f"Yona: {ys['sn']} - {ys['q']}", ys['u']))
            else:
                results.append((ep_id, f"wit_{ep_id}_watch_{w['n']}", w['n'], w['u']))
        for d in decrypt_dl(html):
            results.append((ep_id, f"wit_{ep_id}_dl_{d['n']}_{d['qg']}", f"Download: {d['n']} - {d['qg']}", d['u']))
        
        return (ep_id, aid, ep_num, True, len(results), 'ok', results)
    
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
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
                        print(f"  [{ok[0]+fail[0]}/{len(lacking)}] {Fore.GREEN}OK  {Style.RESET_ALL} | aid={aid} Ep {ep_num} | +{count} servers")
                    else:
                        fail[0] += 1
                        fail_reasons[reason] = fail_reasons.get(reason, 0) + 1
                        reason_map = {
                            'no_match': 'not in matched list',
                            'no_slug': 'WitAnime slug not found',
                            'fetch_fail': 'request failed',
                            '404': 'page not found',
                            '403_blocked': 'blocked by Cloudflare',
                            'no_watch_data': 'no decryption data on page',
                        }
                        desc = reason_map.get(reason, reason)
                        print(f"  [{ok[0]+fail[0]}/{len(lacking)}] {Fore.RED}FAIL{Style.RESET_ALL} | aid={aid} Ep {ep_num} | {Fore.YELLOW}{desc}{Style.RESET_ALL}")
                    total[0] += 1
                    if total[0] % 100 == 0:
                        conn.commit()
                        print(f"  {Fore.MAGENTA}--- {ok[0]} ok, {fail[0]} fail, {total[0]}/{len(lacking)} ---{Style.RESET_ALL}")
            except Exception as e:
                with db_lock:
                    fail[0] += 1; total[0] += 1
                    fail_reasons['crash'] = fail_reasons.get('crash', 0) + 1
                    print(f"  [{total[0]}/{len(lacking)}] {Fore.RED}CRASH{Style.RESET_ALL} | {str(e)[:80]}")
    
    conn.commit()
    
    print(f'\n{Fore.CYAN}=== Results ==={Style.RESET_ALL}')
    print(f'  {Fore.GREEN}OK: {ok[0]}{Style.RESET_ALL}')
    print(f'  {Fore.RED}FAIL: {fail[0]}{Style.RESET_ALL}')
    if fail_reasons:
        print(f'  {Fore.YELLOW}Fail breakdown:{Style.RESET_ALL}')
        for reason, count in sorted(fail_reasons.items(), key=lambda x: -x[1]):
            print(f'    {reason}: {count}')
    
    cur.execute('SELECT count(*) FROM episode_servers WHERE episode_server_name LIKE "%FHD%"')
    print(f'\n  FHD servers: {cur.fetchone()[0]}')
    cur.execute('SELECT count(*) FROM episode_servers WHERE episode_server_id LIKE "wit_%"')
    print(f'  Wit servers: {cur.fetchone()[0]}')
    conn.close()

if __name__ == '__main__':
    main()
