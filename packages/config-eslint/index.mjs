import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    ignores: [
      '**/node_modules/**',
      '**/dist/**',
      '**/.output/**',
      '**/coverage/**',
      '**/site/**',
      '**/tmp/**',
      '**/.venv/**',
      'apps/web/prototypes/**',
      'catalog/templates/**',
    ],
  },
  eslint.configs.recommended,
  {
    files: ['**/*.mjs'],
    languageOptions: {
      globals: {
        Buffer: 'readonly',
        URL: 'readonly',
        console: 'readonly',
        process: 'readonly',
      },
    },
  },
  ...tseslint.configs.strictTypeChecked.map((config) => ({
    ...config,
    files: ['**/*.ts', '**/*.tsx'],
  })),
  {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: { parserOptions: { projectService: true } },
    rules: {
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-floating-promises': 'error',
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['apps/*', '@kya/*/src/*'],
              message: 'Import a package public contract instead.',
            },
          ],
        },
      ],
    },
  },
);
