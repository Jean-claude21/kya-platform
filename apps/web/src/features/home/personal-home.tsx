import { useState } from 'react';
import { Icon } from '@kya/design-system';
import type { IconName } from '@kya/design-system';
import type { Module } from '../../screens/platform-shell';

const capabilities: Array<{
  name: string;
  type: string;
  detail: string;
  icon: IconName;
  target: Module;
  action: string;
}> = [
  {
    name: 'KYA Design System',
    type: 'Skill',
    detail: 'Charte, composants et médias',
    icon: 'skill',
    target: 'Studio',
    action: 'Consulter',
  },
  {
    name: 'KYA-Platform MCP',
    type: 'MCP',
    detail: 'Outils et profils gouvernés',
    icon: 'network',
    target: 'MCP',
    action: 'Configurer',
  },
  {
    name: 'Applications',
    type: 'App',
    detail: 'Répertoire des systèmes métier',
    icon: 'apps',
    target: 'Apps',
    action: 'Explorer',
  },
  {
    name: 'Méthodes KYA',
    type: 'Skill',
    detail: 'Catalogue des méthodes partagées',
    icon: 'file',
    target: 'Skills',
    action: 'Explorer',
  },
  {
    name: 'Référentiels Core',
    type: 'Données',
    detail: 'Clients, projets et unités',
    icon: 'database',
    target: 'Core',
    action: 'Consulter',
  },
];

export function PersonalHome({
  onNavigate,
  unit,
  query,
  preview,
}: {
  onNavigate: (target: Module) => void;
  unit: string;
  query: string;
  preview: boolean;
}) {
  const [filter, setFilter] = useState('Tout');
  const items = capabilities.filter(
    (item) =>
      (filter === 'Tout' || filter === item.type) &&
      (item.name + ' ' + item.detail)
        .toLocaleLowerCase('fr')
        .includes(query.toLocaleLowerCase('fr').trim()),
  );
  return (
    <main className="signature-home">
      <section className="signature-hero" aria-labelledby="home-title">
        <img src="/images/solar-panorama.webp" alt="" width="2172" height="724" />
        <div>
          <h1 id="home-title">Mon espace</h1>
          <p>Vos capacités. Vos équipes. Vos outils.</p>
          <span>{unit}</span>
          <div className="signature-stripe" aria-hidden="true">
            <b />
            <b />
            <b />
          </div>
        </div>
      </section>
      <div className="signature-workspace">
        <section className="signature-capabilities" aria-labelledby="capabilities-title">
          <header>
            <h2 id="capabilities-title">Mes capacités</h2>
            <button
              className="signature-text"
              type="button"
              onClick={() => {
                onNavigate('Catalogue');
              }}
            >
              Catalogue <Icon name="chevron" />
            </button>
          </header>
          <div className="signature-tabs" aria-label="Type de capacité">
            {['Tout', 'App', 'MCP', 'Skill', 'Données'].map((kind) => (
              <button
                type="button"
                key={kind}
                aria-pressed={kind === filter}
                onClick={() => {
                  setFilter(kind);
                }}
              >
                {kind === 'App' ? 'Apps' : kind === 'Skill' ? 'Skills' : kind}
              </button>
            ))}
          </div>
          <div className="signature-resources">
            {items.map((item) => (
              <div className="signature-resource" key={item.name}>
                <button
                  className="signature-resource-main"
                  type="button"
                  onClick={() => {
                    onNavigate(item.target);
                  }}
                >
                  <Icon name={item.icon} />
                  <span>
                    <strong>{item.name}</strong>
                    <small>
                      {item.type} · {item.detail}
                    </small>
                  </span>
                </button>
                <span className="signature-resource-state">
                  {item.target === 'Studio' ? 'Paquet local' : 'Accès à vérifier'}
                </span>
                <button
                  className="signature-outline"
                  type="button"
                  onClick={() => {
                    onNavigate(item.target);
                  }}
                >
                  {item.action}
                  <Icon name="chevron" />
                </button>
              </div>
            ))}
            {!items.length && (
              <p className="signature-empty" role="status">
                Aucun raccourci ne correspond. Modifiez la recherche ou le type.
              </p>
            )}
          </div>
          <section className="signature-shortcuts">
            <h3>Accès rapides</h3>
            <div>
              <button
                type="button"
                onClick={() => {
                  onNavigate('Espaces');
                }}
              >
                Mes espaces
                <Icon name="chevron" />
              </button>
              <button
                type="button"
                onClick={() => {
                  onNavigate('Studio');
                }}
              >
                Design System
                <Icon name="chevron" />
              </button>
              <button
                type="button"
                onClick={() => {
                  onNavigate('MCP');
                }}
              >
                KYA-Platform MCP
                <Icon name="chevron" />
              </button>
            </div>
          </section>
        </section>
        <aside className="signature-rail">
          <section>
            <h2>À traiter</h2>
            <article className="signature-request">
              <div>
                <h3>KYA Design System</h3>
                <p>Paquet local prêt pour revue</p>
              </div>
              <button
                className="signature-text"
                type="button"
                onClick={() => {
                  onNavigate('Studio');
                }}
              >
                Examiner
                <Icon name="chevron" />
              </button>
            </article>
            <article className="signature-request">
              <div>
                <h3>Publications & accès</h3>
                <p>Consulter les parcours de validation</p>
              </div>
              <button
                className="signature-text"
                type="button"
                onClick={() => {
                  onNavigate('Publications');
                }}
              >
                Ouvrir
                <Icon name="chevron" />
              </button>
            </article>
            <p className="signature-note">
              Raccourcis de travail, pas une boîte de demandes en temps réel.
            </p>
          </section>
          <section className="signature-connections">
            <h2>Mes connexions</h2>
            <p>Travaillez depuis votre environnement IA.</p>
            <div>
              {['Claude', 'ChatGPT', 'Codex'].map((client) => (
                <button
                  type="button"
                  key={client}
                  className="signature-client"
                  onClick={() => {
                    onNavigate('MCP');
                  }}
                >
                  <Icon name={client === 'Codex' ? 'code' : 'network'} />
                  <strong>{client}</strong>
                  <span>Vérifier le profil</span>
                  <Icon name="chevron" />
                </button>
              ))}
            </div>
            <button
              className="signature-primary"
              type="button"
              onClick={() => {
                onNavigate('MCP');
              }}
            >
              Gérer mes connexions
            </button>
          </section>
        </aside>
      </div>
      <footer className="signature-footer">
        {preview ? 'Aperçu local · contexte illustratif · ' : ''}Raccourcis vers les fonctions
        existantes · autorisations vérifiées à l’ouverture · visuel illustratif généré
      </footer>
    </main>
  );
}
