import { describe, expect, it } from 'vitest';

import { parseServerEnvironment } from './env.js';

const valid = {
  APP_ENV: 'local',
  APP_BASE_URL: 'http://localhost:3000',
  API_BASE_URL: 'http://localhost:8000',
  NEON_AUTH_BASE_URL: 'https://auth.example.neon.tech',
  VITE_NEON_AUTH_URL: 'https://auth.example.neon.tech',
  OPENFGA_API_URL: 'http://localhost:8080',
  OPENFGA_STORE_ID: 'store',
  OPENFGA_MODEL_ID: 'model',
  KYA_INFISICAL_API_URL: 'http://localhost:8081',
  KYA_INFISICAL_CLIENT_ID: 'client',
  KYA_INFISICAL_CLIENT_SECRET: 'secret',
  KYA_INFISICAL_PROJECT_ID: 'project',
  KYA_INFISICAL_ENVIRONMENT: 'staging',
  KYA_INFISICAL_SECRET_PATH: '/',
  KYA_DEPLOYMENT_PROVIDER: 'mock',
  KYA_NEON_PROJECT_ID: 'neon-project',
  KYA_NEON_API_KEY: 'neon-api-key',
  KYA_DOKPLOY_API_URL: 'https://dokploy.example.com',
  KYA_DOKPLOY_API_TOKEN: 'dokploy-token',
  KYA_DOKPLOY_PROJECT_ID: 'dokploy-project',
  KYA_DOKPLOY_PREVIEW_APP_ID: 'dokploy-preview',
  KYA_DOKPLOY_STAGING_APP_ID: 'dokploy-staging',
  KYA_DOKPLOY_PRODUCTION_APP_ID: 'dokploy-production',
  KYA_COOLIFY_API_URL: 'https://coolify.example.com',
  KYA_COOLIFY_API_TOKEN: 'coolify-token',
  KYA_COOLIFY_PREVIEW_APP_UUID: 'coolify-preview',
  KYA_COOLIFY_STAGING_APP_UUID: 'coolify-staging',
  KYA_COOLIFY_PRODUCTION_APP_UUID: 'coolify-production',
} as const;

describe('serverEnvironmentSchema', () => {
  it('accepts a complete server environment', () => {
    expect(parseServerEnvironment(valid)).toEqual(valid);
  });

  it('does not accept a direct database connection in the Web contract', () => {
    const parsed = parseServerEnvironment({ ...valid, DATABASE_URL: 'postgresql://must-not-leak' });

    expect(parsed).not.toHaveProperty('DATABASE_URL');
  });
});
