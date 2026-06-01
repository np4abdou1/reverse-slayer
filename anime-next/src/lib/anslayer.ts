import { ANSLAYER_BASE, CLIENT_ID, CLIENT_SECRET, CHROME_UA, SERVER_MAP } from './constants';
import { createCipheriv, createDecipheriv, createHmac, pbkdf2Sync, timingSafeEqual } from 'node:crypto';

const cache = new Map<string, { data: any, timestamp: number }>();
const CACHE_TTL = 1000 * 60 * 5; // 5 minutes

const FETCH_TIMEOUT = 10000;

async function acurl(path: string, options: RequestInit = {}) {
  const cacheKey = `${path}_${options.body || ''}`;
  if (options.method !== 'POST' && cache.has(cacheKey)) {
    const cached = cache.get(cacheKey)!;
    if (Date.now() - cached.timestamp < CACHE_TTL) {
      return cached.data;
    }
  }

  const url = path.startsWith('http') ? path : `${ANSLAYER_BASE}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT);
  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        'Client-Id': CLIENT_ID,
        'Client-Secret': CLIENT_SECRET,
        'Accept': 'application/json',
        'User-Agent': CHROME_UA,
        ...options.headers,
      },
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const text = await response.text();
    let result;
    try {
      result = JSON.parse(text);
    } catch {
      result = text;
    }

    if (options.method !== 'POST') {
      cache.set(cacheKey, { data: result, timestamp: Date.now() });
    }
    return result;
  } finally {
    clearTimeout(timer);
  }
}

export async function searchAnime(query: string, type: string = 'anime_list', limit: number = 25, offset: number = 0) {
  let params: any = { list_type: type, limit, offset };
  if (query) {
    // The upstream filter returns matches in publish order. Fetch a wider set
    // and rank locally so exact title searches do not get buried by spin-offs.
    params = { list_type: 'filter', anime_name: query, limit: Math.max(limit, 100), offset };
  } else if (type === 'all') {
    params.list_type = 'anime_list';
  }

  const res = await acurl(`animes/get-published-animes?json=${encodeURIComponent(JSON.stringify(params))}`);
  const anime = res?.response?.data || [];
  return query ? rankSearchResults(anime, query).slice(0, limit) : anime;
}

function normalizeTitle(value: string) {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9\u0600-\u06ff]+/g, ' ')
    .trim();
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
  return anime
    .map((item, index) => ({ item, index, score: searchScore(item.anime_name || '', query) }))
    .sort((a, b) => a.score - b.score || a.index - b.index)
    .map(({ item }) => item);
}

export async function getAnimeDetails(id: number) {
  const res = await acurl(`anime/get-anime-details?anime_id=${id}&fetch_episodes=Yes&more_info=Yes`);
  return res?.response || null;
}

export async function getEpisodeServers(animeId: number, episodeId: number) {
  const params = { anime_id: animeId, episode_ids: [episodeId], limit: 1 };
  const res = await acurl(`episodes/get-episodes-new`, {
    method: 'POST',
    body: `json=${encodeURIComponent(JSON.stringify(params))}`,
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });

  const responseEpisodes = res?.response?.data || [];
  const requestedEpisode = responseEpisodes.find((episode: any) => Number(episode.episode_id) === episodeId);
  let rawUrls = requestedEpisode?.episode_urls || [];
  
  // Sometime the above fails or returns nothing, fallback to old endpoint
  if (!rawUrls.length) {
    const p2 = { anime_id: animeId, limit: 200 };
    const r2 = await acurl(`episodes/get-episodes?json=${encodeURIComponent(JSON.stringify(p2))}`);
    const eps = r2?.response?.data || [];
    const target = eps.find((e: any) => Number(e.episode_id) === episodeId);
    rawUrls = target?.episode_urls || [];
  }

  const backupRecord = rawUrls.find((u: any) => u.episode_url.includes('v-qs.php') || u.episode_url.includes('vq.php'));
  const filtered = rawUrls.filter((u: any) => u !== backupRecord);
  
  const unrolled: any[] = [];
  for (const srv of filtered) {
    if (srv.episode_server_name === 'muilt') {
      const links = await getMultiServerLinks(srv.episode_url);
      if (Array.isArray(links)) {
        links.forEach((link, idx) => {
          let matched = false;
          for (const [key, val] of Object.entries(SERVER_MAP)) {
            if (link.includes(key)) {
              const quality = key === 'mediafire' ? getMediafireQuality(link) : '';
              unrolled.push({
                id: `${srv.episode_url_id}_${idx}`,
                label: val.label,
                name: `${val.name}${quality}`,
                url: link
              });
              matched = true;
              break;
            }
          }
          if (!matched) {
             try {
               const host = new URL(link).hostname.replace('www.', '');
               unrolled.push({ id: `${srv.episode_url_id}_${idx}`, label: 'LINK', name: host, url: link });
             } catch {
               unrolled.push({ id: `${srv.episode_url_id}_${idx}`, label: 'LINK', name: 'direct', url: link });
             }
          }
        });
      }
    } else {
      let label = String(srv.episode_server_id);
      let name = srv.episode_server_name;
      for (const [key, val] of Object.entries(SERVER_MAP)) {
        if (srv.episode_url.includes(key) || srv.episode_server_name.toLowerCase() === key) {
          label = val.label;
          name = val.name;
          break;
        }
      }
      unrolled.push({ id: srv.episode_url_id, label, name, url: srv.episode_url });
    }
  }

  // Resolve direct links in parallel with individual timeouts
  const finalized: any[] = (await Promise.all(
    unrolled.map(async (srv) => {
      try {
        srv.url = await resolveDirectLink(srv.url);
        if (srv.url) srv.url = toPlayerUrl(srv.url);
      } catch {
        srv.url = '';
      }
      return srv;
    })
  )).filter(server => server.url);

  if (backupRecord) {
    const backupServers = await getBackupQualityServers(backupRecord);
    if (backupServers.length) {
      finalized.push(...backupServers);
    } else {
      const fallback = finalized.find(server => server.name === 'MF - 720p')
        || finalized.find(server => server.name.startsWith('MF'));
      if (!fallback) return finalized.sort((a, b) => serverPriority(a.name) - serverPriority(b.name));
      finalized.push({
        id: backupRecord.episode_url_id,
        label: 'BACKUP',
        name: 'back_up_server',
        url: fallback.url,
      });
    }
  }

  return finalized.sort((a, b) => serverPriority(a.name) - serverPriority(b.name));
}

async function getMultiServerLinks(url: string) {
  const candidates = [url];
  try {
    const parsed = new URL(url);
    if (parsed.hostname !== 'anslayer.com') {
      candidates.push(`https://anslayer.com${parsed.pathname}${parsed.search}`);
    }
  } catch {
    // acurl below reports malformed upstream URLs.
  }

  const responses = await Promise.allSettled(candidates.map(candidate => acurl(candidate)));
  return [...new Set(
    responses.flatMap(result => result.status === 'fulfilled' && Array.isArray(result.value) ? result.value : [])
  )];
}

