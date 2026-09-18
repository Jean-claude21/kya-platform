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

export type KyaOrganizationalUnit = Readonly<{
  id: string;
  key: string;
  type_key: string;
  name: string;
  valid_from: string;
  valid_until: string | null;
}>;

export type KyaOrganizationalUnitList = Readonly<{
  items: readonly KyaOrganizationalUnit[];
}>;

export type KyaApplication = Readonly<{
  artifact_id: string;
  name: string;
  summary: string | null;
  version: string;
  lifecycle: string;
  enabled: boolean;
  owner_workspace_id: string;
  launch_url: string;
  launch_mode: 'same-tab' | 'new-tab' | 'embedded';
  icon_url: string | null;
  health_url: string | null;
  required_sdk: string | null;
  visibility: 'private' | 'restricted' | 'internal' | 'public';
  default_scope: 'personal' | 'workspace' | 'unit' | 'subsidiary' | 'group';
  allowed_scopes: readonly string[];
  declared_permissions: readonly string[];
  effective_permissions: readonly string[];
  features: readonly string[];
}>;

export type KyaApplicationList = Readonly<{
  items: readonly KyaApplication[];
  active_unit: string;
}>;

export type KyaTelemetryEvent = Readonly<{
  kind: 'request.completed' | 'request.failed';
  path: string;
  method: string;
  status: number;
  duration_ms: number;
  correlation_id: string | null;
}>;

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
  onTelemetry?: (event: KyaTelemetryEvent) => void;
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
  readonly #onTelemetry: KyaPlatformClientOptions['onTelemetry'];

  constructor(options: KyaPlatformClientOptions) {
    this.#apiUrl = normalizeApiUrl(options.apiUrl);
    this.#getAccessToken = options.getAccessToken;
    this.#getActiveContext = options.getActiveContext;
    // Browser implementations require `fetch` to be called with the global
    // object as its receiver. Keeping the bare function in a class field and
    // invoking it through `this.#fetch(...)` otherwise changes the receiver to
    // the SDK instance and fails before the request reaches KYA-Platform.
    this.#fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.#onTelemetry = options.onTelemetry;
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
    const normalizedPath = path.replace(/^\/+/, '');
    const startedAt = Date.now();
    let response: Response;
    try {
      response = await this.#fetch(`${this.#apiUrl}/${normalizedPath}`, request);
    } catch (error) {
      this.#emitTelemetry({
        kind: 'request.failed',
        path: normalizedPath,
        method: init.method ?? 'GET',
        status: 0,
        duration_ms: Date.now() - startedAt,
        correlation_id: null,
      });
      throw error;
    }
    this.#emitTelemetry({
      kind: response.ok ? 'request.completed' : 'request.failed',
      path: normalizedPath,
      method: init.method ?? 'GET',
      status: response.status,
      duration_ms: Date.now() - startedAt,
      correlation_id: response.headers.get('x-correlation-id'),
    });
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

  listApplications(): Promise<KyaApplicationList> {
    return this.request<KyaApplicationList>('applications');
  }

  getApplication(artifactId: string): Promise<KyaApplication> {
    if (!artifactId.trim()) throw new Error('A KYA application artifact id is required.');
    return this.request<KyaApplication>(`applications/${encodeURIComponent(artifactId)}`);
  }

  getOrganizationalUnit(unitKey: string): Promise<KyaOrganizationalUnit> {
    if (!unitKey.trim()) throw new Error('A KYA organizational unit key is required.');
    return this.request<KyaOrganizationalUnit>(`core/organization/${encodeURIComponent(unitKey)}`);
  }

  listChildUnits(unitKey: string): Promise<KyaOrganizationalUnitList> {
    if (!unitKey.trim()) throw new Error('A KYA organizational unit key is required.');
    return this.request<KyaOrganizationalUnitList>(
      `core/organization/${encodeURIComponent(unitKey)}/children`,
    );
  }

  #emitTelemetry(event: KyaTelemetryEvent): void {
    try {
      this.#onTelemetry?.(event);
    } catch {
      // Application telemetry must never change the result of a governed API call.
    }
  }
}
