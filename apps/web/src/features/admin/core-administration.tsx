import { useEffect, useState } from 'react';
import { Icon, StatusBadge } from '@kya/design-system';
import { platformRequest, idempotencyKey } from '../../platform/api';
import { getActiveUnitId } from '../../platform/active-context';

export type Client = {
  id: string;
  key: string;
  display_name: string;
  party_kind: string;
  status: string;
  version: number;
};
export type Project = { id: string; key: string; name: string; status: string; version: number };
export type Employee = {
  id: string;
  given_name: string;
  family_name: string;
  preferred_name: string | null;
  kind: string;
  personnel_number: string | null;
};
type List<T> = { items: T[] };

const domains = [
  {
    name: 'Organisation',
    detail: 'Unités et validité temporelle',
    icon: 'people' as const,
    state: 'Configurable',
  },
  {
    name: 'Parties & clients',
    detail: 'Identités métier partagées',
    icon: 'user' as const,
    state: 'Configurable',
  },
  {
    name: 'Employés',
    detail: 'Personnel rattaché à une unité',
    icon: 'user' as const,
    state: 'Configurable',
  },
  {
    name: 'Projets',
    detail: 'Références transversales',
    icon: 'folder' as const,
    state: 'Configurable',
  },
  {
    name: 'Data contracts',
    detail: 'Schémas, versions et lignage',
    icon: 'database' as const,
    state: 'Service dédié',
  },
  {
    name: 'Politiques & audit',
    detail: 'Décisions et preuves',
    icon: 'shield' as const,
    state: 'Service dédié',
  },
];

export type WriteState =
  | { phase: 'idle' }
  | { phase: 'working' }
  | { phase: 'success'; message: string }
  | { phase: 'error'; message: string };

function WriteFeedback({ state }: { state: WriteState }) {
  if (state.phase === 'success')
    return (
      <p className="review-duty-warning" data-override="false" role="status">
        {state.message}
      </p>
    );
  if (state.phase === 'error')
    return (
      <p className="review-duty-warning" data-override="true" role="alert">
        {state.message}
      </p>
    );
  return null;
}

