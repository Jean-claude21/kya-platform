import { KyaPlatformClient, type KyaActiveContext } from '@jean-claude21/kya-platform-sdk';

export type KyaAppRuntime = Readonly<{
  apiUrl: string;
  getAccessToken: () => Promise<string | null>;
  getActiveContext: () => KyaActiveContext | Promise<KyaActiveContext>;
}>;

export function createKyaAppClient(runtime: KyaAppRuntime): KyaPlatformClient {
  return new KyaPlatformClient({
    apiUrl: runtime.apiUrl,
    getAccessToken: runtime.getAccessToken,
    getActiveContext: runtime.getActiveContext,
  });
}
