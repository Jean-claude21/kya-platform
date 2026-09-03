import { describe, expect, it } from 'vitest';

import { parseServerEnvironment } from './env.js';

const valid = {
  APP_ENV: 'local',
  APP_BASE_URL: 'http://localhost:3000',
  API_BASE_URL: 'http://localhost:3001',
  DATABASE_URL: 'postgresql://local',
  AUTH_SECRET: 'a'.repeat(32),
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

  it('rejects a short authentication secret', () => {
    expect(() => parseServerEnvironment({ ...valid, AUTH_SECRET: 'short' })).toThrow();
  });
});