export function CoreAdministrationView({
  clients,
  projects,
  employees,
  error,
  clientForm,
  projectForm,
  employeeForm,
}: {
  clients: Client[];
  projects: Project[];
  employees: Employee[];
  error: string;
  clientForm: {
    creation: WriteState;
    key: string;
    name: string;
    kind: 'organization' | 'person';
    onKeyChange: (value: string) => void;
    onNameChange: (value: string) => void;
    onKindChange: (value: 'organization' | 'person') => void;
    onSubmit: () => void;
  };
  projectForm: {
    creation: WriteState;
    key: string;
    name: string;
    clientId: string;
    onKeyChange: (value: string) => void;
    onNameChange: (value: string) => void;
    onClientChange: (value: string) => void;
    onSubmit: () => void;
  };
  employeeForm: {
    creation: WriteState;
    givenName: string;
    familyName: string;
    personnelNumber: string;
    onGivenNameChange: (value: string) => void;
    onFamilyNameChange: (value: string) => void;
    onPersonnelNumberChange: (value: string) => void;
    onSubmit: () => void;
  };
}) {
  return (
    <section className="admin-detail-page" aria-labelledby="core-title">
      <header className="page-lead">
        <div>
          <span className="eyebrow">Socle de références Groupe</span>
          <h1 id="core-title">Administration de KYA Core</h1>
          <p>
            Un noyau minimal, historisé et interopérable. KYA Core référence les autorités ; il ne
            remplace pas chaque application métier.
          </p>
        </div>
        <StatusBadge tone={error ? 'warning' : 'healthy'}>
          {error ? 'API à vérifier' : 'API gouvernée'}
        </StatusBadge>
      </header>
      <div className="core-layout">
        <aside className="core-map">
          <h2>Domaines du socle</h2>
          {domains.map((domain) => (
            <div className="core-domain" key={domain.name}>
              <span className="icon-tile">
                <Icon name={domain.icon} />
              </span>
              <span>
                <strong>{domain.name}</strong>
                <small>{domain.detail}</small>
              </span>
              <StatusBadge tone={domain.state === 'Configurable' ? 'healthy' : 'neutral'}>
                {domain.state}
              </StatusBadge>
            </div>
          ))}
        </aside>
        <section className="core-records">
          <header>
            <div>
              <span>Lecture directe · unité {getActiveUnitId()}</span>
              <h2>Référentiels actuels</h2>
            </div>
            {error && <StatusBadge tone="warning">{error}</StatusBadge>}
          </header>
          <div className="record-columns">
            <section>
              <h3>
                Clients <span>{clients.length}</span>
              </h3>
              {clients.length ? (
                clients.map((client) => (
                  <article key={client.id}>
                    <div>
                      <strong>{client.display_name}</strong>
                      <small>
                        {client.key} · {client.party_kind}
                      </small>
                    </div>
                    <StatusBadge tone={client.status === 'active' ? 'healthy' : 'neutral'}>
                      {client.status}
                    </StatusBadge>
                  </article>
                ))
              ) : (
                <p className="empty-copy">Aucun client visible dans ce périmètre.</p>
              )}
              <form
                className="review-decision-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  clientForm.onSubmit();
                }}
              >
                <h3>Créer un client</h3>
                <label>
                  <span>Type</span>
                  <select
                    value={clientForm.kind}
                    onChange={(event) => {
                      clientForm.onKindChange(event.target.value as 'organization' | 'person');
                    }}
                  >
                    <option value="organization">Organisation</option>
                    <option value="person">Personne</option>
                  </select>
                </label>
                <label>
                  <span>Clé stable</span>
                  <input
                    type="text"
                    value={clientForm.key}
                    placeholder="solar-client"
                    onChange={(event) => {
                      clientForm.onKeyChange(event.target.value);
                    }}
                  />
                </label>
                <label>
                  <span>Nom affiché</span>
                  <input
                    type="text"
                    value={clientForm.name}
                    placeholder="Solar Client SA"
                    onChange={(event) => {
                      clientForm.onNameChange(event.target.value);
                    }}
                  />
                </label>
                <button
                  className="signature-primary"
                  type="submit"
                  disabled={
                    clientForm.creation.phase === 'working' ||
                    !clientForm.key.trim() ||
                    !clientForm.name.trim()
                  }
                >
                  {clientForm.creation.phase === 'working' ? 'Création…' : 'Créer le client'}
                </button>
                <WriteFeedback state={clientForm.creation} />
              </form>
            </section>
            <section>
              <h3>
                Projets <span>{projects.length}</span>
              </h3>
              {projects.length ? (
                projects.map((project) => (
                  <article key={project.id}>
                    <div>
                      <strong>{project.name}</strong>
                      <small>
                        {project.key} · v{project.version}
                      </small>
                    </div>
                    <StatusBadge tone={project.status === 'active' ? 'healthy' : 'neutral'}>
                      {project.status}
                    </StatusBadge>
                  </article>
                ))
              ) : (
                <p className="empty-copy">Aucun projet visible dans ce périmètre.</p>
              )}
              <form
                className="review-decision-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  projectForm.onSubmit();
                }}
              >
                <h3>Créer un projet</h3>
                <label>
                  <span>Clé stable</span>
                  <input
                    type="text"
                    value={projectForm.key}
                    placeholder="audit-energie"
                    onChange={(event) => {
                      projectForm.onKeyChange(event.target.value);
                    }}
                  />
                </label>
                <label>
                  <span>Nom</span>
                  <input
                    type="text"
                    value={projectForm.name}
                    placeholder="Audit énergétique"
                    onChange={(event) => {
                      projectForm.onNameChange(event.target.value);
                    }}
                  />
                </label>
                <label>
                  <span>Client associé (optionnel)</span>
                  <select
                    value={projectForm.clientId}
                    onChange={(event) => {
                      projectForm.onClientChange(event.target.value);
                    }}
                  >
                    <option value="">Aucun</option>
                    {clients.map((client) => (
                      <option key={client.id} value={client.id}>
                        {client.display_name}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="signature-primary"
                  type="submit"
                  disabled={
                    projectForm.creation.phase === 'working' ||
                    !projectForm.key.trim() ||
                    !projectForm.name.trim()
                  }
                >
                  {projectForm.creation.phase === 'working' ? 'Création…' : 'Créer le projet'}
                </button>
                <WriteFeedback state={projectForm.creation} />
              </form>
            </section>
            <section>
              <h3>
                Employés <span>{employees.length}</span>
              </h3>
              {employees.length ? (
                employees.map((employee) => (
                  <article key={employee.id}>
                    <div>
                      <strong>
                        {employee.given_name} {employee.family_name}
                      </strong>
                      <small>
                        {employee.kind}
                        {employee.personnel_number ? ` · ${employee.personnel_number}` : ''}
                      </small>
                    </div>
                    <StatusBadge tone="healthy">{employee.kind}</StatusBadge>
                  </article>
                ))
              ) : (
                <p className="empty-copy">Aucun employé visible dans ce périmètre.</p>
              )}
              <form
                className="review-decision-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  employeeForm.onSubmit();
                }}
              >
                <h3>Rattacher un employé</h3>
                <label>
                  <span>Prénom</span>
                  <input
                    type="text"
                    value={employeeForm.givenName}
                    placeholder="Afi"
                    onChange={(event) => {
                      employeeForm.onGivenNameChange(event.target.value);
                    }}
                  />
                </label>
                <label>
                  <span>Nom</span>
                  <input
                    type="text"
                    value={employeeForm.familyName}
                    placeholder="Mensah"
                    onChange={(event) => {
                      employeeForm.onFamilyNameChange(event.target.value);
                    }}
                  />
                </label>
                <label>
                  <span>Matricule (optionnel)</span>
                  <input
                    type="text"
                    value={employeeForm.personnelNumber}
                    placeholder="EMP-42"
                    onChange={(event) => {
                      employeeForm.onPersonnelNumberChange(event.target.value);
                    }}
                  />
                </label>
                <button
                  className="signature-primary"
                  type="submit"
                  disabled={
                    employeeForm.creation.phase === 'working' ||
                    !employeeForm.givenName.trim() ||
                    !employeeForm.familyName.trim()
                  }
                >
                  {employeeForm.creation.phase === 'working'
                    ? 'Enregistrement…'
                    : 'Rattacher l’employé'}
                </button>
                <WriteFeedback state={employeeForm.creation} />
              </form>
            </section>
          </div>
        </section>
        <aside className="core-boundary">
          <Icon name="governance" />
          <h2>Frontière d’autorité</h2>
          <p>Chaque domaine déclare son système de référence et ses contrats d’échange.</p>
          <dl>
            <div>
              <dt>Identités & accès</dt>
              <dd>Neon Auth + autorisation KYA</dd>
            </div>
            <div>
              <dt>Secrets</dt>
              <dd>Références Infisical, jamais les valeurs</dd>
            </div>
            <div>
              <dt>Documents lourds</dt>
              <dd>Neon Storage, métadonnées dans Core</dd>
            </div>
            <div>
              <dt>Frappe</dt>
              <dd>Adaptateur futur, pas dépendance du noyau</dd>
            </div>
          </dl>
        </aside>
      </div>
    </section>
  );
}

