import { useMemo, useState } from 'react';

import { Icon, StatusBadge } from '@kya/design-system';

const artifacts = [
  {
    id: 'frappe',
    name: 'Frappe / ERPNext',
    type: 'App',
    version: 'Référence actuelle',
    owner: 'CVSI · Groupe',
    summary: 'Système métier existant référencé avec une frontière d’autorité explicite.',
    state: 'Référencé',
    tone: 'healthy' as const,
  },
  {
    id: 'business-method',
    name: 'Méthode métier KYA',
    type: 'Skill',
    version: '0.1.0',
    owner: 'CVSI · Groupe',
    summary: 'Transformer une méthode validée en instruction réutilisable et versionnée.',
    state: 'Publié',
    tone: 'healthy' as const,
  },
  {
    id: 'registry-mcp',
    name: 'Registry MCP',
    type: 'MCP',
    version: '0.1.0-dev',
    owner: 'CVSI · Plateforme',
    summary: 'Découvrir et demander les capacités accessibles depuis un environnement IA.',
    state: 'Dev',
    tone: 'attention' as const,
  },
  {
    id: 'soldesign',
    name: 'KYA SolDesign',
    type: 'Skill',
    version: '0.2.0',
    owner: 'DST · Groupe',
    summary: 'Appliquer la méthode KYA de pré-dimensionnement solaire.',
    state: 'En revue',
    tone: 'warning' as const,
  },
] as const;

type ArtifactType = (typeof artifacts)[number]['type'];

export function CatalogWorkbench({
  typeFilter,
  initialQuery = '',
}: {
  typeFilter?: ArtifactType;
  initialQuery?: string;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [activeType, setActiveType] = useState<ArtifactType | 'Tous'>(typeFilter ?? 'Tous');
  const initialArtifact =
    artifacts.find((artifact) => artifact.type === typeFilter) ?? artifacts[0];
  const [selectedId, setSelectedId] = useState<string>(initialArtifact.id);
  const visible = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('fr');
    return artifacts.filter(
      (artifact) =>
        (activeType === 'Tous' || artifact.type === activeType) &&
        (!normalized ||
          `${artifact.name} ${artifact.type} ${artifact.owner}`
            .toLocaleLowerCase('fr')
            .includes(normalized)),
    );
  }, [activeType, query]);
  const selected =
    visible.find((artifact) => artifact.id === selectedId) ?? visible[0] ?? initialArtifact;

  function selectType(next: ArtifactType | 'Tous') {
    setActiveType(next);
    const nextArtifact = artifacts.find((artifact) => next === 'Tous' || artifact.type === next);
    if (nextArtifact) setSelectedId(nextArtifact.id);
  }

  return (
    <main className="catalog-page">
      <section className="catalog-intro" aria-labelledby="catalog-title">
        <div>
          <span>Catalogue gouverné · données de démonstration</span>
          <h1 id="catalog-title">Capacités disponibles pour votre rôle</h1>
          <p>
            Skills, MCP, API et applications publiés, versionnés et filtrés avant toute divulgation.
          </p>
        </div>
        <div className="catalog-proof">
          <Icon name="shield" />
          <span>
            <strong>Contexte appliqué</strong>
            CVSI · Togo
          </span>
        </div>
      </section>

      <aside className="catalog-filters" aria-labelledby="catalog-filter-title">
        <h2 id="catalog-filter-title">Explorer</h2>
        <label>
          <span className="sr-only">Rechercher dans le catalogue</span>
          <Icon name="search" />
          <input
            value={query}
            placeholder="Nom, type, propriétaire…"
            onChange={(event) => {
              setQuery(event.target.value);
            }}
          />
        </label>
        <div className="catalog-facets">
          <button
            aria-pressed={activeType === 'Tous'}
            type="button"
            onClick={() => { selectType('Tous'); }}
          >
            Tous <span>{artifacts.length}</span>
          </button>
          <button
            aria-pressed={activeType === 'Skill'}
            type="button"
            onClick={() => { selectType('Skill'); }}
          >
            Skills <span>2</span>
          </button>
          <button
            aria-pressed={activeType === 'MCP'}
            type="button"
            onClick={() => { selectType('MCP'); }}
          >
            MCP <span>1</span>
          </button>
          <button
            aria-pressed={activeType === 'App'}
            type="button"
            onClick={() => { selectType('App'); }}
          >
            Apps <span>1</span>
          </button>
        </div>
        <div className="catalog-access-note">
          <Icon name="governance" />
          <p>L’absence d’un résultat peut signifier qu’il n’est pas partagé avec votre espace.</p>
        </div>
      </aside>

      <section className="catalog-results" aria-labelledby="catalog-results-title">
        <header>
          <div>
            <h2 id="catalog-results-title">Résultats autorisés</h2>
            <p>{visible.length} capacité(s) visible(s)</p>
          </div>
          <StatusBadge tone="restricted">Filtré par droits</StatusBadge>
        </header>
        <div className="artifact-grid">
          {visible.map((artifact) => (
            <button
              aria-current={artifact.id === selected.id ? 'true' : undefined}
              key={artifact.id}
              type="button"
              onClick={() => {
                setSelectedId(artifact.id);
              }}
            >
              <span className="artifact-type">
                <Icon
                  name={
                    artifact.type === 'Skill'
                      ? 'skill'
                      : artifact.type === 'MCP'
                        ? 'network'
                        : 'apps'
                  }
                />
                {artifact.type}
              </span>
              <strong>{artifact.name}</strong>
              <p>{artifact.summary}</p>
              <span className="artifact-meta">
                <small>{artifact.owner}</small>
                <StatusBadge tone={artifact.tone}>{artifact.state}</StatusBadge>
              </span>
            </button>
          ))}
        </div>
      </section>

      <aside className="artifact-detail" aria-labelledby="artifact-detail-title">
        <header>
          <span>{selected.type}</span>
          <h2 id="artifact-detail-title">{selected.name}</h2>
          <p>{selected.summary}</p>
        </header>
        <dl>
          <div>
            <dt>Version publiée</dt>
            <dd>{selected.version}</dd>
          </div>
          <div>
            <dt>Propriétaire</dt>
            <dd>{selected.owner}</dd>
          </div>
          <div>
            <dt>Intégrité</dt>
            <dd>SHA-256 vérifiée</dd>
          </div>
        </dl>
        <div className="install-state">
          <header>
            <Icon name="deploy" />
            <span>
              <strong>Installation dans cet espace</strong>
              <small>Version active 0.1.0</small>
            </span>
            <StatusBadge tone="healthy">Saine</StatusBadge>
          </header>
          <div className="update-callout">
            <span>0.1.1 disponible</span>
            <strong>Compatible · approbation requise</strong>
            <small>La version 0.1.0 restera disponible pour rollback.</small>
          </div>
        </div>
        <footer>
          <button disabled title="Disponible après connexion du workflow à Neon" type="button">
            Demander la mise à jour · bientôt
          </button>
          <button disabled title="Aucun incident actif" type="button">
            Revenir à la version saine
          </button>
        </footer>
      </aside>
    </main>
  );
}
