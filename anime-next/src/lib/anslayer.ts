import Database from 'better-sqlite3';
import path from 'path';
import { augmentWithEnglishTitles } from './augment';
import { ANSLAYER_BASE, CLIENT_ID, CLIENT_SECRET, CHROME_UA, SERVER_MAP } from './constants';
import { resolveStreamUrl } from './extractors';
import { resolveAnime3rbEpisode } from './anime3rb-resolver';
import { fetchWitAnimeServers, fetchAnime3rbServers } from './dynamic-servers';

// ── Database connection (singleton) ─────────────────────────────────────────
const globalForDb = globalThis as any;
function getDb() {
  if (!globalForDb.__animeDb) {
    const dbPath = path.join(process.cwd(), 'data/anime.db');
    globalForDb.__animeDb = new Database(dbPath, { readonly: true });
    globalForDb.__animeDb.pragma('journal_mode = WAL');
    globalForDb.__animeDb.pragma('cache_size = -64000');
  }
  return globalForDb.__animeDb;
}

function getWritableDb() {
  if (!globalForDb.__animeWritableDb) {
    const dbPath = path.join(process.cwd(), 'data/anime.db');
    globalForDb.__animeWritableDb = new Database(dbPath);
    globalForDb.__animeWritableDb.pragma('journal_mode = WAL');
  }
  return globalForDb.__animeWritableDb;
}

// ── Jikan poster cache ─────────────────────────────────────────────────────
const JIKAN_BASE = 'https://api.jikan.moe/v4';
const POSTER_BATCH_SIZE = 3;
const POSTER_BATCH_DELAY = 1200; // ms between batches (public Jikan rate limit)

export async function enrichMalImages(animes: any[]): Promise<any[]> {
  return animes;
}

