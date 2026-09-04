import { useState } from 'react';

import { Icon, StatusBadge } from '@kya/design-system';

export type WorkspaceSummary = {
  key: string;
  name: string;
  scope: string;
  role: string;
  classification: 'Interne' | 'Restreint';
};

type WorkspaceControlProps = {
  activeKey: string;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  onSelect: (workspace: WorkspaceSummary) => void;
  workspaces: WorkspaceSummary[];
};

export function WorkspaceControl({
  activeKey,
  isOpen,
  onOpenChange,
  onSelect,
  workspaces,
}: WorkspaceControlProps) {
  const active = workspaces.find((workspace) => workspace.key === activeKey) ?? workspaces[0];

  return (
    <div className="workspace-control">
      <button
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        className="context-switcher"
        type="button"
        onClick={() => {
          onOpenChange(!isOpen);
        }}
      >
        <span>
          <small>Contexte actif</small>
          {active?.scope} · {active?.name}
        </span>
        <Icon name="chevron" />
      </button>
      {isOpen && (
        <div className="workspace-menu" role="listbox" aria-label="Choisir un espace de travail">
          <header>
            <strong>Changer d’espace</strong>
            <span>Les droits sont recalculés à chaque changement.</span>
          </header>
          {workspaces.map((workspace) => (
            <button
              aria-selected={workspace.key === activeKey}
              key={workspace.key}
              role="option"
              type="button"
              onClick={() => {
                onSelect(workspace);
                onOpenChange(false);
              }}
            >
              <Icon name={workspace.classification === 'Restreint' ? 'shield' : 'people'} />
              <span>
                <strong>{workspace.name}</strong>
                <small>
                  {workspace.scope} · {workspace.role}
                </small>
              </span>
              {workspace.key === activeKey && <Icon name="check" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

type WorkspaceAccessPanelProps = {
  activeKey: string;
  onSelect: (workspace: WorkspaceSummary) => void;
  workspaces: WorkspaceSummary[];
};

const members = [
  ['Afi Amouzou', 'Propriétaire', 'Aucune expiration', 'healthy'],
  ['Bob Lawson', 'Contributeur', 'Aucune expiration', 'healthy'],
  ['Sam Mensah', 'Lecteur · stagiaire', '30 sept. 2026', 'attention'],
] as const;

export function WorkspaceAccessPanel({
  activeKey,
  onSelect,
  workspaces,
}: WorkspaceAccessPanelProps) {
  const [selectedKey, setSelectedKey] = useState(activeKey);
  const selected = workspaces.find((workspace) => workspace.key === selectedKey) ?? workspaces[0];

  return (
    <main className="workspace-page">
      <section className="workspace-intro" aria-labelledby="workspace-title">
        <div>
          <h1 id="workspace-title">Espaces et accès</h1>
          <p>
            Chaque personne travaille dans un contexte explicite. Les droits hérités, directs et
            temporaires restent visibles et vérifiables. Vue de référence sur données de
            démonstration.
          </p>
        </div>
        <button disabled title="Disponible après connexion de l’écriture à Neon" type="button">
          Créer un espace · bientôt
        </button>
      </section>

      <aside className="workspace-list" aria-label="Espaces accessibles">
        <header>
          <h2>Vos espaces</h2>
          <span>{workspaces.length}</span>
        </header>
        {workspaces.map((workspace) => (
          <button
            aria-current={workspace.key === selectedKey ? 'true' : undefined}
            key={workspace.key}
            type="button"
            onClick={() => {
              setSelectedKey(workspace.key);
            }}
          >
            <Icon name={workspace.classification === 'Restreint' ? 'shield' : 'people'} />
            <span>
              <strong>{workspace.name}</strong>
              <small>{workspace.scope}</small>
            </span>
            <StatusBadge tone={workspace.classification === 'Restreint' ? 'restricted' : 'neutral'}>
              {workspace.role}
            </StatusBadge>
          </button>
        ))}
      </aside>

      <section className="access-detail" aria-labelledby="access-detail-title">
        <header>
          <div>
            <span>{selected?.scope}</span>
            <h2 id="access-detail-title">{selected?.name}</h2>
            <p>{selected?.classification} · contexte actif requis</p>
          </div>
          {selected && selected.key !== activeKey && (
            <button
              type="button"
              onClick={() => {
                onSelect(selected);
              }}
            >
              Activer cet espace
            </button>
          )}
        </header>

        <div className="access-proof">
          <Icon name="governance" />
          <div>
            <strong>Pourquoi vous avez accès</strong>
            <p>
              Rôle {selected?.role.toLocaleLowerCase('fr')} · unité {selected?.scope} · règle
              active. Une interdiction explicite reste toujours prioritaire.
            </p>
          </div>
        </div>

        <div className="member-heading">
          <div>
            <h3>Membres et responsabilités</h3>
            <p>Les affectations temporaires expirent automatiquement.</p>
          </div>
          <button disabled title="Disponible après connexion de l’écriture à Neon" type="button">
            Ajouter un membre · bientôt
          </button>
        </div>
        <div className="member-table" role="table" aria-label="Membres de l’espace">
          <div className="member-row member-row--head" role="row">
            <span role="columnheader">Personne</span>
            <span role="columnheader">Responsabilité</span>
            <span role="columnheader">Validité</span>
            <span role="columnheader">État</span>
          </div>
          {members.map(([name, role, validity, tone]) => (
            <div className="member-row" key={name} role="row">
              <strong role="cell">{name}</strong>
              <span role="cell">{role}</span>
              <span role="cell">{validity}</span>
              <span role="cell">
                <StatusBadge tone={tone}>{tone === 'healthy' ? 'Actif' : 'Temporaire'}</StatusBadge>
              </span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
