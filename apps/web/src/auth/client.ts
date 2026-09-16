import { createInternalNeonAuth } from '@neondatabase/auth';
import type { ReactBetterAuthClient } from '@neondatabase/auth';
import {
  BetterAuthReactAdapter,
  type BetterAuthReactAdapterInstance,
} from '@neondatabase/auth/react/adapters';

const authUrl = import.meta.env.VITE_NEON_AUTH_URL;

if (!authUrl) {
  throw new Error('VITE_NEON_AUTH_URL is required');
}

const neonAuth = createInternalNeonAuth<BetterAuthReactAdapterInstance>(authUrl, {
  adapter: BetterAuthReactAdapter(),
});

export const authClient: ReactBetterAuthClient = neonAuth.adapter;
export const getAccessToken = neonAuth.getJWTToken;
