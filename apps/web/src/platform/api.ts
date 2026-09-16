import { getAccessToken } from '../auth/client';

export type LoadState<T> =
  | { status: 'loading'; data: null; error: null }
  | { status: 'ready'; data: T; error: null }
  | { status: 'error'; data: null; error: string };

export async function platformRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = import.meta.env.VITE_KYA_API_URL;
  const token = await getAccessToken();
  if (!apiUrl || !token) throw new Error('La session ou l’API KYA-Platform est indisponible.');
  const headers = new Headers(init?.headers);
  headers.set('Authorization', `Bearer ${token}`);
  headers.set('X-KYA-Unit-ID', 'group');
  let response: Response;
  try {
    response = await fetch(`${apiUrl.replace(/\/$/, '')}/api/v1${path}`, {
      ...(init ?? {}),
      headers,
    });
  } catch {
    throw new Error('L’API KYA-Platform est momentanément inaccessible. Réessayez.');
  }
  if (!response.ok) {
    const problem = (await response.json().catch(() => null)) as {
      detail?: string;
      title?: string;
    } | null;
    throw new Error(
      problem?.detail ?? problem?.title ?? `Requête refusée (${String(response.status)}).`,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function idempotencyKey(action: string): string {
  return `${action}-${crypto.randomUUID()}`;
}
