import { useEffect, useState } from 'react';
import { Icon, StatusBadge } from '@kya/design-system';
import { platformRequest } from '../../platform/api';
import { organizationalUnitTypeLabel } from '../../platform/organizational-units';

type Client = {
  id: string;
  key: string;
  display_name: string;
  party_kind: string;
  status: string;
  version: number;
};
type Project = { id: string; key: string; name: string; status: string; version: number };
type List<T> = { items: T[] };

const domains = [
  {
    name: 'Organisation',
    detail: 'Unités et validité temporelle',
    icon: 'people' as const,
    state: 'Exposé',
  },
  {
    name: 'Parties & clients',
    detail: 'Identités métier partagées',
    icon: 'user' as const,
    state: 'Exposé',
  },
  { name: 'Projets', detail: 'Références transversales', icon: 'folder' as const, state: 'Exposé' },
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

export function CoreAdministration() {
  const [clients, setClients] = useState<Client[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    void Promise.all([
      platformRequest<List<Client>>('/core/organization/group/clients'),
      platformRequest<List<Project>>('/core/organization/group/projects'),
    ])
      .then(([clientList, projectList]) => {
        if (active) {
          setClients(clientList.items);
          setProjects(projectList.items);
        }
      })
      .catch((failure: unknown) => {
        if (active) setError(failure instanceof Error ? failure.message : 'KYA Core indisponible.');
      });
    return () => {
      active = false;
    };
  }, []);
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
              <StatusBadge tone={domain.state === 'Exposé' ? 'healthy' : 'neutral'}>
                {domain.state}
              </StatusBadge>
            </div>
          ))}
        </aside>
        <section className="core-records">
          <header>
            <div>
              <span>Lecture directe · unité {organizationalUnitTypeLabel('group')}</span>
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