function serverPriority(name: string) {
  if (name === 'GDS') return 0;
  if (name === 'MF - 1080p') return 1;
  if (name.startsWith('MF')) return 2;
  if (name === 'ST') return 3;
  if (name === 'VNO') return 4;
  if (name.startsWith('back_up_server')) return 5;
  return 10;
}

function toPlayerUrl(url: string) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    if (
      host === 'mediafire.com'
      || host.endsWith('.mediafire.com')
      || host === 'streamtape.to'
      || host.endsWith('.streamtape.to')
      || host === 'tapecontent.net'
      || host.endsWith('.tapecontent.net')
      || host === 'ab-hunter.com'
      || host.endsWith('.ab-hunter.com')
    ) {
      return `/api/stream?url=${encodeURIComponent(url)}`;
    }
  } catch {
    // Leave relative or malformed URLs untouched for the iframe fallback.
  }
  return url;
}

const BACKUP_CERT_SHA1 = '44D8B79265DDBB9C887320F64521A76D72F6D7D4';
const BACKUP_RNCRYPTOR_PASSWORD = 'android-app9>E>VBa=X%;[5BX~=Q~K';

async function getBackupQualityServers(record: any) {
  try {
    const sourceUrl = new URL(record.episode_url);
    const googleResponse = await fetchWithTimeout(`${ANSLAYER_BASE}google.php`, 5000);
    if (!googleResponse.ok) return [];
    const googleValue = (await googleResponse.text()).trim();
    const inf = createBackupInf(googleValue);
    const endpoint = new URL(sourceUrl);
    endpoint.pathname = endpoint.pathname.replace(/\/vq\.php$/i, '/v-qs.php');
    const response = await fetchWithTimeout(endpoint.toString(), 7000, {
      method: 'POST',
      body: new URLSearchParams({
        f: sourceUrl.searchParams.get('f') || '',
        e: sourceUrl.searchParams.get('e') || '',
        inf,
      }),
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': CHROME_UA,
      },
    });
    if (!response.ok) return [];

    const links = JSON.parse(decryptRNCryptor(await response.text(), BACKUP_RNCRYPTOR_PASSWORD));
    if (!Array.isArray(links)) return [];
    return links.flatMap((item: any, index: number) => {
      if (!item?.file || typeof item.file !== 'string') return [];
      const quality = getBackupQuality(item.file);
      return [{
        id: `${record.episode_url_id}_backup_${index}`,
        label: `BACKUP ${quality.label}`,
        name: `back_up_server - ${quality.name}`,
        url: toPlayerUrl(item.file),
        order: quality.order,
      }];
    }).sort((a, b) => a.order - b.order).map(({ order: _order, ...server }) => server);
  } catch (error) {
    console.error('Backup CDN resolution failed', error);
    return [];
  }
}

