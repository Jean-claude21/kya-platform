import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../platform/api', () => ({ platformRequest: vi.fn(), idempotencyKey: vi.fn(() => 'test-key') }));
vi.mock('../../platform/active-context', () => ({ getActiveUnitId: () => 'direction-cvsi' }));

import { CoreAdministrationView, type Client, type Project, type Employee } from './core-administration';

const client: Client = {
  id: '019a2000-0000-7000-8000-000000000010',
  key: 'solar-client',
  display_name: 'Solar Client SA',
  party_kind: 'organization',
  status: 'active',
  version: 1,
};
const project: Project = {
  id: '019a2000-0000-7000-8000-000000000020',
  key: 'audit-energie',
  name: 'Audit énergétique',
  status: 'active',
  version: 1,
};
const employee: Employee = {
  id: '019a2000-0000-7000-8000-000000000030',
  given_name: 'Afi',
  family_name: 'Mensah',
  preferred_name: null,
  kind: 'employee',
  personnel_number: 'EMP-42',
};

const idleClientForm = {
  creation: { phase: 'idle' as const },
  key: '',
  name: '',
  kind: 'organization' as const,
  onKeyChange: () => undefined,
  onNameChange: () => undefined,
  onKindChange: () => undefined,
  onSubmit: () => undefined,
};
const idleProjectForm = {
  creation: { phase: 'idle' as const },
  key: '',
  name: '',
  clientId: '',
  onKeyChange: () => undefined,
  onNameChange: () => undefined,
  onClientChange: () => undefined,
  onSubmit: () => undefined,
};
const idleEmployeeForm = {
  creation: { phase: 'idle' as const },
  givenName: '',
  familyName: '',
  personnelNumber: '',
  onGivenNameChange: () => undefined,
  onFamilyNameChange: () => undefined,
  onPersonnelNumberChange: () => undefined,
  onSubmit: () => undefined,
};

function view(overrides: Partial<Parameters<typeof CoreAdministrationView>[0]> = {}) {
  return (
    <CoreAdministrationView
      clients={[client]}
      projects={[project]}
      employees={[employee]}
      error=""
      clientForm={idleClientForm}
      projectForm={idleProjectForm}
      employeeForm={idleEmployeeForm}
      {...overrides}
    />
  );
}

describe('core administration', () => {
  it('renders real clients, projects and employees from KYA Core', () => {
    const html = renderToStaticMarkup(view());

    expect(html).toContain('Solar Client SA');
    expect(html).toContain('Audit énergétique');
    expect(html).toContain('Afi');
    expect(html).toContain('EMP-42');
  });

  it('offers governed forms to create a client, a project and an employee', () => {
    const html = renderToStaticMarkup(view());

    expect(html).toContain('Créer un client');
    expect(html).toContain('Créer un projet');
    expect(html).toContain('Rattacher un employé');
  });

  it('lists projects clients as project assignment options', () => {
    const html = renderToStaticMarkup(view());

    expect(html).toContain('Client associé (optionnel)');
    expect(html).toContain('Solar Client SA');
  });

  it('disables submission until required client fields are filled', () => {
    const empty = renderToStaticMarkup(view());
    const filled = renderToStaticMarkup(
      view({
        clientForm: { ...idleClientForm, key: 'new-client', name: 'Nouveau Client' },
      }),
    );

    expect(empty.match(/disabled/g)?.length ?? 0).toBeGreaterThan(
      filled.match(/disabled/g)?.length ?? 0,
    );
  });

  it('surfaces write feedback for each form independently', () => {
    const html = renderToStaticMarkup(
      view({
        clientForm: {
          ...idleClientForm,
          creation: { phase: 'success', message: 'Le client a été enregistré dans KYA Core.' },
        },
        projectForm: {
          ...idleProjectForm,
          creation: { phase: 'error', message: 'La création a échoué.' },
        },
      }),
    );

    expect(html).toContain('Le client a été enregistré dans KYA Core.');
    expect(html).toContain('La création a échoué.');
  });

  it('renders truthful empty states for each record list', () => {
    const html = renderToStaticMarkup(view({ clients: [], projects: [], employees: [] }));

    expect(html).toContain('Aucun client visible dans ce périmètre.');
    expect(html).toContain('Aucun projet visible dans ce périmètre.');
    expect(html).toContain('Aucun employé visible dans ce périmètre.');
  });
});

