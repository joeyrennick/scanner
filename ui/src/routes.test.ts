import { describe, expect, it } from 'vitest';
import { appRoutes, getRouteMeta } from './routes';

describe('app routes', () => {
  it('uses unique paths for every routed screen', () => {
    const paths = appRoutes.map((route) => route.path);

    expect(new Set(paths).size).toBe(paths.length);
  });

  it('includes the cache warmup workflow as a routeable screen', () => {
    expect(getRouteMeta('/cache-warmup')).toMatchObject({
      title: 'Cache Warmup',
      navLabel: 'Cache Warmup'
    });
  });

  it('falls back to the dashboard metadata for unknown paths', () => {
    expect(getRouteMeta('/missing')).toMatchObject({ title: 'Dashboard' });
  });
});
