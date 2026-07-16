import { NextResponse } from 'next/server';

const BLOCKED_PATHS = [
  '/api/tags', '/v1/models', '/api/version', '/queue/status',
  '/metrics', '/health', '/docs', '/openapi.json', '/openapi.yaml',
  '/swagger.json', '/api/generate', '/api/chat', '/api/agents',
  '/api/kernels', '/api/flows', '/api/2.0', '/api/v1/',
  '/predict', '/inference', '/embed', '/collections',
  '/config', '/sse', '/rest/workflows', '/.well-known/',
];

export function middleware(request: Request) {
  const url = new URL(request.url);
  
  // Block known scanner paths immediately (no 404 page generation)
  for (const path of BLOCKED_PATHS) {
    if (url.pathname.startsWith(path)) {
      return new NextResponse(null, { status: 204 });
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};
