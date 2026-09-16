/**
 * Labels for organizational unit type keys seeded by the backend
 * (apps/backend/migrations/versions/20260907_0010_kya_core.py).
 * These keys form a stable contract between the seed and any display surface.
 */
export const organizationalUnitTypeLabels: Record<string, string> = {
  group: 'Groupe',
  country: 'Pays',
  entity: 'Filiale',
  agency: 'Agence',
  direction: 'Direction',
  department: 'Département',
  team: 'Équipe',
  program: 'Programme',
  project: 'Équipe projet',
  community: 'Communauté',
};

export function organizationalUnitTypeLabel(typeKey: string): string {
  return organizationalUnitTypeLabels[typeKey] ?? typeKey;
}
