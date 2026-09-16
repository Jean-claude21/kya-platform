export type KyaActiveContext = Readonly<{
  unitId: string;
  workspaceId?: string;
}>;

export type KyaSession = Readonly<{
  principal_id: string;
  email: string | null;
  active_unit_id: string;
  mcp_ready: boolean;
}>;

export type KyaWorkspace = Readonly<{
  id: string;
  key: string;
  name: string;
  kind: string;
  classification: string;
}>;

export type KyaWorkspaceList = Readonly<{ items: readonly KyaWorkspace[] }>;

export type KyaProblem = Readonly<{
  code?: string;
  title?: string;
  detail?: string;
  correlation_id?: string;
}>;

export type KyaRequestOptions = Readonly<{
  idempotencyKey?: string;
  signal?: AbortSignal;
}>;

export type KyaPlatformClientOptions = Readonly<{
  apiUrl: string;
  getAccessToken: () => Promise<string | null>;
  getActiveContext: () => KyaActiveContext | Promise<KyaActiveContext>;
  fetch?: typeof globalThis.fetch;
}>;

export class KyaPlatformError extends Error {
  readonly status: number;
  readonly problem: KyaProblem | null;

  constructor(status: number, problem: KyaProblem | null) {
    super(problem?.detail ?? problem?.title ?? `KYA-Platform request failed (${String(status)}).`);
    this.name = 'KyaPlatformError';
    this.status = status;
    this.problem = problem;
  }
}

function normalizeApiUrl(value: string): string {
  const normalized = value.replace(/\/+$/, '');
  if (!normalized) throw new Error('KYA-Platform API URL is required.');
  return normalized.endsWith('/api/v1') ? normalized : `${normalized}/api/v1`;
}

export function createIdempotencyKey(action: string): string {
  const prefix = action
    .trim()
    .replace(/[^a-z0-9-]+/gi, '-')
    .replace(/^-|-$/g, '');
  if (!prefix) throw new Error('An idempotency action name is required.');
  return `${prefix}-${crypto.randomUUID()}`;
}

export class KyaPlatformClient {
  readonly #apiUrl: string;
  readonly #getAccessToken: KyaPlatformClientOptions['getAccessToken'];
  readonly #getActiveContext: KyaPlatformClientOptions['getActiveContext'];
  readonly #fetch: typeof globalThis.fetch;

  constructor(options: KyaPlatformClientOptions) {
    this.#apiUrl = normalizeApiUrl(options.apiUrl);
    this.#getAccessToken = options.getAccessToken;
    this.#getActiveContext = options.getActiveContext;
    this.#fetch = options.fetch ?? globalThis.fetch;
  }

  async request<T>(
    path: string,
    init: RequestInit = {},
    options: KyaRequestOptions = {},
  ): Promise<T> {
    const [token, context] = await Promise.all([this.#getAccessToken(), this.#getActiveContext()]);
    if (!token) throw new KyaPlatformError(401, { code: 'authentication_required' });
    if (!context.unitId) throw new Error('An active KYA organizational unit is required.');

    const headers = new Headers(init.headers);
    headers.set('Authorization', `Bearer ${token}`);
    headers.set('X-KYA-Unit-ID', context.unitId);
    if (context.workspaceId) headers.set('X-KYA-Workspace-ID', context.workspaceId);
    if (options.idempotencyKey) headers.set('Idempotency-Key', options.idempotencyKey);

    const request: RequestInit = {
      ...init,
      headers,
    };
    const signal = options.signal ?? init.signal;
    if (signal !== undefined) request.signal = signal;
    const response = await this.#fetch(`${this.#apiUrl}/${path.replace(/^\/+/, '')}`, request);
    if (!response.ok) {
      const problem = (await response.json().catch(() => null)) as KyaProblem | null;
      throw new KyaPlatformError(response.status, problem);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  getSession(): Promise<KyaSession> {
    return this.request<KyaSession>('account/me');
  }

  listWorkspaces(): Promise<KyaWorkspaceList> {
    return this.request<KyaWorkspaceList>('workspaces');
  }
}
