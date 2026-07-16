import { createStreamProxyHandler, buildProxyUrl } from 'aetherly-stream-proxy';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const proxy = createStreamProxyHandler({
  pathPrefix: '/api/stream',
  allowedHeaderPrefixes: ['referer', 'origin', 'user-agent', 'cookie', 'range', 'x-'],
  defaultUserAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/132.0.0.0 Safari/537.36',
});

export const HEAD = proxy.HEAD;
export const OPTIONS = proxy.OPTIONS;

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/132.0.0.0 Safari/537.36';

function normalizeMfUrl(mfPage: string): string {
  if (!mfPage.includes('/file/') && !mfPage.includes('/download/')) {
    try {
      const u = new URL(mfPage);
      for (const [key, val] of u.searchParams.entries()) {
        if (!val && /^[a-z0-9]{10,}$/i.test(key)) {
          return `https://www.mediafire.com/file/${key}`;
        }
      }
      const raw = mfPage.split('?')[1] || '';
      const bare = raw.split('&')[0].split('=')[0];
      if (/^[a-z0-9]{10,}$/i.test(bare) && !mfPage.includes('/file/')) {
        return `https://www.mediafire.com/file/${bare}`;
      }
    } catch {}
  }
  return mfPage.replace(/^http:\/\//i, 'https://');
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const mfPage = url.searchParams.get('mfPage');
  const videoUrl = url.searchParams.get('url');
  const cookies = url.searchParams.get('cookies');

  if (mfPage) {
    try {
      const normalized = normalizeMfUrl(mfPage);
      const res = await fetch(normalized, {
        headers: { 'User-Agent': UA, 'Accept': 'text/html', 'Referer': 'https://anslayer.com/' },
        signal: AbortSignal.timeout(15000),
      });
      const html = await res.text();
      if (html.includes('Just a moment') || html.includes('challenge-platform') || html.includes('cf_chl_opt')) {
        return new Response('MediaFire is behind Cloudflare challenge', { status: 502 });
      }
      const m = html.match(/(https?:\/\/download[^"]+)/);
      if (!m) return new Response('Could not extract MediaFire download URL', { status: 502 });
      const targetUrl = m[1].replace(/&amp;/g, '&');
      const setCookies = (res.headers as any).getSetCookie?.() || [];
      const cookieStr = setCookies.map((c: string) => c.split(';')[0]).join('; ');

      const proxyUrl = buildProxyUrl(targetUrl, {
        'Cookie': cookieStr,
        'Referer': 'https://www.mediafire.com/',
        'User-Agent': UA,
      });
      const proxyReq = new Request(new URL(proxyUrl, request.url).toString(), {
        headers: request.headers,
      });
      return await proxy.GET(proxyReq);
    } catch (e: any) {
      return new Response('MediaFire proxy failed: ' + e.message, { status: 502 });
    }
  }

  if (videoUrl && cookies) {
    const proxyUrl = buildProxyUrl(videoUrl, {
      'Cookie': cookies,
      'Referer': 'https://www.mediafire.com/',
    });
    const proxyReq = new Request(new URL(proxyUrl, request.url).toString(), {
      headers: request.headers,
    });
    return await proxy.GET(proxyReq);
  }

  if (videoUrl) {
    const proxyUrl = buildProxyUrl(videoUrl);
    const proxyReq = new Request(new URL(proxyUrl, request.url).toString(), {
      headers: request.headers,
    });
    return await proxy.GET(proxyReq);
  }

  return new Response('Missing stream URL', { status: 400 });
}
