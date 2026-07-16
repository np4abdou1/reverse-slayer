import Database from 'better-sqlite3';
import path from 'path';
import { SocksProxyAgent } from 'socks-proxy-agent';
import https from 'https';
import http from 'http';
import { resolveAnime3rbEpisode } from './anime3rb-resolver';

const TOR_PORTS = [9050, 9051, 9052, 9053, 9054, 9055, 9056, 9058, 9059];
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36';
const WIT_BASE = 'https://witanime.you';
const YONA_KEY = '23a97133-caf3-4eb4-9466-93d0a4ff8198';

let _torIdx = 0;
let _writableDb: Database.Database | null = null;

function getWritableDb(): Database.Database {
  if (!_writableDb) {
    const dbPath = path.join(process.cwd(), 'data/anime.db');
    _writableDb = new Database(dbPath);
    _writableDb.pragma('journal_mode = WAL');
  }
  return _writableDb;
}

function nextTorPort(): number {
  const port = TOR_PORTS[_torIdx % TOR_PORTS.length];
  _torIdx++;
  return port;
}

function httpGetViaTor(url: string, timeout = 15000): Promise<string | null> {
  return new Promise((resolve) => {
    const agent = new SocksProxyAgent(`socks5://127.0.0.1:${nextTorPort()}`);
    const u = new URL(url);
    const mod = u.protocol === 'https:' ? https : http;
    const req = mod.get(url, {
      agent,
      timeout,
      headers: { 'User-Agent': UA, 'Referer': 'https://www.google.com/' },
    }, (res) => {
      if (res.statusCode !== 200) { resolve(null); return; }
      let body = '';
      res.on('data', (chunk: string) => body += chunk);
      res.on('end', () => resolve(body));
    });
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
  });
}

function epToken(epNum: number): string {
  if (Number.isInteger(epNum)) return String(epNum);
  return String(epNum).replace(/0+$/, '').replace(/\.$/, '');
}

export interface DynamicServer {
  id: string;
  label: string;
  name: string;
  url: string;
  quality: string;
}

interface WitServer {
  index: number;
  name: string;
  type: 'direct' | 'yonaplay';
  url: string;
}

function decryptWitWatchServers(html: string): WitServer[] {
  const zxMatch = html.match(/(?:var\s+)?_z[HX]\s*=\s*"([^"]+)"/);
  const zkMatch = html.match(/(?:var\s+)?_z[WK]\s*=\s*"([^"]+)"/);
  if (!zxMatch || !zkMatch) return [];

  try {
    const rr = JSON.parse(Buffer.from(zxMatch[1], 'base64').toString());
    const cr = JSON.parse(Buffer.from(zkMatch[1], 'base64').toString());

    const nameMap: Record<string, string> = {};
    const nameRegex = /<a[^>]*data-server-id="(\d+)"[^>]*>([\s\S]*?)<\/a>/g;
    let nm;
    while ((nm = nameRegex.exec(html)) !== null) {
      nameMap[nm[1]] = nm[2].replace(/<[^>]+>/g, '').trim();
    }

    const servers: WitServer[] = [];
    for (let i = 0; i < rr.length; i++) {
      try {
        const reversed = String(rr[i]).split('').reverse().join('');
        const raw = reversed.replace(/[^A-Za-z0-9+/=]/g, '');
        let url = Buffer.from(raw, 'base64').toString();
        const idx = parseInt(Buffer.from(String(cr[i].k), 'base64').toString());
        const off = cr[i].d[idx];
        if (off > 0) url = url.slice(0, -off);
        if (url.startsWith('//')) url = 'https:' + url;

        const name = nameMap[String(i)] || '';
        const type: 'direct' | 'yonaplay' = url.toLowerCase().includes('yonaplay') ? 'yonaplay' : 'direct';

        servers.push({ index: i, name, type, url });
      } catch {}
    }
    return servers;
  } catch {
    return [];
  }
}