// ── Raw API fetch (for live data only: episode servers, characters, stats) ──
async function rawApi(path: string, body?: any) {
  const url = path.startsWith('http') ? path : `${ANSLAYER_BASE}${path}`;
  const headers: any = {
    'Client-Id': CLIENT_ID,
    'Client-Secret': CLIENT_SECRET,
    'Accept': 'application/json',
    'User-Agent': CHROME_UA,
  };
  const opts: any = { headers };
  if (body) {
    opts.method = 'POST';
    opts.body = `json=${encodeURIComponent(JSON.stringify(body))}`;
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
  }
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    const res = await fetch(url, { ...opts, signal: controller.signal });
    clearTimeout(timer);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

// ── Anime list (paginated, filtered) ────────────────────────────────────────
export async function getAnimeList(listType: string = 'anime_list', limit: number = 24, offset: number = 0, extraParams: any = {}) {
  const db = getDb();
  let conditions: string[] = [];
  let params: any[] = [];
  let orderBy = 'anime_name ASC';
  let joinClause = '';
  let tbl = '';

  // Handle list types
  switch (listType) {
    case 'top_anime':
    case 'top_tv':
      orderBy = 'CAST(anime_rating AS REAL) DESC, anime_rating_user_count DESC';
      conditions.push("anime_status != 'Not Yet Aired'");
      if (listType === 'top_tv') { conditions.push("anime_type = 'TV'"); }
      break;
    case 'top_movie':
      conditions.push("anime_type = 'Movie'");
      conditions.push("anime_status != 'Not Yet Aired'");
      orderBy = 'CAST(anime_rating AS REAL) DESC, anime_rating_user_count DESC';
      break;
    case 'top_currently_airing':
      conditions.push("anime_status = 'Currently Airing'");
      orderBy = 'CAST(anime_rating AS REAL) DESC, anime_rating_user_count DESC';
      break;
    case 'top_upcoming':
      conditions.push("anime_status = 'Not Yet Aired'");
      orderBy = 'anime_rating_user_count DESC, COALESCE(mal_score, CAST(anime_rating AS REAL)) DESC';
      break;
    case 'top_anime_mal':
    case 'top_movie_mal':
    case 'top_currently_airing_mal':
    case 'top_tv_mal':
      orderBy = 'COALESCE(mal_score, 0) DESC, anime_rating_user_count DESC';
      conditions.push('mal_score IS NOT NULL AND mal_score > 0');
      if (listType === 'top_currently_airing_mal') {
        conditions.push("anime_status = 'Currently Airing'");
      } else {
        conditions.push("anime_status != 'Not Yet Aired'");
      }
      if (listType === 'top_movie_mal') { conditions.push("anime_type = 'Movie'"); }
      if (listType === 'top_tv_mal') { conditions.push("anime_type = 'TV'"); }
      break;
    case 'latest_updated_episode_new': {
      const today = new Date().getDay(); // 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
      orderBy = `
        CASE
          WHEN animes.anime_release_day IS NULL OR animes.anime_release_day = '' THEN 999
          WHEN animes.anime_release_day = 'Sunday' THEN (${today} - 0 + 7) % 7
          WHEN animes.anime_release_day = 'Monday' THEN (${today} - 1 + 7) % 7
          WHEN animes.anime_release_day = 'Tuesday' THEN (${today} - 2 + 7) % 7
          WHEN animes.anime_release_day = 'Wednesday' THEN (${today} - 3 + 7) % 7
          WHEN animes.anime_release_day = 'Thursday' THEN (${today} - 4 + 7) % 7
          WHEN animes.anime_release_day = 'Friday' THEN (${today} - 5 + 7) % 7
          WHEN animes.anime_release_day = 'Saturday' THEN (${today} - 6 + 7) % 7
          ELSE 999
        END ASC,
        COALESCE(mal_score, CAST(anime_rating AS REAL)) DESC
      `;
      conditions.push("anime_type NOT IN ('Movie', 'OVA', 'ONA')");
      conditions.push("(SELECT COUNT(*) FROM episodes WHERE episodes.anime_id = animes.anime_id) > 0");
      break;
    }
    case 'last_added_tv':
      conditions.push("anime_type = 'TV'");
      orderBy = 'anime_updated_at DESC';
      break;
    default:
      orderBy = 'COALESCE(mal_score, CAST(anime_rating AS REAL)) DESC, anime_rating_user_count DESC';
  }

  if (extraParams.anime_type) {
    conditions.push(`${tbl}anime_type = ?`); params.push(extraParams.anime_type);
  }
  if (extraParams.anime_status) {
    conditions.push(`${tbl}anime_status = ?`); params.push(extraParams.anime_status);
  }
  if (extraParams.anime_season) {
    conditions.push(`${tbl}anime_season = ?`); params.push(extraParams.anime_season);
  }
  if (extraParams.anime_release_years) {
    conditions.push(`${tbl}anime_release_year = ?`); params.push(extraParams.anime_release_years[0]);
  }
  if (extraParams.anime_genre_ids) {
    conditions.push(`${tbl}anime_id IN (SELECT anime_id FROM anime_genres WHERE genre_id = ?)`);
    params.push(extraParams.anime_genre_ids[0]);
  }
  if (extraParams.anime_studio_ids) {
    conditions.push(`${tbl}anime_id IN (SELECT anime_id FROM anime_studios WHERE studio_id = ?)`);
    params.push(extraParams.anime_studio_ids[0]);
  }

  const fromClause = joinClause ? `animes a ${joinClause}` : 'animes';
  const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';
  const selectCols = joinClause ? 'a.*' : '*';

  const countRow = db.prepare(`SELECT COUNT(*) as total FROM ${fromClause} ${where}`).get(...params);
  const total = (countRow as any)?.total || 0;

  let rows = db.prepare(`SELECT ${selectCols} FROM ${fromClause} ${where} ORDER BY ${orderBy} LIMIT ? OFFSET ?`).all(...params, limit, offset);

  // Attach comma-separated genres from junction table
  if (rows.length > 0) {
    const ids = (rows as any[]).map(r => r.anime_id);
    const placeholders = ids.map(() => '?').join(',');
    const genreRows = db.prepare(`SELECT anime_id, genre_name FROM anime_genres WHERE anime_id IN (${placeholders})`).all(...ids) as any[];
    const genreMap: Record<number, string[]> = {};
    for (const gr of genreRows) {
      if (!genreMap[gr.anime_id]) genreMap[gr.anime_id] = [];
      genreMap[gr.anime_id].push(gr.genre_name);
    }
    for (const row of rows as any[]) {
      const g = genreMap[row.anime_id];
      if (g) row.anime_genres = g.join('،');
    }
  }

  // Enrich posters via Jikan
  rows = await enrichMalImages(rows);

  // Attach latest episode info for 'latest_updated_episode_new'
  if (listType === 'latest_updated_episode_new' && rows.length > 0) {
    const animeIds = (rows as any[]).map(r => r.anime_id);
    const placeholders = animeIds.map(() => '?').join(',');
    const latestEps = db.prepare(
      `SELECT e.anime_id, e.episode_id, e.episode_name, e.episode_number FROM episodes e
       INNER JOIN (SELECT anime_id, MAX(episode_id) as m FROM episodes WHERE anime_id IN (${placeholders}) GROUP BY anime_id) em
       ON e.anime_id = em.anime_id AND e.episode_id = em.m`
    ).all(...animeIds);
    const epMap: Record<number, any> = {};
    for (const ep of latestEps as any[]) epMap[ep.anime_id] = ep;
    for (const row of rows as any[]) {
      const ep = epMap[row.anime_id];
      if (ep) {
        row.latest_episode_name = ep.episode_name;
        row.latest_episode_id = ep.episode_id;
        row.latest_episode_number = ep.episode_number;
      }
    }
  }

  return { data: await augmentWithEnglishTitles(rows), total };
}

// ── Search ──────────────────────────────────────────────────────────────────
export async function searchAnime(query: string, limit: number = 24, offset: number = 0, filters: any = {}) {
  const db = getDb();
  let conditions: string[] = [];
  let params: any[] = [];

  if (query) {
    conditions.push('(anime_name LIKE ? OR anime_english_title LIKE ?)');
    const like = `%${query}%`;
    params.push(like, like);
  }
  if (filters.anime_type) {
    conditions.push('anime_type = ?'); params.push(filters.anime_type);
  }
  if (filters.anime_status) {
    conditions.push('anime_status = ?'); params.push(filters.anime_status);
  }
  if (filters.anime_season) {
    conditions.push('anime_season = ?'); params.push(filters.anime_season);
  }
  if (filters.anime_genre_ids) {
    conditions.push(`anime_id IN (SELECT anime_id FROM anime_genres WHERE genre_id = ?)`);
    params.push(filters.anime_genre_ids[0]);
  }

  const where = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';
  const countRow = db.prepare(`SELECT COUNT(*) as total FROM animes ${where}`).get(...params);
  const total = countRow?.total || 0;

  let rows = db.prepare(`SELECT * FROM animes ${where} ORDER BY anime_name ASC LIMIT ? OFFSET ?`).all(...params, limit, offset);

  if (query) {
    // Sort by relevance using the search score algorithm
    rows = rankSearchResults(rows, query);
  }

  return { data: await enrichMalImages(await augmentWithEnglishTitles(rows)), total };
}

export function getSlug(id: number): string | null {
  const db = getDb();
  const row = db.prepare('SELECT anime_slug FROM animes WHERE anime_id = ?').get(id) as any;
  return row?.anime_slug || null;
}

export async function resolveSlug(slug: string): Promise<number | null> {
  const db = getDb();
  // Try exact slug match first
  let row = db.prepare('SELECT anime_id FROM animes WHERE anime_slug = ?').get(slug) as any;
  if (row) return row.anime_id;
  // Fallback: try parsing as numeric ID
  const num = parseInt(slug);
  if (!isNaN(num)) {
    row = db.prepare('SELECT anime_id FROM animes WHERE anime_id = ?').get(num) as any;
    if (row) return row.anime_id;
  }
  // Try LIKE match
  row = db.prepare('SELECT anime_id FROM animes WHERE anime_slug LIKE ? LIMIT 1').get(`${slug}%`) as any;
  if (row) return row.anime_id;
  return null;
}

export async function toSlug(name: string, englishTitle?: string, id?: number): Promise<string> {
  const src = englishTitle || name || '';
  let slug = src.toLowerCase().replace(/[^a-z0-9\u0600-\u06ff\s-]/g, '').replace(/[\s_]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
  if (!slug) slug = `anime-${id || 0}`;
  return slug;
}

// ── Anime details ───────────────────────────────────────────────────────────
export async function getAnimeDetails(idOrSlug: number | string) {
  const db = getDb();
  let animeId = Number(idOrSlug);
  if (isNaN(animeId) || String(idOrSlug) !== String(animeId)) {
    const resolved = await resolveSlug(String(idOrSlug));
    if (!resolved) return null;
    animeId = resolved;
  }
  const anime = db.prepare('SELECT * FROM animes WHERE anime_id = ?').get(animeId);
  if (!anime) return null;

  const episodes = db.prepare('SELECT * FROM episodes WHERE anime_id = ? ORDER BY episode_number ASC').all(Number(animeId));

  // Batch fetch episode servers in a single query
  const epIds = episodes.map((ep: any) => ep.episode_id);
  const serverMap: Record<number, any[]> = {};
  if (epIds.length > 0) {
    const placeholders = epIds.map(() => '?').join(',');
    const allServers = db.prepare(`SELECT * FROM episode_servers WHERE episode_id IN (${placeholders})`).all(...epIds);
    for (const srv of allServers as any[]) {
      if (!serverMap[srv.episode_id]) serverMap[srv.episode_id] = [];
      serverMap[srv.episode_id].push(srv);
    }
  }
  const epWithSrv = episodes.map((ep: any) => ({
    ...ep,
    episode_urls: serverMap[ep.episode_id] || [],
  }));

  // Get genres
  const genres = db.prepare('SELECT * FROM anime_genres WHERE anime_id = ?').all(Number(animeId));
  const genreIds = genres.map((g: any) => g.genre_id).join(',');
  const genreNames = genres.map((g: any) => g.genre_name).join(',');

  // Get recommendations with poster images
  const recs = db.prepare(`
    SELECT r.*, a.mal_image, a.mal_id, a.anime_cover_image_full_url
    FROM recommendations r
    LEFT JOIN animes a ON a.anime_id = r.recommended_anime_id
    WHERE r.anime_id = ?
  `).all(Number(animeId));

  // Lightweight remote fetch bypassed for fully offline load
  let moreInfo: any = null;
  let relatedAnimes: any[] = [];

  const enriched = await enrichMalImages([anime as any]);
  const enrichedAnime = enriched[0] || anime;

  // Enrich recommendation posters
  const recAnimes = recs.map((r: any) => ({
    anime_id: r.recommended_anime_id,
    mal_id: r.mal_id,
    mal_image: r.mal_image,
  })).filter((r: any) => !r.mal_image && r.mal_id);
  if (recAnimes.length > 0) {
    const enrichedRecs = await enrichMalImages(recAnimes);
    for (const er of enrichedRecs) {
      if (er.mal_image) {
        const match = recs.find((r: any) => r.recommended_anime_id === er.anime_id);
        if (match) match.mal_image = er.mal_image;
      }
    }
  }

  // Enrich related anime / suggestions posters from DB
  if (relatedAnimes.length > 0) {
    const ids = relatedAnimes.map((s: any) => s.anime_id).filter(Boolean);
    if (ids.length > 0) {
      const placeholders = ids.map(() => '?').join(',');
      const posterRows = db.prepare(`SELECT anime_id, mal_image, mal_id FROM animes WHERE anime_id IN (${placeholders})`).all(...ids) as any[];
      const posterMap: Record<number, any> = {};
      for (const pr of posterRows) posterMap[pr.anime_id] = pr;
      for (const s of relatedAnimes as any[]) {
        const p = posterMap[s.anime_id];
        if (p) {
          s.mal_image = p.mal_image;
          s.mal_id = p.mal_id;
        }
      }
    }
    // Enrich any that still lack mal_image
    const enrichedSuggestions = await enrichMalImages(relatedAnimes);
    for (let i = 0; i < relatedAnimes.length; i++) {
      if (enrichedSuggestions[i]?.mal_image) relatedAnimes[i].mal_image = enrichedSuggestions[i].mal_image;
    }
  }

  return {
    ...enrichedAnime,
    episodes: epWithSrv,
    anime_genre_ids: genreIds,
    anime_genres: genreNames,
    related_recommendations: { data: recs },
    related_animes: { data: relatedAnimes },
    more_info_result: moreInfo,
  };
}

// ── Filters (dropdowns) ─────────────────────────────────────────────────────
export async function getFilters() {
  const db = getDb();
  const genres = db.prepare('SELECT * FROM dropdowns WHERE type = ? ORDER BY label ASC').all('anime_genres');
  const studios = db.prepare('SELECT * FROM dropdowns WHERE type = ? ORDER BY label ASC').all('anime_studio_ids');
  const years = db.prepare('SELECT * FROM dropdowns WHERE type = ? ORDER BY label ASC').all('anime_release_years');

  return {
    anime_genres: { data: genres.map((g: any) => ({ value: g.id, option: g.label })) },
    anime_studio_ids: { data: studios.map((s: any) => ({ value: s.id, option: s.label })) },
    anime_release_years: { data: years.map((y: any) => ({ value: y.id, option: y.label })) },
  };
}

// ── Schedule ────────────────────────────────────────────────────────────────
export async function getSchedule() {
  const db = getDb();
  const days = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
  const schedule: any = {};
  
  for (const day of days) {
    const animes = db.prepare(`
      SELECT a.*,
        (SELECT episode_number FROM episodes WHERE anime_id = a.anime_id ORDER BY episode_number DESC LIMIT 1) as latest_episode_number,
        (SELECT episode_name FROM episodes WHERE anime_id = a.anime_id ORDER BY episode_number DESC LIMIT 1) as latest_episode_name,
        (SELECT GROUP_CONCAT(genre_name, ',') FROM anime_genres WHERE anime_id = a.anime_id) as anime_genres,
        (SELECT COUNT(*) FROM episodes WHERE anime_id = a.anime_id) as anime_episode_count
      FROM animes a
      WHERE a.anime_release_day = ?
        AND (a.anime_status = 'Currently Airing' OR a.anime_status = 'Not Yet Aired')
      ORDER BY a.anime_name ASC
    `).all(day) as any[];
    
    schedule[day] = animes;
  }
  
  // Catch-all: currently airing anime without a release day
  const unassigned = db.prepare(`
    SELECT a.*,
      (SELECT episode_number FROM episodes WHERE anime_id = a.anime_id ORDER BY episode_number DESC LIMIT 1) as latest_episode_number,
      (SELECT episode_name FROM episodes WHERE anime_id = a.anime_id ORDER BY episode_number DESC LIMIT 1) as latest_episode_name,
      (SELECT GROUP_CONCAT(genre_name, ',') FROM anime_genres WHERE anime_id = a.anime_id) as anime_genres,
      (SELECT COUNT(*) FROM episodes WHERE anime_id = a.anime_id) as anime_episode_count
    FROM animes a
    WHERE (a.anime_release_day IS NULL OR a.anime_release_day = '')
      AND a.anime_status = 'Currently Airing'
    ORDER BY a.anime_name ASC
  `).all() as any[];
  
  schedule['Unspecified'] = unassigned;

  // Enrich posters via Jikan for all days
  await Promise.all(
    Object.keys(schedule).map(async (day) => {
      schedule[day] = await enrichMalImages(schedule[day]);
    })
  );

  return schedule;
}

// ── Seasons ─────────────────────────────────────────────────────────────────
export function getSeasonsFromDb() {
  const db = getDb();
  return db.prepare(
    "SELECT DISTINCT anime_season, anime_release_year FROM animes WHERE anime_season IS NOT NULL AND anime_season != '' AND anime_release_year IS NOT NULL AND anime_release_year != '' ORDER BY anime_release_year DESC, anime_season DESC"
  ).all() as { anime_season: string; anime_release_year: string }[];
}

// ── Episode Details by Number ──────────────────────────────────────────────
export function getEpisodeDetails(animeId: number | string, episodeNumber: number | string) {
  const db = getDb();
  return db.prepare('SELECT * FROM episodes WHERE anime_id = ? AND episode_number = ?').get(Number(animeId), Number(episodeNumber)) as any;
}

// ── Episode servers (muilt expansion + backup decryption) ──────────────────
export async function getEpisodeServers(animeId: number | string, episodeId: number | string) {
  const db = getDb();
  const rows = db.prepare('SELECT * FROM episode_servers WHERE episode_id = ?').all(Number(episodeId));

  const results: any[] = [];

  for (const srv of rows) {
    const name = (srv.episode_server_name || '').trim();
    const serverId = String(srv.episode_url_id || srv.id);
    const url = srv.episode_url || '';

    if (!url) continue;

    // Anime3RB — resolve page URL to direct mp4s (SSR)
    if (name.startsWith('Anime3RB') || name.startsWith('anime3rb') || url.includes('anime3rb.com')) {
      if (url.includes('files-') || url.includes('/files/')) {
        const quality = name.replace(/^Anime3RB\s*/i, '').trim();
        results.push({ id: serverId, label: name, name: 'Anime3RB', url, quality });
        continue;
      }
      const sources = await resolveAnime3rbEpisode(url);
      for (const src of sources) {
        results.push({
          id: `${serverId}_${src.label}`,
          label: `Anime3RB ${src.label}`,
          name: 'Anime3RB',
          url: src.url,
          quality: src.label.replace(/[^\dp]/g, '') || src.label,
        });
      }
      continue;
    }

    // Regular servers (wit-embed)
    const parts = name.split(' - ');
    results.push({
      id: serverId,
      label: name || 'Server',
      name: parts[0] || 'Server',
      url,
      quality: parts[1] || '',
    });
  }

  return results;
}

// ── Characters (still remote) ──────────────────────────────────────────────
export async function getAnimeCharacters(id: number | string) {
  const res = await rawApi(`animes/get-anime-characters?json=${encodeURIComponent(JSON.stringify({ anime_id: Number(id), type: 'all' }))}`);
  if (!res) return null;
  const main = res.main || [];
  const supporting = res.supporting || [];
  const chars = [
    ...main.map((c: any) => ({ character_id: c.character_id, character_name: c.character_name, character_image_url: c.character_image_url, role: 'Main' })),
    ...supporting.map((c: any) => ({ character_id: c.character_id, character_name: c.character_name, character_image_url: c.character_image_url, role: 'Supporting' })),
  ];
  return { anime_characters: chars };
}

// ── Stats (still remote) ────────────────────────────────────────────────────
export async function getAnimeStats(id: number | string) {
  const res = await rawApi(`animes/get-anime-stats?anime_id=${id}`);
  return res?.response || null;
}

// ── Internal helpers ────────────────────────────────────────────────
function toPlayerUrl(urlOrResult: string | { url: string; cookies?: string; mfPage?: string; directUrl?: string }): string {
  if (typeof urlOrResult === 'object' && urlOrResult !== null) {
    const r = urlOrResult as { url: string; cookies?: string; mfPage?: string; directUrl?: string };
    if (r.mfPage) {
      return `/api/stream?mfPage=${encodeURIComponent(r.mfPage)}`;
    }
    if (r.cookies) {
      return `/api/stream?url=${encodeURIComponent(r.url)}&cookies=${encodeURIComponent(r.cookies)}`;
    }
    urlOrResult = r.url;
  }
  const url = urlOrResult as string;
  if (url.startsWith('/api/stream')) return url;
  try {
    const host = new URL(url).hostname.toLowerCase();
    // MediaFire page URLs → always proxy via mfPage for on-demand extraction
    if (host.includes('mediafire.com')) {
      return `/api/stream?mfPage=${encodeURIComponent(url)}`;
    }
    // Direct .mp4/.webm/.m3u8 from any domain → proxy
    if (/\.(mp4|webm|m3u8)([\/?]|$)/i.test(url)) {
      return `/api/stream?url=${encodeURIComponent(url)}`;
    }
    // Known CDN hosts → proxy
    const cdnHosts = ['tapecontent', 'ab-hunter', 'vinovo', 'doodstream', 'doodcdn', 'vidmoly', 'mp4upload.com'];
    if (cdnHosts.some(h => host.includes(h))) {
      return `/api/stream?url=${encodeURIComponent(url)}`;
    }
  } catch {}
  return url;
}

// ── Extraction cache ──
const extractionCache = new Map<string, { result: any; ts: number }>();
const CACHE_TTL = 10 * 60 * 1000; // 10 minutes

async function resolveDirectLink(url: string) {
  const cached = extractionCache.get(url);
  if (cached && Date.now() - cached.ts < CACHE_TTL) return cached.result;

  const result = await Promise.race([
    resolveStreamUrl(url),
    new Promise<null>(resolve => setTimeout(() => resolve(null), 12000)),
  ]);
  if (result === null) return url; // timeout → fallback to iframe
  const processed = processExtractionResult(url, result);
  extractionCache.set(url, { result: processed, ts: Date.now() });
  return processed;
}

function processExtractionResult(originalUrl: string, result: any) {
  if (typeof result === 'object' && result !== null) {
    const r = result as { url: string; cookies?: string };
    if (r.cookies) return { mfPage: originalUrl };
    return `/api/stream?url=${encodeURIComponent(r.url)}`;
  }
  // Extraction returned a different URL — only proxy if it looks playable
  if (result && result !== originalUrl && !result.startsWith('/api/stream')) {
    try {
      const host = new URL(result).hostname.toLowerCase();
      const isPlayable =
        /\.(mp4|webm|m3u8)([\/?]|$)/i.test(result) ||
        ['tapecontent', 'ab-hunter', 'vinovo', 'doodstream', 'doodcdn', 'vidmoly', 'mp4upload.com', 'cdn.'].some(h => host.includes(h)) ||
        result.includes('/get_video');
      if (isPlayable) return `/api/stream?url=${encodeURIComponent(result)}`;
    } catch {
      return result;
    }
  }
  return result;
}

async function getMultiServerLinks(url: string) {
  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': CHROME_UA },
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return [];
    return await res.json();
  } catch {
    // fallback to anslayer
    try {
      const res2 = await fetch(`https://anslayer.com${new URL(url).pathname}${new URL(url).search}`, {
        headers: { 'User-Agent': CHROME_UA },
        signal: AbortSignal.timeout(5000),
      });
      if (!res2.ok) return [];
      return await res2.json();
    } catch { return []; }
  }
}

const BACKUP_CERT_SHA1 = '44D8B79265DDBB9C887320F64521A76D72F6D7D4';
const BACKUP_RNCRYPTOR_PASSWORD = 'android-app9>E>VBa=X%;[5BX~=Q~K';

async function getBackupQualityServers(record: any) {
  try {
    const sourceUrl = new URL(record.episode_url);
    const googleRes = await fetchWithTimeout(`${ANSLAYER_BASE}google.php`, 5000);
    if (!googleRes.ok) return [];
    const googleValue = (await googleRes.text()).trim();
    const inf = createBackupInf(googleValue);
    const endpoint = new URL(sourceUrl);
    endpoint.pathname = endpoint.pathname.replace(/\/vq\.php$/i, '/v-qs.php');
    const response = await fetchWithTimeout(endpoint.toString(), 7000, {
      method: 'POST',
      body: new URLSearchParams({ f: sourceUrl.searchParams.get('f') || '', e: sourceUrl.searchParams.get('e') || '', inf }),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': CHROME_UA },
    });
    if (!response.ok) return [];
    const links = JSON.parse(decryptRNCryptor(await response.text(), BACKUP_RNCRYPTOR_PASSWORD));
    if (!Array.isArray(links)) return [];
    return links.flatMap((item: any, index: number) => {
      if (!item?.file || typeof item.file !== 'string') return [];
      const quality = getBackupQuality(item.file);
      return [{ id: `${record.episode_url_id}_backup_${index}`, label: `BACKUP ${quality.label}`, name: `back_up_server - ${quality.name}`, url: toPlayerUrl(item.file), order: quality.order, quality: quality.label }];
    }).sort((a: any, b: any) => a.order - b.order).map(({ order: _order, ...server }: any) => server);
  } catch { return []; }
}

function createBackupInf(googleValue: string) {
  const { createCipheriv } = require('node:crypto');
  const payload = JSON.stringify({ uhy: 'com.anslayer', dma: 47, mvd: '1.5.10', vko: BACKUP_CERT_SHA1 });
  const key = `${googleValue.slice(0, 10)}${BACKUP_CERT_SHA1.slice(0, 22)}`.slice(0, 16);
  const cipher = createCipheriv('aes-128-ecb', Buffer.from(key), null);
  return JSON.stringify({ a: Buffer.concat([cipher.update(payload), cipher.final()]).toString('base64'), b: googleValue });
}

function decryptRNCryptor(encrypted: string, password: string) {
  const { createDecipheriv, createHmac, pbkdf2Sync, timingSafeEqual } = require('node:crypto');
  const data = Buffer.from(encrypted.trim(), 'base64');
  if (data.length < 66 || data[0] !== 3 || data[1] !== 1) throw new Error('Invalid');
  const encryptedData = data.subarray(0, -32);
  const authCode = data.subarray(-32);
  const encKey = pbkdf2Sync(password, data.subarray(2, 10), 10000, 32, 'sha1');
  const hmacKey = pbkdf2Sync(password, data.subarray(10, 18), 10000, 32, 'sha1');
  const expected = createHmac('sha256', hmacKey).update(encryptedData).digest();
  if (!timingSafeEqual(authCode, expected)) throw new Error('Invalid');
  const decipher = createDecipheriv('aes-256-cbc', encKey, data.subarray(18, 34));
  return Buffer.concat([decipher.update(data.subarray(34, -32)), decipher.final()]).toString();
}

function getBackupQuality(url: string) {
  const filename = new URL(url).pathname.split('/').pop()?.toLowerCase();
  if (filename?.startsWith('hh.mp4')) return { name: '1080p', label: '1080p', order: 3 };
  if (filename?.startsWith('h.mp4')) return { name: '720p', label: '720p', order: 2 };
  if (filename?.startsWith('s.mp4')) return { name: '480p', label: '480p', order: 1 };
  if (filename?.startsWith('m.mp4')) return { name: '360p', label: '360p', order: 0 };
  return { name: 'unknown', label: 'UNKNOWN', order: 4 };
}

async function fetchWithTimeout(url: string, timeout: number, options: RequestInit = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    return await fetch(url, { ...options, signal: controller.signal, headers: { 'User-Agent': CHROME_UA, ...(options.headers || {}) } });
  } finally { clearTimeout(timer); }
}

// ── Search helpers ──────────────────────────────────────────────────────────
function normalizeTitle(value: string) {
  return value.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9\u0600-\u06ff]+/g, ' ').trim();
}

function searchScore(title: string, query: string) {
  const normalizedTitle = normalizeTitle(title);
  const normalizedQuery = normalizeTitle(query);
  const words = normalizedTitle.split(' ');
  const queryWords = normalizedQuery.split(' ').filter(Boolean);
  if (normalizedTitle === normalizedQuery) return 0;
  if (normalizedTitle.startsWith(`${normalizedQuery} `)) return 1;
  if (words.includes(normalizedQuery)) return 2;
  if (normalizedTitle.includes(normalizedQuery)) return 3;
  if (queryWords.every(word => normalizedTitle.includes(word))) return 4;
  return 5;
}

function rankSearchResults(anime: any[], query: string) {
  return anime.map((item, index) => ({ item, index, score: searchScore(item.anime_name || '', query) }))
    .sort((a, b) => a.score - b.score || a.index - b.index)
    .map(({ item }) => item);
}
