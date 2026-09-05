import { defineConfig } from '@playwright/test';

import baseConfig from '@kya/test-kit/playwright';

export default defineConfig(baseConfig, {
  testDir: './tests/e2e',
  timeout: 30_000,
  use: {
    ...baseConfig.use,
    baseURL: 'http://127.0.0.1:3000',
    colorScheme: 'light',
  },
  webServer: {
    command: 'pnpm build && pnpm start',
    port: 3000,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