export function CoreAdministration() {
  const [clients, setClients] = useState<Client[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [error, setError] = useState('');

  const [clientCreation, setClientCreation] = useState<WriteState>({ phase: 'idle' });
  const [clientKey, setClientKey] = useState('');
  const [clientName, setClientName] = useState('');
  const [clientKind, setClientKind] = useState<'organization' | 'person'>('organization');

  const [projectCreation, setProjectCreation] = useState<WriteState>({ phase: 'idle' });
  const [projectKey, setProjectKey] = useState('');
  const [projectName, setProjectName] = useState('');
  const [projectClientId, setProjectClientId] = useState('');

  const [employeeCreation, setEmployeeCreation] = useState<WriteState>({ phase: 'idle' });
  const [employeeGivenName, setEmployeeGivenName] = useState('');
  const [employeeFamilyName, setEmployeeFamilyName] = useState('');
  const [employeeNumber, setEmployeeNumber] = useState('');

  function reload() {
    const unitKey = getActiveUnitId();
    return Promise.all([
      platformRequest<List<Client>>(`/core/organization/${unitKey}/clients`),
      platformRequest<List<Project>>(`/core/organization/${unitKey}/projects`),
      platformRequest<List<Employee>>(`/core/organization/${unitKey}/employees`),
    ]).then(([clientList, projectList, employeeList]) => {
      setClients(clientList.items);
      setProjects(projectList.items);
      setEmployees(employeeList.items);
    });
  }

  useEffect(() => {
    let active = true;
    reload().catch((failure: unknown) => {
      if (active) setError(failure instanceof Error ? failure.message : 'KYA Core indisponible.');
    });
   return () => {
     active = false;
   };
 }, []);

  function submitClient() {
    if (!clientKey.trim() || !clientName.trim()) return;
    setClientCreation({ phase: 'working' });
    const unitKey = getActiveUnitId();
    void platformRequest<Client>(`/core/organization/${unitKey}/clients`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey('core-client-create'),
      },
      body: JSON.stringify({
        key: clientKey.trim(),
        party_kind: clientKind,
        display_name: clientName.trim(),
        valid_from: new Date().toISOString(),
      }),
    })
      .then(() => reload())
      .then(() => {
        setClientKey('');
        setClientName('');
        setClientCreation({
          phase: 'success',
          message: 'Le client a été enregistré dans KYA Core.',
        });
      })
      .catch((failure: unknown) => {
        setClientCreation({
          phase: 'error',
          message: failure instanceof Error ? failure.message : 'La création a échoué.',
        });
      });
  }

  function submitProject() {
    if (!projectKey.trim() || !projectName.trim()) return;
    setProjectCreation({ phase: 'working' });
    const unitKey = getActiveUnitId();
    void platformRequest<Project>(`/core/organization/${unitKey}/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey('core-project-create'),
      },
      body: JSON.stringify({
        key: projectKey.trim(),
        name: projectName.trim(),
        client_id: projectClientId || null,
        valid_from: new Date().toISOString(),
      }),
    })
      .then(() => reload())
      .then(() => {
        setProjectKey('');
        setProjectName('');
        setProjectClientId('');
        setProjectCreation({
          phase: 'success',
          message: 'Le projet a été enregistré dans KYA Core.',
        });
      })
      .catch((failure: unknown) => {
        setProjectCreation({
          phase: 'error',
          message: failure instanceof Error ? failure.message : 'La création a échoué.',
        });
      });
  }

  function submitEmployee() {
    if (!employeeGivenName.trim() || !employeeFamilyName.trim()) return;
    setEmployeeCreation({ phase: 'working' });
    const unitKey = getActiveUnitId();
    void platformRequest<Employee>(`/core/organization/${unitKey}/employees`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey('core-employee-create'),
      },
      body: JSON.stringify({
        given_name: employeeGivenName.trim(),
        family_name: employeeFamilyName.trim(),
        personnel_number: employeeNumber.trim() || null,
        valid_from: new Date().toISOString(),
      }),
    })
      .then(() => reload())
      .then(() => {
        setEmployeeGivenName('');
        setEmployeeFamilyName('');
        setEmployeeNumber('');
        setEmployeeCreation({
          phase: 'success',
          message: 'L’employé a été rattaché à l’unité active dans KYA Core.',
        });
      })
      .catch((failure: unknown) => {
        setEmployeeCreation({
          phase: 'error',
          message: failure instanceof Error ? failure.message : 'La création a échoué.',
        });
      });
  }

  return (
    <CoreAdministrationView
      clients={clients}
      projects={projects}
      employees={employees}
      error={error}
      clientForm={{
        creation: clientCreation,
        key: clientKey,
        name: clientName,
        kind: clientKind,
        onKeyChange: setClientKey,
        onNameChange: setClientName,
        onKindChange: setClientKind,
        onSubmit: submitClient,
      }}
      projectForm={{
        creation: projectCreation,
        key: projectKey,
        name: projectName,
        clientId: projectClientId,
        onKeyChange: setProjectKey,
        onNameChange: setProjectName,
        onClientChange: setProjectClientId,
        onSubmit: submitProject,
      }}
      employeeForm={{
        creation: employeeCreation,
        givenName: employeeGivenName,
        familyName: employeeFamilyName,
        personnelNumber: employeeNumber,
        onGivenNameChange: setEmployeeGivenName,
        onFamilyNameChange: setEmployeeFamilyName,
        onPersonnelNumberChange: setEmployeeNumber,
        onSubmit: submitEmployee,
      }}
    />
  );
}
