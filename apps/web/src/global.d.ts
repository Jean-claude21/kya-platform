declare module '*.css';

interface ImportMetaEnv {
  readonly VITE_NEON_AUTH_URL: string;
  readonly VITE_KYA_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
