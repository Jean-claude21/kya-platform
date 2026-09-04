import { useEffect, useMemo, useRef, useState } from 'react';

import { Button, Icon, IconButton, KyaMark, StatusBadge } from '@kya/design-system';
import type { IconName, StatusTone } from '@kya/design-system';

import {
  WorkspaceAccessPanel,
  WorkspaceControl,
  type WorkspaceSummary,
} from '../features/workspaces/workspace-control';

type Capability = {
  id: string;
  name: string;
  kind: string;
  detail: string;
  state: string;
  tone: StatusTone;
  restricted?: boolean;
  dependsOn?: string[];
};
type Layer = { id: string; label: string; icon: IconName; items: Capability[] };

const layers: Layer[] = [
  {
    id: 'sources',
    label: 'Sources',
    icon: 'database',
    items: [
      {
        id: 'frappe',
        name: 'Frappe / ERPNext',
        kind: 'Source',
        detail: 'Production',
        state: 'Disponible',
        tone: 'healthy',
      },
      {
        id: 'clients',
        name: 'Référentiel Clients',
        kind: 'Donnée',
        detail: 'Groupe',
        state: 'Disponible',
        tone: 'healthy',
      },
      {
        id: 'scraping',
        name: 'Veille & scraping',
        kind: 'Source',
        detail: 'Sandbox',
        state: 'À qualifier',
        tone: 'warning',
      },
    ],
  },
  {
    id: 'data',
    label: 'Données',
    icon: 'database',
    items: [
      {
        id: 'neon',
        name: 'Neon PostgreSQL',
        kind: 'Data',
        detail: 'Branches isolées',
        state: 'Sain',
        tone: 'healthy',
        dependsOn: ['frappe', 'clients'],
      },
      {
        id: 'storage',
        name: 'Objets & documents',
        kind: 'Storage',
        detail: 'Références seules',
        state: 'Cadré',
        tone: 'healthy',
        dependsOn: ['scraping'],
      },
    ],
  },
  {
    id: 'api',
    label: 'Business API',
    icon: 'command',
    items: [
      {
        id: 'catalog-api',
        name: 'API Catalogue',
        kind: 'API',
        detail: 'v0.1',
        state: 'En construction',
        tone: 'attention',
        dependsOn: ['neon'],
      },
      {
        id: 'reference-api',
        name: 'API Référentiels',
        kind: 'API',
        detail: 'Restreint',
        state: 'Gouverné',
        tone: 'restricted',
        restricted: true,
        dependsOn: ['neon', 'storage'],
      },
    ],
  },
  {
    id: 'mcp',
    label: 'MCP',
    icon: 'network',
    items: [
      {
        id: 'registry-mcp',
        name: 'MCP Registre',
        kind: 'MCP',
        detail: 'Rôles appliqués',
        state: 'Planifié',
        tone: 'attention',
        dependsOn: ['catalog-api'],
      },
      {
        id: 'sandbox-mcp',
        name: 'MCP Sandbox',
        kind: 'MCP',
        detail: 'Branche Neon',
        state: 'Restreint',
        tone: 'restricted',
        restricted: true,
        dependsOn: ['catalog-api', 'reference-api'],
      },
    ],
  },
  {
    id: 'skills',
    label: 'Skills',
    icon: 'skill',
    items: [
      {
        id: 'soldesign',
        name: 'KYA SolDesign',
        kind: 'Skill',
        detail: 'Énergie',
        state: 'À valider',
        tone: 'attention',
        dependsOn: ['registry-mcp'],
      },
      {
        id: 'ecolabel',
        name: 'KYA EcoLabel',
        kind: 'Skill',
        detail: 'Durabilité',
        state: 'Prototype',
        tone: 'warning',
        dependsOn: ['registry-mcp', 'sandbox-mcp'],
      },
    ],
  },
  {
    id: 'people',
    label: 'Collaborateurs',
    icon: 'people',
    items: [
      {
        id: 'my-space',
        name: 'Mon espace',
        kind: 'Rôle',
        detail: 'Responsable de domaine',
        state: '7 capacités',
        tone: 'healthy',
        dependsOn: ['soldesign'],
      },
      {
        id: 'shared-spaces',
        name: 'Espaces partagés',
        kind: 'Équipe',
        detail: 'DST · Togo',
        state: 'Autorisé',
        tone: 'healthy',
        dependsOn: ['soldesign', 'ecolabel'],
      },
    ],
  },
];