function createBackupInf(googleValue: string) {
  const payload = JSON.stringify({
    uhy: 'com.anslayer',
    dma: 47,
    mvd: '1.5.10',
    vko: BACKUP_CERT_SHA1,
  });
  const key = `${googleValue.slice(0, 10)}${BACKUP_CERT_SHA1.slice(0, 22)}`.slice(0, 16);
  const cipher = createCipheriv('aes-128-ecb', Buffer.from(key), null);
  return JSON.stringify({
    a: Buffer.concat([cipher.update(payload), cipher.final()]).toString('base64'),
    b: googleValue,
  });
}

function decryptRNCryptor(encrypted: string, password: string) {
  const data = Buffer.from(encrypted.trim(), 'base64');
  if (data.length < 66 || data[0] !== 3 || data[1] !== 1) throw new Error('Invalid RNCryptor payload');

  const encryptedData = data.subarray(0, -32);
  const authenticationCode = data.subarray(-32);
  const encryptionKey = pbkdf2Sync(password, data.subarray(2, 10), 10000, 32, 'sha1');
  const hmacKey = pbkdf2Sync(password, data.subarray(10, 18), 10000, 32, 'sha1');
  const expectedCode = createHmac('sha256', hmacKey).update(encryptedData).digest();
  if (!timingSafeEqual(authenticationCode, expectedCode)) throw new Error('Invalid RNCryptor HMAC');

  const decipher = createDecipheriv('aes-256-cbc', encryptionKey, data.subarray(18, 34));
  return Buffer.concat([decipher.update(data.subarray(34, -32)), decipher.final()]).toString();
}

function getBackupQuality(url: string) {
  const filename = new URL(url).pathname.split('/').pop()?.toLowerCase();
  if (filename === 'hh.mp4') return { name: 'very high', label: 'VERY HIGH', order: 3 };
  if (filename === 'h.mp4') return { name: 'high', label: 'HIGH', order: 2 };
  if (filename === 's.mp4') return { name: 'medium', label: 'MEDIUM', order: 1 };
  if (filename === 'm.mp4') return { name: 'low', label: 'LOW', order: 0 };
  return { name: 'unknown', label: 'UNKNOWN', order: 4 };
}

