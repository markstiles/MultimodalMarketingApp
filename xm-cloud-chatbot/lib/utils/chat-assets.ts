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

interface SearchResultItem {
  itemId?: string;
  id?: string;
  item_id?: string;
  path?: string;
  name?: string;
  displayName?: string | null;
  type?: string | null;
  url?: string;
  templateName?: string;
  innerItem?: {
    alt?: string;
    width?: number;
    height?: number;
    extension?: string;
    size?: number;
    description?: string;
  };
}

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

function isImageExtension(ext?: string): boolean {
  const e = (ext || '').replace(/^\./, '').toLowerCase();
  return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'avif', 'bmp', 'ico', 'tiff', 'ashx'].includes(e);
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))) return Number(value);
  return undefined;
}

export function extractChatAssetsFromToolResult(args: {
  results: SearchResultItem[];
  thumbnailWidth?: number;
}): ChatAsset[] {
  const w = args.thumbnailWidth ?? 100;

  const assets: ChatAsset[] = [];

  for (const result of args.results) {
    const assetId = result.itemId || result.id || result.item_id;
    const url = buildEdgeAssetUrl({ assetId });
    if (!url) continue;

    const path = result.path as string | undefined;
    const extension = result.innerItem?.extension;
    const type = result.type as string | undefined;
    const name = result.displayName || result.name;
    const isImage = isImageExtension(extension)

    // Get dimensions from innerItem (prioritized) or fallback to root properties
    const width = asNumber(result.innerItem?.width) || asNumber((result as any).width) || asNumber((result as any).Width);
    const height = asNumber(result.innerItem?.height) || asNumber((result as any).height) || asNumber((result as any).Height);

    const asset: ChatAsset = {
      kind: isImage ? 'image' : 'file',
      url,
      thumbUrl: isImage ? addWidthParam(url, w) : undefined,
      name,
      itemId: assetId,
      path,
      extension: extension,
      size: asNumber(result.innerItem?.size) || asNumber((result as any).size),
      description: result.innerItem?.description,
      width,
      height,
      altText: result.innerItem?.alt,
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
