export function buildEdgeAssetUrl(args: {
  // Canonical name for the environment host segment, e.g. "env-abc123".
  // Example output: https://edge.sitecorecloud.io/<environmentHost>/<path>.<ext>
  environmentHost?: string;
  path?: string;
  extension?: string;
  explicitUrl?: string;
}): string | null {
  if (args.explicitUrl && /^https?:\/\//i.test(args.explicitUrl)) {
    return args.explicitUrl;
  }

  const environmentHost = (args.environmentHost ?? '').trim();
  const path = (args.path || '').trim();
  if (!environmentHost || !path) return null;

  // Example target format (per project prompt):
  // https://edge.sitecorecloud.io/<SITECORE_ENVIRONMENT_NAME><image_path>.<image_extension>
  const base = 'https://edge.sitecorecloud.io';

  const hostPart = '/' + environmentHost.replace(/^\/+/, '').replace(/\/+$/, '');
  const pathPart = '/' + path.replace(/^\/+/, '');

  const ext = (args.extension || '').replace(/^\./, '').trim();

  // If the path already has an extension, do not append.
  const hasDotExt = /\.[a-z0-9]{2,5}$/i.test(pathPart);
  const withExt = !hasDotExt && ext ? `${pathPart}.${ext}` : pathPart;

  return `${base}${hostPart}${withExt}`;
}
