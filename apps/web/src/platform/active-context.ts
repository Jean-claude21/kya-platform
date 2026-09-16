import type { KyaActiveContext } from '@jean-claude21/kya-platform-sdk';

const STORAGE_KEY = 'kya-platform.active-unit';
let activeUnitId = readStoredUnit() ?? 'group';

function readStoredUnit(): string | null {
  if (typeof window === 'undefined') return null;
  return window.sessionStorage.getItem(STORAGE_KEY);
}

export function getActiveContext(): KyaActiveContext {
  return { unitId: activeUnitId };
}

export function getActiveUnitId(): string {
  return activeUnitId;
}

export function setActiveUnitId(unitId: string): void {
  const normalized = unitId.trim();
  if (!normalized) throw new Error('An active organizational unit is required');
  activeUnitId = normalized;
  if (typeof window !== 'undefined') window.sessionStorage.setItem(STORAGE_KEY, normalized);
}
