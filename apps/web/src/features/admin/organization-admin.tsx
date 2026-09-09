import { useEffect, useState } from 'react';
import { Icon, StatusBadge } from '@kya/design-system';
import { platformRequest } from '../../platform/api';

type Unit = {
  id: string;
  key: string;
  type_key: string;
  name: string;
  valid_from: string;
  valid_until: string | null;
};
type List<T> = { items: T[] };

export function OrganizationAdmin() {
  const [root, setRoot] = useState<Unit | null>(null);
  const [children, setChildren] = useState<Unit[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    void Promise.all([
      platformRequest<Unit>('/core/organization/group'),
      platformRequest<List<Unit>>('/core/organization/group/children'),
    ])
      .then(([unit, list]) => {
        if (active) {
          setRoot(unit);
          setChildren(list.items);
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
                    {root.type_key} · {root.key}
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
                          {unit.type_key} · {unit.key}
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
              <span>Modèle temporel</span>
              <h2>Affectations historisées</h2>
            </div>
            <StatusBadge tone="healthy">Principe actif</StatusBadge>
          </header>
          <div className="timeline-example">
            <span className="timeline-line" />
            <article>
              <time>Avant</time>
              <strong>Ancienne affectation</strong>
              <small>Conservée pour l’audit</small>
            </article>
            <article className="current">
              <time>Maintenant</time>
              <strong>Rôle dans l’unité active</strong>
              <small>Droits calculés dans le contexte</small>
            </article>
            <article>
              <time>Après</time>
              <strong>Fin ou nouvelle affectation</strong>
              <small>Transition sans réécriture du passé</small>
            </article>
          </div>
          <div className="principle-note">
            <Icon name="shield" />
            <p>
              <strong>Le poste n’est pas le rôle d’accès.</strong> Une personne occupe un poste
              pendant une période ; les permissions découlent ensuite de règles explicites et
              vérifiables.
            </p>
          </div>
        </section>
        <aside className="inheritance-panel">
          <h2>Calcul des droits</h2>
          <ol>
            <li>
              <span>1</span>
              <div>
                <strong>Identité</strong>
                <small>Qui agit ?</small>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <strong>Contexte</strong>
                <small>Dans quelle unité ?</small>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <strong>Rôle</strong>
                <small>Quel mandat actif ?</small>
              </div>
            </li>
            <li>
              <span>4</span>
              <div>
                <strong>Objet</strong>
                <small>Sur quelle ressource ?</small>
              </div>
            </li>
          </ol>
          <p>Une interdiction explicite reste prioritaire sur l’héritage.</p>
        </aside>
      </div>
    </section>
  );
}
