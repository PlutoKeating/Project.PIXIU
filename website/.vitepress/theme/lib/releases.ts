import { site } from './site';
export interface Asset {
  id: number;
  name: string;
  size: number;
  browser_download_url: string;
  digest: string | null;
}
export interface Release {
  id: number;
  name: string | null;
  tag_name: string;
  body: string | null;
  html_url: string;
  published_at: string | null;
  prerelease: boolean;
  draft: boolean;
  assets: Asset[];
}
export class ReleaseError extends Error {
  constructor(
    public kind: 'network' | 'rate' | 'missing' | 'invalid' | 'server',
    public reset?: Date,
  ) {
    super(kind);
  }
}
export function githubUrl(value: unknown, asset = false): string {
  if (typeof value !== 'string') return '';
  try {
    const url = new URL(value);
    const prefix = `/${site.repository}/releases/${asset ? 'download/' : 'tag/'}`;
    return url.protocol === 'https:' &&
      url.hostname === 'github.com' &&
      !url.username &&
      !url.password &&
      url.pathname.startsWith(prefix)
      ? url.href
      : '';
  } catch {
    return '';
  }
}
function parseRelease(value: unknown): Release {
  const r = value as Release;
  if (
    !r ||
    !Number.isSafeInteger(r.id) ||
    typeof r.tag_name !== 'string' ||
    !r.tag_name ||
    !githubUrl(r.html_url) ||
    !Array.isArray(r.assets) ||
    typeof r.prerelease !== 'boolean' ||
    typeof r.draft !== 'boolean' ||
    (r.name !== null && typeof r.name !== 'string') ||
    (r.body !== null && typeof r.body !== 'string') ||
    (r.published_at !== null &&
      (typeof r.published_at !== 'string' || !Number.isFinite(Date.parse(r.published_at))))
  )
    throw new ReleaseError('invalid');
  for (const asset of r.assets) {
    if (
      !Number.isSafeInteger(asset.id) ||
      typeof asset.name !== 'string' ||
      !asset.name ||
      !Number.isFinite(asset.size) ||
      asset.size < 0 ||
      !githubUrl(asset.browser_download_url, true) ||
      (asset.digest != null && typeof asset.digest !== 'string')
    )
      throw new ReleaseError('invalid');
  }
  return r;
}
async function request(
  path: string,
  signal: AbortSignal,
): Promise<{ data: unknown; next: boolean }> {
  try {
    const response = await fetch(`${site.api}${path}`, {
      signal,
      cache: 'no-store',
      headers: { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' },
    });
    if (
      response.status === 429 ||
      (response.status === 403 && response.headers.get('x-ratelimit-remaining') === '0')
    ) {
      const reset = Number(response.headers.get('x-ratelimit-reset'));
      throw new ReleaseError('rate', reset ? new Date(reset * 1000) : undefined);
    }
    if (response.status === 404) throw new ReleaseError('missing');
    if (!response.ok) throw new ReleaseError('server');
    return {
      data: await response.json(),
      next: /rel="next"/.test(response.headers.get('link') || ''),
    };
  } catch (error) {
    if (error instanceof ReleaseError) throw error;
    if (signal.aborted) throw error;
    throw new ReleaseError('network');
  }
}
export async function latestRelease(signal: AbortSignal): Promise<Release> {
  const { data } = await request('/releases/latest', signal);
  const release = parseRelease(data);
  if (release.draft || release.prerelease) throw new ReleaseError('invalid');
  return release;
}
export async function listReleases(page: number, signal: AbortSignal) {
  const { data, next } = await request(`/releases?per_page=10&page=${page}`, signal);
  if (!Array.isArray(data)) throw new ReleaseError('invalid');
  return { releases: data.map(parseRelease).filter((r) => !r.draft), next };
}
export function formatBytes(size: number) {
  if (size < 1024) return `${size} B`;
  const unit = size < 1024 ** 2 ? 1 : size < 1024 ** 3 ? 2 : 3;
  return `${(size / 1024 ** unit).toLocaleString('zh-CN', { maximumFractionDigits: 1 })} ${['B', 'KB', 'MB', 'GB'][unit]}`;
}
