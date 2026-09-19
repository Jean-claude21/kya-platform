import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../platform/api', () => ({ platformRequest: vi.fn(), idempotencyKey: vi.fn(() => 'test-key') }));
vi.mock('../../platform/active-context', () => ({ getActiveUnitId: () => 'direction-cvsi' }));

import { OrganizationAdminView, type Unit, type UnitType } from './organization-admin';

const root: Unit = {
  id: '019a2000-0000-7000-8000-000000000001',
  key: 'direction-cvsi',
  type_key: 'direction',
  name: 'Direction des Systèmes',
  valid_from: '2026-01-01T00:00:00Z',
  valid_until: null,
};
const unitTypes: UnitType[] = [
  { key: 'direction', label: 'Direction', allowed_parent_types: ['group'], is_temporary: false },
  { key: 'team', label: 'Équipe', allowed_parent_types: ['direction'], is_temporary: false },
];

function view(overrides: Partial<Parameters<typeof OrganizationAdminView>[0]> = {}) {
  return (
    <OrganizationAdminView
      root={root}
      children={[]}
      unitTypes={unitTypes}
      error=""
      creation={{ phase: 'idle' }}
      newKey=""
      newName=""
      newTypeKey="direction"
      onKeyChange={() => undefined}
      onNameChange={() => undefined}
      onTypeChange={() => undefined}
      onSubmit={() => undefined}
      {...overrides}
    />
  );
}

describe('organization admin', () => {
  it('renders the active organizational structure from real data', () => {
    const html = renderToStaticMarkup(view());

    expect(html).toContain('Direction des Systèmes');
    expect(html).toContain('direction-cvsi');
    expect(html).toContain('Données réelles');
  });

  it('offers a governed form to create a child unit', () => {
    const html = renderToStaticMarkup(view());

    expect(html).toContain('Créer une unité fille');
    expect(html).toContain('Créer l’unité');
  });

  it('disables submission until required fields are filled', () => {
    const empty = renderToStaticMarkup(view({ newKey: '', newName: '' }));
    const filled = renderToStaticMarkup(
      view({ newKey: 'agence-lome', newName: 'Agence Lomé' }),
    );

    expect(empty).toContain('disabled');
    expect(filled.match(/disabled/g)?.length ?? 0).toBeLessThan(
      empty.match(/disabled/g)?.length ?? 0,
    );
  });

  it('surfaces creation feedback without hiding errors', () => {
    const success = renderToStaticMarkup(
      view({ creation: { phase: 'success', message: 'La nouvelle unité a été enregistrée dans KYA Core.' } }),
    );
    const failure = renderToStaticMarkup(
      view({ creation: { phase: 'error', message: 'La création a échoué.' } }),
    );

    expect(success).toContain('La nouvelle unité a été enregistrée dans KYA Core.');
    expect(failure).toContain('La création a échoué.');
  });

  it('renders truthful loading and error states without a root unit', () => {
    const loading = renderToStaticMarkup(view({ root: null, error: '' }));
    const failed = renderToStaticMarkup(
      view({ root: null, error: 'Organisation indisponible.' }),
    );

    expect(loading).toContain('Chargement de la structure');
    expect(failed).toContain('Organisation indisponible.');
  });
});

