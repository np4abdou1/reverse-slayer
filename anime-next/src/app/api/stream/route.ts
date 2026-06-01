import { NextRequest } from 'next/server';

const FORWARDED_HEADERS = [
  'accept-ranges',
  'cache-control',
  'content-length',
  'content-range',
  'content-type',
] as const;

function isAllowedHost(host: string) {
  return host === 'mediafire.com'
    || host.endsWith('.mediafire.com')
    || host === 'streamtape.to'
    || host.endsWith('.streamtape.to')
    || host === 'tapecontent.net'
    || host.endsWith('.tapecontent.net')
    || host === 'ab-hunter.com'
    || host.endsWith('.ab-hunter.com');
}

export async function GET(request: NextRequest) {
  const target = request.nextUrl.searchParams.get('url');
  if (!target) return new Response('Missing stream URL', { status: 400 });

  let url: URL;
  try {
    url = new URL(target);
  } catch {
    return new Response('Invalid stream URL', { status: 400 });
  }

  if (!['http:', 'https:'].includes(url.protocol) || !isAllowedHost(url.hostname.toLowerCase())) {
    return new Response('Unsupported stream host', { status: 403 });
  }

  let upstream: Response;
  try {
    upstream = await fetchAllowed(url, request);
  } catch {
    return new Response('Stream upstream failed', { status: 502 });
  }

  const headers = new Headers();
  for (const name of FORWARDED_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  headers.set('Access-Control-Allow-Origin', '*');

  return new Response(upstream.body, { status: upstream.status, headers });
}

async function fetchAllowed(initialUrl: URL, request: NextRequest) {
  let url = initialUrl;
  for (let redirects = 0; redirects <= 4; redirects++) {
    if (!isAllowedHost(url.hostname.toLowerCase())) throw new Error('Unsupported redirect host');
    const response = await fetch(url, {
      redirect: 'manual',
      headers: {
        'User-Agent': request.headers.get('user-agent') || 'Mozilla/5.0',
        ...(request.headers.get('range') ? { Range: request.headers.get('range')! } : {}),
      },
    });
    const location = response.headers.get('location');
    if (!location || response.status < 300 || response.status >= 400) return response;
    url = new URL(location, url);
  }
  throw new Error('Too many redirects');
}