const allCapabilities = layers.flatMap((layer) => layer.items);
const graphPositions: Record<string, readonly [x: number, y: number]> = {
  frappe: [82, 82],
  clients: [82, 180],
  scraping: [82, 278],
  neon: [285, 112],
  storage: [285, 224],
  'catalog-api': [488, 112],
  'reference-api': [488, 224],
  'registry-mcp': [691, 112],
  'sandbox-mcp': [691, 224],
  soldesign: [894, 112],
  ecolabel: [894, 224],
  'my-space': [1097, 112],
  'shared-spaces': [1097, 224],
};

function NetworkTopology({ selectedId }: { selectedId: string | null }) {
  const edges = allCapabilities.flatMap((target) =>
    (target.dependsOn ?? []).map((sourceId) => ({
      sourceId,
      targetId: target.id,
      restricted: target.restricted ?? false,
    })),
  );

  return (
    <svg
      className="network-topology"
      viewBox="0 0 1180 330"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {edges.map((edge) => {
        const source = graphPositions[edge.sourceId];
        const target = graphPositions[edge.targetId];
        if (!source || !target) return null;
        const midpoint = (source[0] + target[0]) / 2;
        const active = selectedId === edge.sourceId || selectedId === edge.targetId;
        const pathData = [
          'M',
          source[0],
          source[1],
          'C',
          midpoint,
          source[1],
          midpoint,
          target[1],
          target[0],
          target[1],
        ].join(' ');
        return (
          <path
            className={`${edge.restricted ? 'network-edge--restricted' : ''} ${active ? 'network-edge--active' : ''}`}
            d={pathData}
            key={`${edge.sourceId}-${edge.targetId}`}
          />
        );
      })}
    </svg>
  );
}

const nav: Array<{ label: string; icon: IconName }> = [
  { label: 'Catalogue', icon: 'catalog' },
  { label: 'Réseau', icon: 'network' },
  { label: 'Déploiements', icon: 'deploy' },
  { label: 'Espaces', icon: 'people' },
  { label: 'Gouvernance', icon: 'governance' },
];

const decisions = [
  {
    title: 'Skill KYA SolDesign',
    detail: 'Passage en validation métier',
    owner: 'Direction Solutions Énergie',
    tone: 'attention' as const,
  },
  {
    title: 'Accès au Référentiel Clients',
    detail: 'Extension à l’équipe Prospection',
    owner: 'Responsable Data',
    tone: 'warning' as const,
  },
  {
    title: 'API Catalogue v0.1',
    detail: 'Publication sur dev',
    owner: 'CVSI',
    tone: 'healthy' as const,
  },
];

const recommendations: Array<readonly [title: string, meta: string]> = [
  ['Préparer un dimensionnement solaire', 'Skill · KYA SolDesign'],
  ['Interroger le référentiel clients', 'MCP · Données Groupe'],
  ['Créer une branche d’expérimentation', 'Neon · Sandbox'],
  ['Publier une nouvelle capacité', 'Workflow · Gouvernance'],
];

const workspaces: WorkspaceSummary[] = [
  {
    key: 'platform',
    name: 'KYA Platform',
    scope: 'CVSI · Togo',
    role: 'Gestionnaire',
    classification: 'Interne',
  },
  {
    key: 'sol-design',
    name: 'KYA SolDesign',
    scope: 'DST · Groupe',
    role: 'Contributeur',
    classification: 'Interne',
  },
  {
    key: 'interns',
    name: 'Espace stagiaires',
    scope: 'CVSI · Togo',
    role: 'Lecteur',
    classification: 'Restreint',
  },
];

