import { useEffect, useState } from 'react';
import { Icon, StatusBadge } from '@kya/design-system';
import { platformRequest } from '../../platform/api';
import { getActiveUnitId } from '../../platform/active-context';
import { organizationalUnitTypeLabel } from '../../platform/organizational-units';

type Unit = {
  id: string;
  key: string;
  type_key: string;
  name: string;
  valid_from: string;
  valid_until: string | null;
};
type List<T> = { items: T[] };
type UnitType = {
  key: string;
  label: string;
  allowed_parent_types: string[];
  is_temporary: boolean;
};

export function OrganizationAdmin() {
  const [root, setRoot] = useState<Unit | null>(null);
  const [children, setChildren] = useState<Unit[]>([]);
  const [unitTypes, setUnitTypes] = useState<UnitType[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    const unitKey = getActiveUnitId();
    void Promise.all([
      platformRequest<Unit>(`/core/organization/${unitKey}`),
      platformRequest<List<Unit>>(`/core/organization/${unitKey}/children`),
      platformRequest<List<UnitType>>(`/core/organization/${unitKey}/unit-types`),
    ])
      .then(([unit, list, types]) => {
        if (active) {
          setRoot(unit);
          setChildren(list.items);
          setUnitTypes(types.items);
        }
      })
      .catch((failure: unknown) => {
        if (active)
          setError(failure instanceof Error ? failure.message : 'Organisation indisponible.');
      });
    return () => {
      active = false;
    };
  }, []);
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
        <aside className="inheritance-panel">
          <h2>Dimensions séparées</h2>
          <ol>
            <li>
              <span>1</span>
              <div>
                <strong>Groupe</strong>
                <small>Sommet institutionnel</small>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <strong>Filiale</strong>
                <small>Autorité juridique ou opérationnelle</small>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <strong>Agence</strong>
                <small>Unité locale rattachée à une filiale</small>
              </div>
            </li>
            <li>
              <span>4</span>
              <div>
                <strong>Pays</strong>
                <small>Localisation, distincte du propriétaire</small>
              </div>
            </li>
          </ol>
          <p>Les relations sont datées : un rattachement change sans effacer le passé.</p>
        </aside>
      </div>
    </section>
  );
}