async function expandYonaplay(url: string): Promise<Array<{ name: string; quality: string; url: string }>> {
  const fullUrl = url.includes('embed.php?id=') ? `${url}&apiKey=${YONA_KEY}` : url;
  const html = await httpGetViaTor(fullUrl, 10000);
  if (!html) return [];

  const results: Array<{ name: string; quality: string; url: string }> = [];
  const regex = /\{[^}]*?"file"[^}]*?\}/g;
  let m;
  while ((m = regex.exec(html)) !== null) {
    try {
      const d = JSON.parse(m[0]);
      if (d.file) {
        results.push({
          name: d.label || d.type || '',
          quality: d.label || '',
          url: d.file,
        });
      }
    } catch {}
  }
  return results;
}

async function storeWitServers(
  db: Database.Database,
  episodeId: number,
  servers: WitServer[]
): Promise<DynamicServer[]> {
  const maxIdRow = db.prepare('SELECT COALESCE(MAX(episode_url_id), 0) as m FROM episode_servers').get() as { m: number };
  let nextId = maxIdRow.m + 1;

  const insert = db.prepare(
    'INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?, ?, ?, ?, ?, ?)'
  );

  const results: DynamicServer[] = [];

  const insertAll = db.transaction(() => {
    for (const srv of servers) {
      insert.run(nextId, episodeId, `wit_${episodeId}_${srv.index}`, srv.name, srv.url, 'active');
      nextId++;
      results.push({
        id: String(nextId - 1),
        label: srv.name || 'WitAnime',
        name: srv.name.split(' - ')[0] || 'WitAnime',
        url: srv.url,
        quality: '',
      });
    }
  });
  insertAll();

  // Expand yonaplay sub-servers
  for (const srv of servers) {
    if (srv.type === 'yonaplay') {
      const subs = await expandYonaplay(srv.url);
      if (subs.length > 0) {
        const subInsert = db.transaction(() => {
          for (const sub of subs) {
            insert.run(nextId, episodeId, `wit_${episodeId}_${srv.index}_sub`, `${sub.name} ${sub.quality}`.trim(), sub.url, 'active');
            nextId++;
            results.push({
              id: String(nextId - 1),
              label: `${sub.name} ${sub.quality}`.trim() || 'WitAnime',
              name: sub.name || 'WitAnime',
              url: sub.url,
              quality: sub.quality,
            });
          }
        });
        subInsert();
      }
    }
  }

  return results;
}

