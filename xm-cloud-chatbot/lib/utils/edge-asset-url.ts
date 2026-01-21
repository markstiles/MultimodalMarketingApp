export function buildEdgeAssetUrl(args: {
  // Asset item id (GUID-like). Prefer this for URL construction.
  assetId?: string;
  // Legacy / fallback inputs (may exist on some objects); no longer used to build the URL.
  path?: string;
  extension?: string;
  explicitUrl?: string;
}): string | null {
  if (args.explicitUrl && /^https?:\/\//i.test(args.explicitUrl)) {
    return args.explicitUrl;
  }

  const normalizeGuidToN = (value: string): string | null => {
    const v = (value || '').trim();
    if (!v) return null;
    // Common Sitecore-ish formats we may receive:
    // - {GUID}
    // - GUID
    // - GUID with dashes
    const stripped = v.replace(/^[{(]/, '').replace(/[)}]$/, '').replace(/[-{}]/g, '');
    if (/^[0-9a-fA-F]{32}$/.test(stripped)) return stripped.toLowerCase();
    return null;
  };

  const rawAssetId = (args.assetId ?? '').trim();
  if (!rawAssetId) return null;

  // Asset IDs must be in "short" GUID format (32 hex chars, no braces/dashes)
  // for the media handler URL.
  const assetId = normalizeGuidToN(rawAssetId);
  if (!assetId) return null;

  const host = process.env.ENVIRONMENT_HOST;
  const base = `https://${host}.sitecorecloud.io`;

  // Note: keep the path constant as provided by user.
  return `${base}/sitecore/shell/Applications/-/media/${encodeURIComponent(assetId)}.ashx`;
}