export function PlatformShell() {
  const [query, setQuery] = useState('');
  const [notice, setNotice] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mobileLayerIndex, setMobileLayerIndex] = useState(0);
  const [activeModule, setActiveModule] = useState<'Réseau' | 'Espaces'>('Réseau');
  const [activeWorkspaceKey, setActiveWorkspaceKey] = useState('platform');
  const [isWorkspaceMenuOpen, setIsWorkspaceMenuOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const isFiltering = query.trim().length > 0;
  const visibleLayers = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('fr');
    if (!normalized) return layers;
    return layers
      .map((layer) => ({
        ...layer,
        items: layer.items.filter((item) =>
          `${item.name} ${item.kind} ${item.detail}`.toLocaleLowerCase('fr').includes(normalized),
        ),
      }))
      .filter((layer) => layer.items.length > 0);
  }, [query]);

  const selectedCapability = allCapabilities.find((item) => item.id === selectedId) ?? null;
  const relatedIds = new Set([
    ...(selectedCapability?.dependsOn ?? []),
    ...allCapabilities
      .filter((item) => item.dependsOn?.includes(selectedCapability?.id ?? ''))
      .map((item) => item.id),
  ]);

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === 'k') {
        event.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
      if (event.key === 'Escape' && document.activeElement === searchRef.current) {
        setQuery('');
        searchRef.current?.blur();
      }
    }
    window.addEventListener('keydown', handleShortcut);
    return () => {
      window.removeEventListener('keydown', handleShortcut);
    };
  }, []);

  function acknowledge(message: string) {
    setNotice(message);
    window.setTimeout(() => {
      setNotice('');
    }, 3200);
  }

  function moveToLayer(nextIndex: number) {
    const boundedIndex = Math.max(0, Math.min(layers.length - 1, nextIndex));
    setMobileLayerIndex(boundedIndex);
    document
      .getElementById(`layer-${layers[boundedIndex]?.id ?? 'sources'}`)
      ?.closest('.network-layer')
      ?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' });
  }

  function selectWorkspace(workspace: WorkspaceSummary) {
    setActiveWorkspaceKey(workspace.key);
    acknowledge(`${workspace.name} est maintenant le contexte actif.`);
  }

  return (
    <div className="platform-shell">
      <header className="topbar">
        <KyaMark />
        <label className="global-search">
          <Icon name="search" />
          <span className="sr-only">Rechercher une capacité ou une action</span>
          <input
            ref={searchRef}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
            placeholder="Rechercher une capacité ou une action…"
          />
          <kbd>Ctrl K</kbd>
        </label>
        <WorkspaceControl
          activeKey={activeWorkspaceKey}
          isOpen={isWorkspaceMenuOpen}
          workspaces={workspaces}
          onOpenChange={setIsWorkspaceMenuOpen}
          onSelect={selectWorkspace}
        />
        <IconButton icon="bell" label="Ouvrir les notifications" />
        <button className="user-menu" type="button" aria-label="Ouvrir le menu du compte">
          AA
        </button>
      </header>

      <nav className="module-nav" aria-label="Navigation principale">
        {nav.map((item) => (
          <button
            aria-current={item.label === activeModule ? 'page' : undefined}
            disabled={item.label !== 'Réseau' && item.label !== 'Espaces'}
            key={item.label}
            title={
              item.label === 'Réseau' || item.label === 'Espaces'
                ? `Ouvrir ${item.label}`
                : 'Disponible dans un prochain incrément'
            }
            type="button"
            onClick={() => {
              if (item.label === 'Réseau' || item.label === 'Espaces') setActiveModule(item.label);
            }}
          >
            <Icon name={item.icon} />
            {item.label}
          </button>
        ))}
      </nav>

      {activeModule === 'Espaces' ? (
        <WorkspaceAccessPanel
          activeKey={activeWorkspaceKey}
          workspaces={workspaces}
          onSelect={selectWorkspace}
        />
      ) : (
        <main>
          <section className="network-panel" aria-labelledby="network-title">
            <div className="section-heading">
              <div>
                <h1 id="network-title">Réseau de capacités</h1>
                <p>
                  Une vue commune des briques disponibles, de leurs dépendances et de leurs accès.
                </p>
              </div>
              <div className="legend" aria-label="Légende des états">
                <StatusBadge tone="healthy">Disponible</StatusBadge>
                <StatusBadge tone="attention">À valider</StatusBadge>
                <StatusBadge tone="warning">À traiter</StatusBadge>
                <StatusBadge tone="restricted">Restreint</StatusBadge>
              </div>
            </div>

            {isFiltering && (
              <div className="filter-summary" role="status">
                <span>
                  {visibleLayers.reduce((count, layer) => count + layer.items.length, 0)}{' '}
                  résultat(s) dans {visibleLayers.length} couche(s)
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setQuery('');
                  }}
                >
                  Effacer la recherche
                </button>
              </div>
            )}

            {!isFiltering && (
              <div className="layer-overview" aria-label="Parcourir les six couches du réseau">
                <button
                  aria-label="Couche précédente"
                  type="button"
                  disabled={mobileLayerIndex === 0}
                  onClick={() => {
                    moveToLayer(mobileLayerIndex - 1);
                  }}
                >
                  ‹
                </button>
                <ol>
                  {layers.map((layer, index) => (
                    <li key={layer.id}>
                      <button
                        aria-current={mobileLayerIndex === index ? 'step' : undefined}
                        type="button"
                        onClick={() => {
                          moveToLayer(index);
                        }}
                      >
                        <span>{index + 1}</span>
                        {layer.label}
                      </button>
                    </li>
                  ))}
                </ol>
                <button
                  aria-label="Couche suivante"
                  type="button"
                  disabled={mobileLayerIndex === layers.length - 1}
                  onClick={() => {
                    moveToLayer(mobileLayerIndex + 1);
                  }}
                >
                  ›
                </button>
              </div>
            )}

            <div
              className={`network-grid ${isFiltering ? 'network-grid--filtered' : ''}`}
              aria-label="Chaîne des capacités KYA"
            >
              {!isFiltering && <NetworkTopology selectedId={selectedId} />}
              {visibleLayers.map((layer) => (
                <section
                  className="network-layer"
                  key={layer.id}
                  aria-labelledby={`layer-${layer.id}`}
                >
                  <header>
                    <span className="layer-icon">
                      <Icon name={layer.icon} />
                    </span>
                    <h2 id={`layer-${layer.id}`}>{layer.label}</h2>
                    <span>{layer.items.length}</span>
                  </header>
                  <div className="network-items">
                    {layer.items.length
                      ? layer.items.map((item) => (
                          <button
                            aria-pressed={selectedId === item.id}
                            className={`capability-node ${selectedId === item.id ? 'capability-node--selected' : ''} ${relatedIds.has(item.id) ? 'capability-node--related' : ''}`}
                            key={item.name}
                            type="button"
                            onClick={() => {
                              setSelectedId(item.id);
                              acknowledge(`${item.name} : dépendances mises en évidence.`);
                            }}
                          >
                            <span className="node-top">
                              <strong>{item.name}</strong>
                              {item.restricted && <Icon name="shield" />}
                            </span>
                            <span className="node-meta">
                              <span>
                                {item.kind} · {item.detail}
                              </span>
                              <StatusBadge tone={item.tone}>{item.state}</StatusBadge>
                            </span>
                          </button>
                        ))
                      : null}
                  </div>
                </section>
              ))}
            </div>
            {selectedCapability && (
              <div className="relationship-summary" role="status">
                <Icon name="network" />
                <p>
                  <strong>{selectedCapability.name}</strong> dépend de{' '}
                  {selectedCapability.dependsOn?.length ?? 0} capacité(s) et alimente{' '}
                  {
                    allCapabilities.filter((item) =>
                      item.dependsOn?.includes(selectedCapability.id),
                    ).length
                  }{' '}
                  capacité(s) directement.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedId(null);
                  }}
                >
                  Fermer
                </button>
              </div>
            )}
          </section>

          <aside className="decision-panel" aria-labelledby="decision-title">
            <div className="section-heading">
              <div>
                <h2 id="decision-title">À décider</h2>
                <p>3 éléments attendent une action.</p>
              </div>
              <span className="decision-count">3</span>
            </div>
            <div className="decision-list">
              {decisions.map((decision) => (
                <article className="decision" key={decision.title}>
                  <StatusBadge tone={decision.tone}>{decision.title}</StatusBadge>
                  <h3>{decision.detail}</h3>
                  <p>{decision.owner}</p>
                  <div>
                    <Button disabled title="L’action sera activée avec le workflow de gouvernance">
                      <Icon name="check" />À connecter
                    </Button>
                    <button disabled title="Disponible dans un prochain incrément" type="button">
                      Détail · bientôt
                    </button>
                  </div>
                </article>
              ))}
            </div>
            <button className="all-decisions" disabled type="button">
              Toutes les décisions · bientôt <Icon name="chevron" />
            </button>
          </aside>

          <section className="recommended" aria-labelledby="recommended-title">
            <div className="section-heading">
              <div>
                <h2 id="recommended-title">Recommandé pour votre rôle</h2>
                <p>Responsable de domaine · DST · Togo</p>
              </div>
              <button disabled title="Disponible dans un prochain incrément" type="button">
                Catalogue · bientôt <Icon name="chevron" />
              </button>
            </div>
            <div className="recommendation-list">
              {recommendations.map(([title, meta]) => (
                <button
                  key={title}
                  type="button"
                  onClick={() => {
                    acknowledge(`${title} sélectionné.`);
                  }}
                >
                  <Icon name="branch" />
                  <span>
                    <strong>{title}</strong>
                    <small>{meta}</small>
                  </span>
                  <Icon name="chevron" />
                </button>
              ))}
            </div>
          </section>

          <section className="deployments" aria-labelledby="deployment-title">
            <div className="section-heading">
              <div>
                <h2 id="deployment-title">Déploiements récents</h2>
                <p>Traçabilité des versions et environnements.</p>
              </div>
            </div>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Capacité</th>
                    <th>Type</th>
                    <th>Version</th>
                    <th>Environnement</th>
                    <th>État</th>
                    <th>Mis à jour</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>API Catalogue</td>
                    <td>Business API</td>
                    <td>0.1.0-dev</td>
                    <td>Dev</td>
                    <td>
                      <StatusBadge tone="attention">En construction</StatusBadge>
                    </td>
                    <td>Aujourd’hui</td>
                  </tr>
                  <tr>
                    <td>Frappe / ERPNext</td>
                    <td>Application</td>
                    <td>Socle actuel</td>
                    <td>Production</td>
                    <td>
                      <StatusBadge tone="healthy">Disponible</StatusBadge>
                    </td>
                    <td>Hier</td>
                  </tr>
                  <tr>
                    <td>KYA SolDesign</td>
                    <td>Skill</td>
                    <td>0.2.0</td>
                    <td>Sandbox</td>
                    <td>
                      <StatusBadge tone="warning">À valider</StatusBadge>
                    </td>
                    <td>Hier</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </main>
      )}
      <div className={`toast ${notice ? 'toast--visible' : ''}`} role="status" aria-live="polite">
        {notice}
      </div>
    </div>
  );
}
