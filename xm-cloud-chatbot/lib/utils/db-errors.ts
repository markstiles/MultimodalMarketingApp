export function isDatabaseUnavailableError(error: unknown): boolean {
  if (!error) return false;

  const anyErr = error as any;
  const message = String(anyErr?.message || '');
  const code = String(anyErr?.code || anyErr?.errno || '');

  // Common Prisma connection/init errors
  if (code === 'P1001' || code === 'P1002' || code === 'P1003') return true;

  // Node/pg connection errors often bubble up this way
  if (code === 'ECONNREFUSED' || code === 'ENOTFOUND' || code === 'ETIMEDOUT') return true;

  // Message-based fallbacks (Prisma + pg)
  if (/ECONNREFUSED/i.test(message)) return true;
  if (/Can\s*not\s*reach\s*database\s*server/i.test(message)) return true;
  if (/connect\s+ECONNREFUSED/i.test(message)) return true;
  if (/password\s+authentication\s+failed/i.test(message)) return true;

  // If Prisma wraps the error, look at the cause/message fields.
  const meta = anyErr?.meta;
  if (meta && typeof meta === 'object') {
    const metaMessage = String((meta as any)?.message || (meta as any)?.cause || '');
    if (/ECONNREFUSED/i.test(metaMessage)) return true;
    if (/Can\s*not\s*reach\s*database\s*server/i.test(metaMessage)) return true;
  }

  return false;
}

export function getDatabaseUnavailableHint(): string {
  return [
    'Database connection failed (Postgres).',
    'If you are running locally, start Postgres (e.g. `cd docker; docker-compose up -d`).',
    'Then ensure `xm-cloud-chatbot/.env` has a valid `POSTGRES_URL` (or `DATABASE_URL`) pointing at it.',
  ].join(' ');
}