async function resolveDirectLink(url: string) {
  if (url.includes('ok.ru')) {
    const embedUrl = url.includes('videoembed') ? url : `https://ok.ru/videoembed/${url.split('/').pop()}`;
    return await isOkEmbedAvailable(embedUrl) ? embedUrl : '';
  }

  // The APK's BackupCdn presenter scrapes MediaFire pages for a temporary
  // download*.mediafire.com MP4 URL. MediaFire pages cannot be iframed.
  if (/(?:www\.)?mediafire\.com\/file/i.test(url)) {
    return resolveMediafireLink(url);
  }

  // These retired providers still exist in old episode records but no longer
  // expose a usable browser player. Do not present broken server buttons.
  if (isUnsupportedLegacyUrl(url) || /fembed\.com\/api\/source/i.test(url)) {
    return '';
  }

  // Already a direct media link (mp4, webm, m3u8) - return as-is.
  if (/\.(mp4|webm|m3u8)([\/?]|$)/i.test(url)) {
    return url;
  }

  // Try scraping embed/page URLs for a direct video link first.
  // If scraping fails, VideoPlayer will detect /e/ etc. and use an iframe fallback.
  // Goodstream and Lulustream HLS links require their embed context and return
  // 403 when loaded directly by the browser, so leave those as iframe URLs.
  const scrapable = ['streamtape', 'filemoon', 'mixdrop'];
  if (!scrapable.some(d => url.includes(d))) {
    return url;
  }

  try {
    const scrapeController = new AbortController();
    const scrapeTimer = setTimeout(() => scrapeController.abort(), 5000);
    let html: string;
    try {
      const response = await fetch(url, {
        signal: scrapeController.signal,
        headers: { 'User-Agent': CHROME_UA },
      });
      html = await response.text();
    } finally {
      clearTimeout(scrapeTimer);
    }
    let directUrl: string | null = null;

    if (url.includes('goodstream') || url.includes('lulustream')) {
      const m = html.match(/file:\s*"([^"]+)"/) ||
                html.match(/file:\s*'([^']+)'/) ||
                html.match(/sources:\s*\[\{\s*file:\s*"([^"]+)"/);
      if (m) directUrl = m[1];
    } else if (url.includes('streamtape')) {
      const m = html.match(/document\.getElementById\('norobotlink'\)\.innerHTML = (.*);/);
      if (m) {
        const tm = m[1].match(/token=([^&']+)/);
        const fm = html.match(/<div id="ideoooolink" style="display:none;">(.*)<\/div>/);
        if (tm && fm) {
           const host = new URL(url).host;
           const path = fm[1].split(host)[1];
           directUrl = `https://${host}${path}&token=${tm[1]}&dl=1`;
        }
      }
    } else if (url.includes('filemoon')) {
      const m = html.match(/file:\s*"([^"]+)"/) ||
                html.match(/<source\s+src="([^"]+)"/);
      if (m) directUrl = m[1];
    } else if (url.includes('mixdrop')) {
      const m = html.match(/location\s*=\s*"([^"]+)"/);
      if (m) directUrl = m[1];
    }

    if (directUrl) return directUrl;
  } catch (e) {
    console.error('Resolution failed for', url, e);
  }

  // Scraping failed. Return an embed-capable URL for the iframe fallback.
  if (url.includes('mixdrop')) return '';
  return normalizeEmbedUrl(url);
}

function getMediafireQuality(url: string) {
  if (url.match(/_(uhd|1080p|hh)(?:_1080p)?\.mp4/i)) return ' - 1080p';
  if (url.match(/_(h|720p)\.mp4/i)) return ' - 720p';
  if (url.match(/_(s|480p)\.mp4/i)) return ' - 480p';
  if (url.match(/_(m|360p)\.mp4/i)) return ' - 360p';
  return '';
}

async function resolveMediafireLink(url: string) {
  try {
    const response = await fetchWithTimeout(url, 5000);
    const html = await response.text();
    const match = html.match(/href\s*=\s*["'](https?:\/\/download\d+\.mediafire\.com[^"']+\.mp4[^"']*)/i);
    if (match) return decodeHtmlUrl(match[1]);
  } catch (error) {
    console.error('MediaFire resolution failed for', url, error);
  }
  return '';
}

async function isOkEmbedAvailable(url: string) {
  try {
    const response = await fetchWithTimeout(url, 5000);
    if (!response.ok) return false;
    const html = await response.text();
    return !html.includes('data-movie-id="null"') && !html.includes('vp_video_stub __na');
  } catch {
    return false;
  }
}

function isUnsupportedLegacyUrl(url: string) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return [
      'drive.google.com',
      'tune.pk',
      'vidlox.me',
      'uptostream.com',
      'jawcloud.co',
      'streamvid.net',
      'streamhub.ink',
      'highstream.tv',
    ].includes(host);
  } catch {
    return true;
  }
}

function normalizeEmbedUrl(url: string) {
  if (url.includes('streamtape')) {
    return url.replace(/\/v\//, '/e/');
  }
  return url;
}

function decodeHtmlUrl(url: string) {
  return url.replace(/&amp;/g, '&');
}

async function fetchWithTimeout(url: string, timeout: number, options: RequestInit = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: { 'User-Agent': CHROME_UA, ...options.headers },
    });
  } finally {
    clearTimeout(timer);
  }
}
