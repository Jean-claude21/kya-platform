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
  DEPLOYMENT_PROVIDER: z.enum(['mock', 'dokploy', 'coolify']),
});

export type ServerEnvironment = z.infer<typeof serverEnvironmentSchema>;

export function parseServerEnvironment(input: unknown): ServerEnvironment {
  return serverEnvironmentSchema.parse(input);
}
