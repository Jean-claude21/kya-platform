export type ActiveKyaContext = Readonly<{
  accessToken: string;
  unitId: string;
  workspaceId: string;
}>;

export async function callBusinessApi<T>(
  path: string,
  context: ActiveKyaContext,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      ...init.headers,
      Authorization: `Bearer ${context.accessToken}`,
      'X-KYA-Unit-ID': context.unitId,
      'X-KYA-Workspace-ID': context.workspaceId,
    },
  });
  if (!response.ok) throw new Error(`Business API request failed with ${response.status}`);
  return (await response.json()) as T;
}
