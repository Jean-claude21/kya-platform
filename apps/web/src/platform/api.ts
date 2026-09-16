import { KyaPlatformClient, createIdempotencyKey } from '@jean-claude21/kya-platform-sdk';

import { getAccessToken } from '../auth/client';

export type LoadState<T> =
  | { status: 'loading'; data: null; error: null }
  | { status: 'ready'; data: T; error: null }
  | { status: 'error'; data: null; error: string };

const apiUrl = import.meta.env.VITE_KYA_API_URL;
if (!apiUrl) throw new Error('VITE_KYA_API_URL is required');

export const platformClient = new KyaPlatformClient({
  apiUrl,
  getAccessToken,
  getActiveContext: () => ({ unitId: 'group' }),
});

export async function platformRequest<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    return await platformClient.request<T>(path, init);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('L’API KYA-Platform est momentanément inaccessible. Réessayez.', {
        cause: error,
      });
    }
    throw error;
  }
}

export function idempotencyKey(action: string): string {
  return createIdempotencyKey(action);
}
