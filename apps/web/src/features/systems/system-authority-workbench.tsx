import { Icon, StatusBadge } from '@kya/design-system';

const authorities = [
  {
    category: 'Métadonnées des artefacts',
    scope: 'Groupe KYA',
    system: 'KYA-Platform',
    since: '5 sept. 2026',
    sensitivity: 'Interne',
  },
] as const;

export function SystemAuthorityWorkbench() {
  return (
    <main className="systems-page">
      <section className="systems-intro" aria-labelledby="systems-title">
        <div>
          <h1 id="systems-title">Où se trouve la donnée qui fait foi ?</h1>
          <p>
            Chaque domaine partagé possède une autorité explicite, une période, un périmètre et des
            interfaces approuvées.
          </p>
        </div>
        <StatusBadge tone="healthy">1 autorité vérifiée</StatusBadge>
      </section>

      <aside className="system-list" aria-labelledby="system-list-title">
        <header>
          <h2 id="system-list-title">Systèmes enregistrés</h2>
          <span>1</span>
        </header>
        <button aria-current="true" type="button">
          <Icon name="database" />
          <span>
            <strong>KYA-Platform</strong>
            <small>Interne · preview</small>
          </span>
          <StatusBadge tone="healthy">Actif</StatusBadge>
        </button>
      </aside>

      <section className="system-detail" aria-labelledby="system-detail-title">
        <header>
          <div>
            <span>Système de gouvernance numérique</span>
            <h2 id="system-detail-title">KYA-Platform</h2>
            <p>
              Premier système enregistré avec une responsabilité volontairement limitée à ses
              propres données.
            </p>
          </div>
          <StatusBadge tone="healthy">Disponible en continu</StatusBadge>
        </header>

        <div className="system-facts">
          <article>
            <Icon name="people" />
            <span>
              <small>Propriétaire métier</small>
              <strong>CVSI</strong>
            </span>
          </article>
          <article>
            <Icon name="governance" />
            <span>
              <small>Responsable technique</small>
              <strong>Équipe Informatique et Logiciels</strong>
            </span>
          </article>
          <article>
            <Icon name="network" />
            <span>
              <small>Interface approuvée</small>
              <strong>Business API · contrat OpenAPI</strong>
            </span>
          </article>
        </div>

        <div className="authority-heading">
          <div>
            <h3>Autorités de données actives</h3>
            <p>Une deuxième source exclusive sur la même période bloquerait la publication.</p>
          </div>
          <button disabled title="Disponible après connexion du formulaire à l’API" type="button">
            Ajouter un système · bientôt
          </button>
        </div>

        <div className="authority-table" role="table" aria-label="Autorités de données">
          <div className="authority-row authority-row--head" role="row">
            <span role="columnheader">Catégorie</span>
            <span role="columnheader">Périmètre</span>
            <span role="columnheader">Source qui fait foi</span>
            <span role="columnheader">Depuis</span>
            <span role="columnheader">Sensibilité</span>
          </div>
          {authorities.map((authority) => (
            <div
              className="authority-row"
              key={`${authority.category}-${authority.scope}`}
              role="row"
            >
              <strong role="cell">{authority.category}</strong>
              <span role="cell">{authority.scope}</span>
              <span role="cell">{authority.system}</span>
              <span role="cell">{authority.since}</span>
              <span role="cell">
                <StatusBadge tone="restricted">{authority.sensitivity}</StatusBadge>
              </span>
            </div>
          ))}
        </div>

        <aside className="no-copy-proof">
          <Icon name="shield" />
          <div>
            <strong>Une autorité limitée aux données du Hub.</strong>
            <p>
              KYA-Platform fait foi pour le catalogue, ses versions et ses politiques de
              distribution. Frappe et les données métiers seront référencés dans un pilote séparé.
            </p>
          </div>
        </aside>
      </section>
    </main>
  );
}
