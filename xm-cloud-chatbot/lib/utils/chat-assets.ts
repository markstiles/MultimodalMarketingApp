import { buildEdgeAssetUrl } from '@/lib/utils/edge-asset-url';

export type ChatAsset = {
  kind: 'image' | 'file';
  url: string;
  thumbUrl?: string;
  name?: string;
  itemId?: string;
  path?: string;
  extension?: string;
  size?: number;
  description?: string;
  width?: number;
  height?: number;
  altText?: string;
};

function addWidthParam(url: string, width: number): string {
  try {
    const u = new URL(url);
    if (!u.searchParams.has('w')) {
      u.searchParams.set('w', String(width));
    }
    return u.toString();
  } catch {
    // fallback for relative-ish strings
    const joiner = url.includes('?') ? '&' : '?';
    return `${url}${joiner}w=${width}`;
  }
}

function isProbablyImageExtension(ext?: string): boolean {
  const e = (ext || '').replace(/^\./, '').toLowerCase();
  return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'avif'].includes(e);
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) return Number(value);
  return undefined;
}

function pickString(obj: any, keys: string[]): string | undefined {
  for (const k of keys) {
    const v = obj?.[k];
    if (typeof v === 'string' && v.trim()) return v;
  }
  return undefined;
}

function extractCandidateObjects(root: unknown): any[] {
  const out: any[] = [];

  const seen = new Set<any>();
  const queue: any[] = [root];

  while (queue.length) {
    const cur = queue.shift();
    if (!cur || typeof cur !== 'object') continue;
    if (seen.has(cur)) continue;
    seen.add(cur);

    if (Array.isArray(cur)) {
      for (const v of cur) queue.push(v);
      continue;
    }

    // Heuristics: an asset-ish object has at least a path/url/id-ish field.
    const hasPath = typeof (cur as any).path === 'string';
    const hasUrl = typeof (cur as any).url === 'string';
    const hasId = typeof (cur as any).itemId === 'string' || typeof (cur as any).id === 'string' || typeof (cur as any).item_id === 'string';

    if (hasPath || hasUrl || hasId) {
      out.push(cur);
    }

    for (const v of Object.values(cur as any)) {
      queue.push(v);
    }
  }

  return out;
}

export function extractChatAssetsFromToolResult(args: {
  result: unknown;
  thumbnailWidth?: number;
}): ChatAsset[] {
  const w = args.thumbnailWidth ?? 100;

  const candidates = extractCandidateObjects(args.result);
  const assets: ChatAsset[] = [];

  for (const c of candidates) {
    const explicitUrl = pickString(c, ['url', 'assetUrl', 'imageUrl', 'mediaUrl']);
    const assetId = pickString(c, ['assetId', 'asset_id', 'itemId', 'id', 'item_id']);
    const path = pickString(c, ['path', 'mediaPath', 'image_path', 'asset_path']);
    const extension = pickString(c, ['extension', 'ext', 'fileExtension', 'image_extension']);

    const url = buildEdgeAssetUrl({
      assetId,
      explicitUrl,
    });

    if (!url) continue;

    const type = pickString(c, ['type', 'assetType', 'mime_type', 'mimeType']);

    const isImage =
      (typeof type === 'string' && type.toLowerCase().startsWith('image/')) ||
      isProbablyImageExtension(extension);

    const asset: ChatAsset = {
      kind: isImage ? 'image' : 'file',
      url,
      thumbUrl: isImage ? addWidthParam(url, w) : undefined,
      name: pickString(c, ['name', 'title', 'displayName', 'filename', 'fileName']),
      itemId: assetId,
      path,
      extension,
      size: asNumber(c?.size),
      description: pickString(c, ['description', 'summary']),
      width: asNumber(c?.width),
      height: asNumber(c?.height),
      altText: pickString(c, ['altText', 'alt_text', 'alt']),
    };

    assets.push(asset);
  }

  // Deduplicate by URL
  const seenUrl = new Set<string>();
  return assets.filter((a) => {
    if (seenUrl.has(a.url)) return false;
    seenUrl.add(a.url);
    return true;
  });
}
