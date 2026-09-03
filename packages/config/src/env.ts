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
  INFISICAL_API_URL: z.url(),
  INFISICAL_CLIENT_ID: required,
  INFISICAL_CLIENT_SECRET: required,
  DEPLOYMENT_PROVIDER: z.enum(['mock', 'dokploy', 'coolify']),
});

export type ServerEnvironment = z.infer<typeof serverEnvironmentSchema>;

export function parseServerEnvironment(input: unknown): ServerEnvironment {
  return serverEnvironmentSchema.parse(input);
}