export async function fetchWitAnimeServers(
  animeId: number,
  episodeId: number,
  slug: string,
  epNum: number
): Promise<DynamicServer[]> {
  const db = getWritableDb();

  const existing = db.prepare(
    "SELECT * FROM episode_servers WHERE episode_id = ? AND episode_server_id LIKE 'wit_%'"
  ).all(episodeId) as Array<Record<string, unknown>>;
  if (existing.length > 0) {
    return existing.map(s => ({
      id: String(s.episode_url_id),
      label: (s.episode_server_name as string) || 'WitAnime',
      name: ((s.episode_server_name as string) || 'WitAnime').split(' - ')[0] || 'WitAnime',
      url: s.episode_url as string,
      quality: '',
    }));
  }

  const tkn = epToken(epNum);

  // Also fetch anime names for additional slug candidates
  const nameRow = db.prepare('SELECT anime_name, anime_english_title FROM animes WHERE anime_id = ?').get(animeId) as Record<string, string> | undefined;
  const altNames: string[] = [];
  if (nameRow) {
    if (nameRow.anime_name) altNames.push(nameRow.anime_name.toLowerCase().replace(/[^a-z0-9\u0600-\u06ff\s-]+/g, '').replace(/[\s_]+/g, '-').replace(/-+/g, '-'));
    if (nameRow.anime_english_title) altNames.push(nameRow.anime_english_title.toLowerCase().replace(/[^a-z0-9\u0600-\u06ff\s-]+/g, '').replace(/[\s_]+/g, '-').replace(/-+/g, '-'));
  }

  const candidates = [
    // Try anslayer slug patterns
    `${WIT_BASE}/episode/${slug}-%D8%A7%D9%84%D8%AD%D9%84%D9%82%D8%A9-${tkn}/`,
    `${WIT_BASE}/episode/${slug}-${tkn}/`,
    `${WIT_BASE}/episode/${slug}/${tkn}/`,
    `${WIT_BASE}/${slug}/episode-${tkn}/`,
  ];

  // Try alternative name slugs
  for (const alt of altNames) {
    if (alt === slug) continue;
    candidates.push(`${WIT_BASE}/episode/${alt}-%D8%A7%D9%84%D8%AD%D9%84%D9%82%D8%A9-${tkn}/`);
    candidates.push(`${WIT_BASE}/episode/${alt}-${tkn}/`);
  }

  // Add search-based fallback candidates
  const searchTerms: string[] = [];
  if (nameRow?.anime_english_title) searchTerms.push(nameRow.anime_english_title);
  if (nameRow?.anime_name) searchTerms.push(nameRow.anime_name);
  for (const q of searchTerms) {
    candidates.push(`${WIT_BASE}/?s=${encodeURIComponent(q)}`);
  }

  for (const url of candidates) {
    const html = await httpGetViaTor(url);
    if (!html) continue;

    // If this is a search results page, follow episode links
    if (url.includes('/?s=')) {
      const links = html.match(/href="(https?:\/\/[^"]+\/episode\/[^"]+)"/g);
      if (!links) continue;
      for (const link of links) {
        const href = (link.match(/href="([^"]+)"/) || [])[1];
        if (!href) continue;
        const epHtml = await httpGetViaTor(href, 10000);
        if (!epHtml) continue;
        const epServers = decryptWitWatchServers(epHtml);
        if (epServers.length > 0) {
          return await storeWitServers(db, episodeId, epServers);
        }
      }
      continue;
    }

    const servers = decryptWitWatchServers(html);
    if (servers.length === 0) continue;

    return await storeWitServers(db, episodeId, servers);
  }

  return [];
}

export async function fetchAnime3rbServers(
  animeId: number,
  episodeId: number,
  slug: string,
  epNum: number
): Promise<DynamicServer[]> {
  const db = getWritableDb();

  const existing = db.prepare(
    "SELECT * FROM episode_servers WHERE episode_id = ? AND episode_server_id LIKE 'a3rb_%'"
  ).all(episodeId) as Array<Record<string, unknown>>;
  if (existing.length > 0) {
    return existing.map(s => ({
      id: String(s.episode_url_id),
      label: (s.episode_server_name as string) || 'Anime3RB',
      name: 'Anime3RB',
      url: s.episode_url as string,
      quality: '',
    }));
  }

  const tkn = epToken(epNum);
  const url = `https://anime3rb.com/episode/${slug}/${tkn}`;

  const sources = await resolveAnime3rbEpisode(url);
  if (sources.length === 0) return [];

  const maxIdRow = db.prepare('SELECT COALESCE(MAX(episode_url_id), 0) as m FROM episode_servers').get() as { m: number };
  let nextId = maxIdRow.m + 1;

  const insert = db.prepare(
    'INSERT OR IGNORE INTO episode_servers (episode_url_id, episode_id, episode_server_id, episode_server_name, episode_url, episode_server_status) VALUES (?, ?, ?, ?, ?, ?)'
  );

  const results: DynamicServer[] = [];

  const insertAll = db.transaction(() => {
    for (const src of sources) {
      const serverId = `a3rb_${slug}_${tkn}_${src.label}`;
      insert.run(nextId, episodeId, serverId, `Anime3RB ${src.label}`, src.url, 'active');
      results.push({
        id: String(nextId),
        label: `Anime3RB ${src.label}`,
        name: 'Anime3RB',
        url: src.url,
        quality: src.label.replace(/[^\dp]/g, '') || src.label,
      });
      nextId++;
    }
  });
  insertAll();

  return results;
}
