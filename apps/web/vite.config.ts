import viteReact from '@vitejs/plugin-react';
import { tanstackStart } from '@tanstack/react-start/plugin/vite';
import { nitro } from 'nitro/vite';
import { configDefaults, defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [tanstackStart(), nitro(), viteReact()],
  test: {
    exclude: [...configDefaults.exclude, 'tests/e2e/**'],
  },
});
