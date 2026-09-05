import { useState } from 'react';

import { Icon, StatusBadge } from '@kya/design-system';

const requests = [
  {
    id: 'sol-design',
    name: 'KYA SolDesign',
    type: 'Skill',
    version: '0.2.0',
    owner: 'Direction Solutions Énergie',
    state: 'Revue métier',
  },
  {
    id: 'catalog-api',
    name: 'API Catalogue',
    type: 'API',
    version: '0.1.0-dev',
    owner: 'CVSI',
    state: 'Approbation',
  },
] as const;

export function PublicationWorkbench() {
  const [selectedId, setSelectedId] = useState<string>(requests[0].id);
  const selected = requests.find((request) => request.id === selectedId) ?? requests[0];

  return (
    <main className="publication-page">
      <section className="publication-intro" aria-labelledby="publication-title">
        <div>
          <h1 id="publication-title">Publication gouvernée</h1>
          <p>
            Une même version traverse la soumission, la revue et l’approbation. Vue de référence sur
            données de démonstration.
          </p>
        </div>
        <button disabled title="Disponible après connexion de l’écriture à Neon" type="button">
          Nouvel artefact · bientôt
        </button>
      </section>

      <aside className="approval-inbox" aria-labelledby="approval-inbox-title">
        <header>
          <div>
            <h2 id="approval-inbox-title">À valider</h2>
            <p>Selon votre mandat actif</p>
          </div>
          <span>{requests.length}</span>
        </header>
        {requests.map((request) => (
          <button
            aria-current={request.id === selected.id ? 'true' : undefined}
            key={request.id}
            type="button"
            onClick={() => {
              setSelectedId(request.id);
            }}
          >
            <span>
              <strong>{request.name}</strong>
              <small>
                {request.type} · {request.version}
              </small>
            </span>
            <StatusBadge tone={request.state === 'Approbation' ? 'warning' : 'attention'}>
              {request.state}
            </StatusBadge>
          </button>
        ))}
      </aside>

      <section className="publication-editor" aria-labelledby="candidate-title">
        <header>
          <div>
            <span>{selected.owner}</span>
            <h2 id="candidate-title">{selected.name}</h2>
            <p>
              {selected.type} · version {selected.version}
            </p>
          </div>
          <StatusBadge tone="restricted">Digest figé</StatusBadge>
        </header>

        <ol className="publication-steps" aria-label="Progression de la publication">
          <li data-state="done">
            <Icon name="check" />
            <span>
              <strong>Soumission</strong>
              <small>Auteur identifié</small>
            </span>
          </li>
          <li data-state="active">
            <span>2</span>
            <span>
              <strong>Revue</strong>
              <small>Contrôles métier</small>
            </span>
          </li>
          <li>
            <span>3</span>
            <span>
              <strong>Approbation</strong>
              <small>Décideur distinct</small>
            </span>
          </li>
          <li>
            <span>4</span>
            <span>
              <strong>Publication</strong>
              <small>Même empreinte</small>
            </span>
          </li>
        </ol>

        <div className="candidate-fields">
          <label>
            Identifiant stable
            <input readOnly value={`kya:${selected.type.toLocaleLowerCase('fr')}:${selected.id}`} />
          </label>
          <label>
            Version candidate
            <input readOnly value={selected.version} />
          </label>
          <label className="candidate-field--wide">
            Empreinte du contenu
            <input readOnly value="b4d0…7a91 · SHA-256" />
          </label>
          <label className="candidate-field--wide">
            Justification métier
            <textarea
              defaultValue="Méthode vérifiée sur le cas pilote et prête pour une revue de conformité."
              rows={3}
            />
          </label>
        </div>

        <div className="review-checks">
          <h3>Contrôles exigés</h3>
          <ul>
            <li>
              <Icon name="check" /> Propriétaires métier et technique renseignés
            </li>
            <li>
              <Icon name="check" /> Provenance et compatibilité documentées
            </li>
            <li>
              <Icon name="check" /> Aucun secret présent dans le manifeste
            </li>
          </ul>
        </div>

        <footer>
          <p>
            Vous intervenez comme réviseur. L’approbation devra être faite par une autre personne.
          </p>
          <div>
            <button disabled title="Disponible après connexion de l’écriture à Neon" type="button">
              Demander des corrections · bientôt
            </button>
            <button disabled title="Disponible après connexion de l’écriture à Neon" type="button">
              Valider la revue · bientôt
            </button>
          </div>
        </footer>
      </section>
    </main>
  );
}
