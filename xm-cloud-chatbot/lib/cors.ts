import { NextResponse } from 'next/server';

export function corsHeaders(origin: string | null) {
  console.log('[CORS] Generating headers for origin:', origin);
  
  // If origin is null (common in PNA) or missing, we must NOT use '*' if we want credentials.
  // We'll default to the known Sitecore Pages origin to satisfy the browser check.
  const effectiveOrigin = (origin && origin !== 'null') ? origin : 'https://pages.sitecorecloud.io';
  
  return {
    'Access-Control-Allow-Origin': effectiveOrigin,
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With, Access-Control-Request-Private-Network',
    'Access-Control-Allow-Credentials': 'true',
    'Access-Control-Allow-Private-Network': 'true',
  };
}

export function handleOptions(req: Request) {
  const origin = req.headers.get('origin');
  console.log('[CORS] Handling OPTIONS request. Origin:', origin);
  return NextResponse.json({}, { headers: corsHeaders(origin) });
}
