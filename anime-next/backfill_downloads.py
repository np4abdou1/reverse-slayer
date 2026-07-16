#!/usr/bin/env python3
"""Re-scrape download servers for episodes that have WitAnime watch servers but no download servers."""
import sqlite3, json, re, base64, socket, time, sys
from curl_cffi import requests

DB = '/home/ubuntu/Projects/reverse-slayer/anime-next/data/anime.db'
WIT = 'https://witanime.you'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
PROXY_PORTS = [40000, 9050, 9051, 9052, 9053, 9054, 9055, 9056, 9057, 9058, 9059]
BATCH = int(sys.argv[1]) if len(sys.argv) > 1 else 200

active_ports = [p for p in PROXY_PORTS if socket.socket().connect_ex(('127.0.0.1', p)) == 0]
idx = 0

def get_proxy():
    global idx
    p = active_ports[idx % len(active_ports)]
    idx += 1
    if p == 40000:
        return {'http': 'http://127.0.0.1:40000', 'https': 'http://127.0.0.1:40000'}
    return {'http': f'socks5://127.0.0.1:{p}', 'https': f'socks5://127.0.0.1:{p}'}

def fetch(url):
    for _ in range(2):
        try:
            r = requests.get(url, headers={'User-Agent': UA}, proxies=get_proxy(), impersonate='chrome124', timeout=8)
            if r.status_code == 200: return r.text
        except: pass
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

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute('''
        SELECT e.episode_id, e.episode_number, a.anime_id, a.anime_slug, a.anime_name
        FROM episodes e
        JOIN animes a ON e.anime_id = a.anime_id
        WHERE EXISTS (SELECT 1 FROM episode_servers es WHERE es.episode_id = e.episode_id AND es.episode_server_id LIKE 'wit_%watch_%')
          AND NOT EXISTS (SELECT 1 FROM episode_servers es WHERE es.episode_id = e.episode_id AND es.episode_server_id LIKE 'wit_%dl_%')
        ORDER BY e.episode_id DESC
        LIMIT ?
    ''', (BATCH,))
    rows = cur.fetchall()
    print(f'Re-scraping downloads for {len(rows)} episodes...')

    max_id = cur.execute('SELECT COALESCE(MAX(episode_url_id), 0) FROM episode_servers').fetchone()[0]
    fixed = 0
    skipped = 0

    for ep_id, ep_num, aid, slug, name in rows:
        tkn = str(int(ep_num)) if ep_num.is_integer() else str(ep_num)
        candidates = [
            f'{WIT}/episode/{slug}-%D8%A7%D9%84%D8%AD%D9%84%D9%82%D8%A9-{tkn}/',
            f'{WIT}/episode/{slug}-{tkn}/',
        ]
        if name:
            alt = gen_slug(name)
            if alt and alt != slug:
                candidates.append(f'{WIT}/episode/{alt}-%D8%A7%D9%84%D8%AD%D9%84%D9%82%D8%A9-{tkn}/')

        html = None
        for url in candidates:
            html = fetch(url)
            if html and re.search(r'_m\s*=', html): break

        if html:
            dls = decrypt_dl(html)
            for d in dls:
                max_id += 1
                cur.execute('INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?,?,?,?,?,?)',
                            (max_id, ep_id, f'wit_{ep_id}_dl_{d["n"]}_{d["qg"]}', f'Download: {d["n"]} - {d["qg"]}', d['u'], 'active'))
            fixed += 1
        else:
            skipped += 1

        if (fixed + skipped) % 20 == 0:
            conn.commit()
            print(f'  Progress: {fixed} fixed, {skipped} skipped ({fixed + skipped}/{len(rows)})')

    conn.commit()
    print(f'Done. Fixed: {fixed}, Skipped: {skipped}')

    cur.execute('SELECT count(*) FROM episode_servers WHERE episode_server_name LIKE "%FHD%"')
    print(f'Total FHD servers: {cur.fetchone()[0]}')
    cur.execute('SELECT count(DISTINCT episode_id) FROM episode_servers WHERE episode_server_name LIKE "%FHD%"')
    print(f'Episodes with FHD: {cur.fetchone()[0]}')
    conn.close()

if __name__ == '__main__':
    main()
