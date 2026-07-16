import { SocksProxyAgent } from 'socks-proxy-agent';
import { HttpsProxyAgent } from 'https-proxy-agent';
import https from 'https';
import http from 'http';

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36';
const WARP = 'http://127.0.0.1:40000';
const TOR = 'socks5://127.0.0.1:9050';

const warpAgent = new HttpsProxyAgent(WARP);
const torAgent = new SocksProxyAgent(TOR);

function httpGet(url: string, agent: any, timeout = 15000): Promise<{ body: string; status?: number; location?: string }> {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const mod = u.protocol === 'https:' ? https : http;
    const req = mod.get(url, { agent, timeout }, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => resolve({ body, status: res.statusCode, location: res.headers.location as string }));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

function extractPlayerUrl(html: string): string | null {
  const regex = /wire:snapshot=(["'])([^"']+?)\1/g;
  let m;
  while ((m = regex.exec(html)) !== null) {
    try {
      const decoded = m[2].replace(/&quot;/g, '"').replace(/&amp;/g, '&');
      const data = JSON.parse(decoded);
      if (data?.data?.video_url) return data.data.video_url;
    } catch {}
  }
  return null;
}

function extractVideoSources(html: string): any[] {
  const regex = /var video_sources = (\[.*?\]);/g;
  let m;
  while ((m = regex.exec(html)) !== null) {
    try {
      const sources = JSON.parse(m[1].replace(/\\\//g, '/'));
      if (Array.isArray(sources) && sources.some(s => s.src)) return sources;
    } catch {}
  }
  return [];
}

export interface Anime3rbSource {
  label: string;
  url: string;
}

export async function resolveAnime3rbEpisode(episodeUrl: string): Promise<Anime3rbSource[]> {
  try {
    // Step 1: Episode page via WARP → player URL
    const ep = await httpGet(episodeUrl, warpAgent);
    const playerUrl = extractPlayerUrl(ep.body);
    if (!playerUrl) return [];

    // Step 2: Player page via Tor → video sources
    const pp = await httpGet(playerUrl, torAgent);
    const sources = extractVideoSources(pp.body);
    if (!sources.length) return [];

    // Step 3: Resolve redirects via Tor → direct mp4 URLs
    const results: Anime3rbSource[] = [];
    for (const src of sources) {
      if (src.premium || !src.src) continue;
      try {
        const redir = await httpGet(src.src, torAgent, 10000);
        if ((redir.status === 302 || redir.status === 301) && redir.location) {
          results.push({ label: src.label, url: redir.location });
        }
      } catch {}
    }

    return results;
  } catch {
    return [];
  }
}
