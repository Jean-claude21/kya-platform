import { z } from 'zod';

const required = z.string().min(1);
export const serverEnvironmentSchema = z.object({
  APP_ENV: z.enum(['local', 'preview', 'test', 'production']),
  APP_BASE_URL: z.url(),
  API_BASE_URL: z.url(),
  NEON_AUTH_BASE_URL: z.url(),
  VITE_NEON_AUTH_URL: z.url(),
  OPENFGA_API_URL: z.url(),
  OPENFGA_STORE_ID: required,
  OPENFGA_MODEL_ID: required,
  KYA_INFISICAL_API_URL: z.url(),
  KYA_INFISICAL_CLIENT_ID: required,
  KYA_INFISICAL_CLIENT_SECRET: required,
  KYA_INFISICAL_PROJECT_ID: required,
  KYA_INFISICAL_ENVIRONMENT: z.enum(['dev', 'staging', 'prod']),
  KYA_INFISICAL_SECRET_PATH: z.string().startsWith('/'),
  KYA_DEPLOYMENT_PROVIDER: z.enum(['mock', 'dokploy', 'coolify']),
  KYA_NEON_PROJECT_ID: required.optional(),
  KYA_NEON_API_KEY: required.optional(),
  KYA_DOKPLOY_API_URL: z.url().optional(),
  KYA_DOKPLOY_API_TOKEN: required.optional(),
  KYA_DOKPLOY_PROJECT_ID: required.optional(),
  KYA_DOKPLOY_PREVIEW_APP_ID: required.optional(),
  KYA_DOKPLOY_STAGING_APP_ID: required.optional(),
  KYA_DOKPLOY_PRODUCTION_APP_ID: required.optional(),
  KYA_COOLIFY_API_URL: z.url().optional(),
  KYA_COOLIFY_API_TOKEN: required.optional(),
  KYA_COOLIFY_PREVIEW_APP_UUID: required.optional(),
  KYA_COOLIFY_STAGING_APP_UUID: required.optional(),
  KYA_COOLIFY_PRODUCTION_APP_UUID: required.optional(),
});

export type ServerEnvironment = z.infer<typeof serverEnvironmentSchema>;

export function parseServerEnvironment(input: unknown): ServerEnvironment {
  return serverEnvironmentSchema.parse(input);
}
