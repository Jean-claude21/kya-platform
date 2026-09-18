import { describe, expect, it, vi } from 'vitest';

import { KyaPlatformClient, createIdempotencyKey } from './index';

describe('KyaPlatformClient', () => {
  it('preserves the browser receiver when using the global fetch implementation', async () => {
    const browserFetch = vi.fn(function (this: unknown) {
      if (this !== globalThis) throw new TypeError('Illegal invocation');
      return Promise.resolve(
        new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    }) as unknown as typeof globalThis.fetch;
    vi.stubGlobal('fetch', browserFetch);

    try {
      const client = new KyaPlatformClient({
        apiUrl: 'https://api.kya.example',
        getAccessToken: () => Promise.resolve('access-token'),
        getActiveContext: () => ({ unitId: 'group' }),
      });

      await client.listWorkspaces();

      expect(browserFetch).toHaveBeenCalledOnce();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('adds identity and organizational context to every request', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = new KyaPlatformClient({
      apiUrl: 'https://api.kya.example/',
      getAccessToken: () => Promise.resolve('access-token'),
      getActiveContext: () => ({ unitId: 'direction-cvsi', workspaceId: 'platform' }),
      fetch,
    });

    await client.listWorkspaces();

    const [url, request] = fetch.mock.calls[0] ?? [];
    const headers = new Headers(request?.headers);
    expect(url).toBe('https://api.kya.example/api/v1/workspaces');
    expect(headers.get('Authorization')).toBe('Bearer access-token');
    expect(headers.get('X-KYA-Unit-ID')).toBe('direction-cvsi');
    expect(headers.get('X-KYA-Workspace-ID')).toBe('platform');
  });

  it('preserves structured KYA errors for application recovery', async () => {
    const client = new KyaPlatformClient({
      apiUrl: 'https://api.kya.example/api/v1',
      getAccessToken: () => Promise.resolve('access-token'),
      getActiveContext: () => ({ unitId: 'group' }),
      fetch: vi.fn<typeof globalThis.fetch>().mockResolvedValue(
        new Response(JSON.stringify({ code: 'permission_denied', detail: 'Accès refusé' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    });

    await expect(client.getSession()).rejects.toMatchObject({
      status: 403,
      message: 'Accès refusé',
      problem: { code: 'permission_denied' },
    });
  });

  it('refuses calls without a user token', async () => {
    const client = new KyaPlatformClient({
      apiUrl: 'https://api.kya.example',
      getAccessToken: () => Promise.resolve(null),
      getActiveContext: () => ({ unitId: 'group' }),
      fetch: vi.fn<typeof globalThis.fetch>(),
    });

    await expect(client.getSession()).rejects.toMatchObject({ status: 401 });
  });

  it('discovers governed applications through the active context', async () => {
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(
      new Response(JSON.stringify({ items: [], active_unit: 'group' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    const client = new KyaPlatformClient({
      apiUrl: 'https://api.kya.example',
      getAccessToken: () => Promise.resolve('access-token'),
      getActiveContext: () => ({ unitId: 'group' }),
      fetch,
    });

    await client.listApplications();

    expect(fetch.mock.calls[0]?.[0]).toBe('https://api.kya.example/api/v1/applications');
  });

  it('reports request telemetry without exposing credentials', async () => {
    const onTelemetry = vi.fn();
    const client = new KyaPlatformClient({
      apiUrl: 'https://api.kya.example',
      getAccessToken: () => Promise.resolve('secret-access-token'),
      getActiveContext: () => ({ unitId: 'group' }),
      fetch: vi.fn<typeof globalThis.fetch>().mockResolvedValue(
        new Response(JSON.stringify({ items: [], active_unit: 'group' }), {
          status: 200,
          headers: { 'x-correlation-id': 'correlation-1' },
        }),
      ),
      onTelemetry,
    });

    await client.listApplications();

    expect(onTelemetry).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'request.completed',
        path: 'applications',
        status: 200,
        correlation_id: 'correlation-1',
      }),
    );
    expect(JSON.stringify(onTelemetry.mock.calls)).not.toContain('secret-access-token');
  });
});

describe('createIdempotencyKey', () => {
  it('creates an action-scoped replay key', () => {
    expect(createIdempotencyKey('create project')).toMatch(/^create-project-[0-9a-f-]+$/);
  });
});
