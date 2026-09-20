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

export type TreeNode = {
  unit: Unit;
  children: TreeNode[];
};

function TreeBranch({
  node,
  depth,
  selectedKey,
  viewedKey,
  typeLabel,
  onSelect,
  onView,
}: {
  node: TreeNode;
  depth: number;
  selectedKey: string;
  viewedKey: string;
  typeLabel: (key: string) => string;
  onSelect: (unit: Unit) => void;
  onView: (unit: Unit) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.children.length > 0;
  return (
    <div className="org-branch" style={{ marginLeft: depth ? 12 : 0 }}>
      <div
        className={
          'org-node' +
          (node.unit.key === viewedKey ? ' org-node--active' : '') +
          (node.unit.key === selectedKey ? ' org-node--selected' : '')
        }
      >
        {hasChildren ? (
          <button
            type="button"
            className="org-node__toggle"
            aria-label={expanded ? 'Réduire' : 'Développer'}
            onClick={() => {
              setExpanded((value) => !value);
            }}
          >
            <Icon name="chevron" />
          </button>
        ) : (
          <span className="org-node__toggle org-node__toggle--spacer" aria-hidden="true" />
        )}
        <button
          type="button"
          className="org-node__label"
          onClick={() => {
            onView(node.unit);
          }}
        >
          <Icon name={depth === 0 ? 'home' : 'people'} />
          <span>
            <strong>{node.unit.name}</strong>
            <small>
              {typeLabel(node.unit.type_key)} · {node.unit.key}
            </small>
          </span>
        </button>
        <button
          type="button"
          className="org-node__pick"
          onClick={() => {
            onSelect(node.unit);
          }}
        >
          {node.unit.key === selectedKey ? 'Parent choisi' : 'Choisir comme parent'}
        </button>
      </div>
      {hasChildren && expanded ? (
        <div className="org-children">
          {node.children.map((child) => (
            <TreeBranch
              key={child.unit.id}
              node={child}
              depth={depth + 1}
              selectedKey={selectedKey}
              viewedKey={viewedKey}
              typeLabel={typeLabel}
              onSelect={onSelect}
              onView={onView}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function OrganizationAdminView({
  tree,
  viewed,
  viewedChildren,
  unitTypes,
  error,
  creation,
  newKey,
  newName,
  newTypeKey,
  parentUnit,
  onKeyChange,
  onNameChange,
  onTypeChange,
  onParentSelect,
  onView,
  onSubmit,
}: {
  tree: TreeNode | null;
  viewed: Unit | null;
  viewedChildren: Unit[];
  unitTypes: UnitType[];
  error: string;
  creation: CreateUnitState;
  newKey: string;
  newName: string;
  newTypeKey: string;
  parentUnit: Unit | null;
  onKeyChange: (value: string) => void;
  onNameChange: (value: string) => void;
  onTypeChange: (value: string) => void;
  onParentSelect: (unit: Unit) => void;
  onView: (unit: Unit) => void;
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
        <StatusBadge tone={error ? 'warning' : tree ? 'healthy' : 'neutral'}>
          {error ? 'Lecture limitée' : tree ? 'Données réelles' : 'Chargement'}
        </StatusBadge>
      </header>
      <div className="organization-layout">
        <aside className="org-tree">
          <h2>Arborescence complète</h2>
          <p className="org-tree-hint">
            Cliquez un nœud pour l’examiner, ou « Choisir comme parent » pour rattacher une nouvelle
            unité ailleurs que sous l’unité active.
          </p>
          {tree ? (
            <TreeBranch
              node={tree}
              depth={0}
              selectedKey={parentUnit?.key ?? ''}
              viewedKey={viewed?.key ?? ''}
              typeLabel={typeLabel}
              onSelect={onParentSelect}
              onView={onView}
            />
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
              <span>Unité examinée</span>
              <h2>{viewed ? viewed.name : 'Sélectionnez un nœud'}</h2>
            </div>
            <StatusBadge tone={unitTypes.length ? 'healthy' : 'neutral'}>
              {unitTypes.length} types actifs
            </StatusBadge>
          </header>
          {viewed ? (
            <div className="viewed-unit-summary">
              <dl>
                <div>
                  <dt>Clé stable</dt>
                  <dd>{viewed.key}</dd>
                </div>
                <div>
                  <dt>Type</dt>
                  <dd>{typeLabel(viewed.type_key)}</dd>
                </div>
                <div>
                  <dt>Validité</dt>
                  <dd>
                    depuis {new Date(viewed.valid_from).toLocaleDateString('fr-FR')}
                    {viewed.valid_until
                      ? ` jusqu’au ${new Date(viewed.valid_until).toLocaleDateString('fr-FR')}`
                      : ''}
                  </dd>
                </div>
              </dl>
              <h3>Unités filles directes ({viewedChildren.length})</h3>
              {viewedChildren.length ? (
                <ul className="viewed-children-list">
                  {viewedChildren.map((unit) => (
                    <li key={unit.id}>
                      <strong>{unit.name}</strong>
                      <small>
                        {typeLabel(unit.type_key)} · {unit.key}
                      </small>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="empty-copy">Aucune unité fille directe.</p>
              )}
            </div>
          ) : null}
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
          <p>
            Rattachée à <strong>{parentUnit ? parentUnit.name : 'l’unité active'}</strong>
            {parentUnit ? ` (${parentUnit.key})` : ''}, avec une validité qui démarre aujourd’hui.
          </p>
          <form
            className="review-decision-form"
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit();
            }}
          >
            <label>
              <span>Unité parente</span>
              <input
                type="text"
                value={parentUnit ? `${parentUnit.name} (${parentUnit.key})` : 'Unité active'}
                readOnly
              />
            </label>
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
  const [tree, setTree] = useState<TreeNode | null>(null);
  const [viewed, setViewed] = useState<Unit | null>(null);
  const [viewedChildren, setViewedChildren] = useState<Unit[]>([]);
  const [parentUnit, setParentUnit] = useState<Unit | null>(null);
  const [unitTypes, setUnitTypes] = useState<UnitType[]>([]);
  const [error, setError] = useState('');
  const [creation, setCreation] = useState<CreateUnitState>({ phase: 'idle' });
  const [newKey, setNewKey] = useState('');
  const [newName, setNewName] = useState('');
  const [newTypeKey, setNewTypeKey] = useState('');

  async function loadChildrenOf(unit: Unit): Promise<Unit[]> {
    const list = await platformRequest<List<Unit>>(`/core/organization/${unit.key}/children`);
    return list.items;
  }

  async function buildTree(rootKey: string): Promise<{ node: TreeNode; byKey: Map<string, Unit> }> {
    const byKey = new Map<string, Unit>();
    const root = await platformRequest<Unit>(`/core/organization/${rootKey}`);
    byKey.set(root.key, root);

    async function expand(unit: Unit, depth: number): Promise<TreeNode> {
      const kids = depth < 6 ? await loadChildrenOf(unit) : [];
      kids.forEach((kid) => byKey.set(kid.key, kid));
      const childNodes = await Promise.all(kids.map((kid) => expand(kid, depth + 1)));
      return { unit, children: childNodes };
    }

    const node = await expand(root, 0);
    return { node, byKey };
  }

  function reload() {
    const activeKey = getActiveUnitId();
    // The tree is always rooted at "group" so any unit can be picked as a parent,
    // not only children of the currently active unit.
    return Promise.all([
      buildTree('group'),
      platformRequest<List<UnitType>>(`/core/organization/${activeKey}/unit-types`),
    ]).then(([{ node, byKey }, types]) => {
      setTree(node);
      setUnitTypes(types.items);
      setNewTypeKey((current) => current || (types.items[0]?.key ?? ''));
      const active = byKey.get(activeKey) ?? node.unit;
      setViewed((current) => current ?? active);
      setParentUnit((current) => current ?? active);
      return loadChildrenOf(active).then((kids) => {
        setViewedChildren((current) => current);
        setViewedChildren(kids);
      });
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

  function view(unit: Unit) {
    setViewed(unit);
    void loadChildrenOf(unit)
      .then(setViewedChildren)
      .catch(() => {
        setViewedChildren([]);
      });
  }

  function submit() {
    if (!newKey.trim() || !newName.trim() || !newTypeKey.trim()) return;
    setCreation({ phase: 'working' });
    const unitKey = parentUnit?.key ?? getActiveUnitId();
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
      tree={tree}
      viewed={viewed}
      viewedChildren={viewedChildren}
      unitTypes={unitTypes}
      error={error}
      creation={creation}
      newKey={newKey}
      newName={newName}
      newTypeKey={newTypeKey}
      parentUnit={parentUnit}
      onKeyChange={setNewKey}
      onNameChange={setNewName}
      onTypeChange={setNewTypeKey}
      onParentSelect={setParentUnit}
      onView={view}
      onSubmit={submit}
    />
  );
}
