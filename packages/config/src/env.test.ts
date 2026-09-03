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
  INFISICAL_API_URL: 'http://localhost:8081',
  INFISICAL_CLIENT_ID: 'client',
  INFISICAL_CLIENT_SECRET: 'secret',
  DEPLOYMENT_PROVIDER: 'mock',
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
