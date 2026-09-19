import { useEffect, useState } from 'react';
import { Icon, StatusBadge } from '@kya/design-system';
import { platformRequest, idempotencyKey } from '../../platform/api';
import { getActiveUnitId } from '../../platform/active-context';
import { organizationalUnitTypeLabel } from '../../platform/organizational-units';

export type Unit = {
  id: string;
  key: string;
  type_key: string;
  name: string;
  valid_from: string;
  valid_until: string | null;
};
type List<T> = { items: T[] };
export type UnitType = {
  key: string;
  label: string;
  allowed_parent_types: string[];
  is_temporary: boolean;
};

export type CreateUnitState =
  | { phase: 'idle' }
  | { phase: 'working' }
  | { phase: 'success'; message: string }
  | { phase: 'error'; message: string };

export function OrganizationAdminView({
  root,
  children,
  unitTypes,
  error,
  creation,
  newKey,
  newName,
  newTypeKey,
  onKeyChange,
  onNameChange,
  onTypeChange,
  onSubmit,
}: {
  root: Unit | null;
  children: Unit[];
  unitTypes: UnitType[];
  error: string;
  creation: CreateUnitState;
  newKey: string;
  newName: string;
  newTypeKey: string;
  onKeyChange: (value: string) => void;
  onNameChange: (value: string) => void;
  onTypeChange: (value: string) => void;
  onSubmit: () => void;
}) {
  const labels = new Map(unitTypes.map((type) => [type.key, type.label]));
  const typeLabel = (key: string) => labels.get(key) ?? organizationalUnitTypeLabel(key);

  return (
    <section className="admin-detail-page" aria-labelledby="organization-title">
      <header className="page-lead">
        <div>
          <span className="eyebrow">KYA Core · organisation canonique</span>
          <h1 id="organization-title">Organisation & responsabilités</h1>
          <p>Représenter une organisation mouvante sans écraser son histoire.</p>
        </div>
        <StatusBadge tone={error ? 'warning' : root ? 'healthy' : 'neutral'}>
          {error ? 'Lecture limitée' : root ? 'Données réelles' : 'Chargement'}
        </StatusBadge>
      </header>
      <div className="organization-layout">
        <aside className="org-tree">
          <h2>Structure active</h2>
          {root ? (
            <>
              <button className="org-node org-node--root" type="button">
                <Icon name="home" />
                <span>
                  <strong>{root.name}</strong>
                  <small>
                    {typeLabel(root.type_key)} · {root.key}
                  </small>
                </span>
              </button>
              <div className="org-children">
                {children.length ? (
                  children.map((unit) => (
                    <button className="org-node" key={unit.id} type="button">
                      <Icon name="people" />
                      <span>
                        <strong>{unit.name}</strong>
                        <small>
                          {typeLabel(unit.type_key)} · {unit.key}
                        </small>
                      </span>
                    </button>
                  ))
                ) : (
                  <p>Aucune unité fille active.</p>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state compact">
              <Icon name="database" />
              <p>{error || 'Chargement de la structure…'}</p>
            </div>
          )}
        </aside>
        <section className="assignment-panel">
          <header>
            <div>
              <span>Configuration issue de KYA Core</span>
              <h2>Taxonomie organisationnelle</h2>
            </div>
            <StatusBadge tone={unitTypes.length ? 'healthy' : 'neutral'}>
              {unitTypes.length} types actifs
            </StatusBadge>
          </header>
          <div className="taxonomy-list">
            {unitTypes.map((type) => (
              <article key={type.key}>
                <div>
                  <strong>{type.label}</strong>
                  <small>
                    Clé stable : {type.key} · {type.is_temporary ? 'temporaire' : 'permanent'}
                  </small>
                </div>
                <span>
                  {type.allowed_parent_types.length
                    ? `Sous ${type.allowed_parent_types.map(typeLabel).join(', ')}`
                    : 'Racine'}
                </span>
              </article>
            ))}
          </div>
          <div className="principle-note">
            <Icon name="shield" />
            <p>
              <strong>« Filiale » est le libellé gouverné de la clé stable `entity`.</strong> Une
              agence relève d’une filiale sur le plan opérationnel ; son pays reste une propriété
              géographique indépendante.
            </p>
          </div>
        </section>
        <aside className="core-create-panel">
          <h2>Créer une unité fille</h2>
          <p>Rattachée à l’unité active, avec une validité qui démarre aujourd’hui.</p>
          <form
            className="review-decision-form"
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit();
            }}
          >
            <label>
              <span>Type d’unité</span>
              <select
                value={newTypeKey}
                onChange={(event) => {
                  onTypeChange(event.target.value);
                }}
                disabled={unitTypes.length === 0}
              >
                {unitTypes.map((type) => (
                  <option key={type.key} value={type.key}>
                    {type.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Clé stable</span>
              <input
                type="text"
                value={newKey}
                placeholder="agence-lome"
                onChange={(event) => {
                  onKeyChange(event.target.value);
                }}
              />
            </label>
            <label>
              <span>Nom</span>
              <input
                type="text"
                value={newName}
                placeholder="Agence Lomé"
                onChange={(event) => {
                  onNameChange(event.target.value);
                }}
              />
            </label>
            <button
              className="signature-primary"
              type="submit"
              disabled={creation.phase === 'working' || !newKey.trim() || !newName.trim()}
            >
              {creation.phase === 'working' ? 'Création…' : 'Créer l’unité'}
            </button>
            {creation.phase === 'success' && (
              <p className="review-duty-warning" data-override="false" role="status">
                {creation.message}
              </p>
            )}
            {creation.phase === 'error' && (
              <p className="review-duty-warning" data-override="true" role="alert">
                {creation.message}
              </p>
            )}
          </form>
        </aside>
      </div>
    </section>
  );
}

export function OrganizationAdmin() {
  const [root, setRoot] = useState<Unit | null>(null);
  const [children, setChildren] = useState<Unit[]>([]);
  const [unitTypes, setUnitTypes] = useState<UnitType[]>([]);
  const [error, setError] = useState('');
  const [creation, setCreation] = useState<CreateUnitState>({ phase: 'idle' });
  const [newKey, setNewKey] = useState('');
  const [newName, setNewName] = useState('');
  const [newTypeKey, setNewTypeKey] = useState('');

  function reload() {
    const unitKey = getActiveUnitId();
    return Promise.all([
      platformRequest<Unit>(`/core/organization/${unitKey}`),
      platformRequest<List<Unit>>(`/core/organization/${unitKey}/children`),
      platformRequest<List<UnitType>>(`/core/organization/${unitKey}/unit-types`),
    ]).then(([unit, list, types]) => {
      setRoot(unit);
      setChildren(list.items);
      setUnitTypes(types.items);
      setNewTypeKey((current) => current || (types.items[0]?.key ?? ''));
    });
  }

  useEffect(() => {
    let active = true;
    reload().catch((failure: unknown) => {
      if (active)
        setError(failure instanceof Error ? failure.message : 'Organisation indisponible.');
    });
    return () => {
      active = false;
    };
  }, []);

  function submit() {
    if (!newKey.trim() || !newName.trim() || !newTypeKey.trim()) return;
    setCreation({ phase: 'working' });
    const unitKey = getActiveUnitId();
    void platformRequest<Unit>(`/core/organization/${unitKey}/children`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey('core-unit-create'),
      },
      body: JSON.stringify({
        key: newKey.trim(),
        type_key: newTypeKey,
        name: newName.trim(),
        valid_from: new Date().toISOString(),
      }),
    })
      .then(() => reload())
      .then(() => {
        setNewKey('');
        setNewName('');
        setCreation({
          phase: 'success',
          message: 'La nouvelle unité a été enregistrée dans KYA Core.',
        });
      })
      .catch((failure: unknown) => {
        setCreation({
          phase: 'error',
          message: failure instanceof Error ? failure.message : 'La création a échoué.',
        });
      });
  }

  return (
    <OrganizationAdminView
      root={root}
      children={children}
      unitTypes={unitTypes}
      error={error}
      creation={creation}
      newKey={newKey}
      newName={newName}
      newTypeKey={newTypeKey}
      onKeyChange={setNewKey}
      onNameChange={setNewName}
      onTypeChange={setNewTypeKey}
      onSubmit={submit}
    />
  );
}
