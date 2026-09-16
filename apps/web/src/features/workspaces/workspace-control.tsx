import { useEffect, useState } from 'react';

import { Icon, StatusBadge } from '@kya/design-system';

import { platformRequest } from '../../platform/api';

export type WorkspaceKind =
  'personal' | 'team' | 'direction' | 'project' | 'country' | 'group' | 'temporary' | 'restricted';

export type WorkspaceSummary = {
  id: string;
  key: string;
  name: string;
  kind: WorkspaceKind;
  classification: string;
};

export type WorkspaceMembership = {
  workspace_id: string;
  principal_id: string;
  level: string;
  valid_from: string;
  valid_until: string | null;
};

type RequestState = 'loading' | 'ready' | 'error';

const kindLabels: Record<WorkspaceKind, string> = {
  personal: 'Personnel',
  team: 'Équipe',
  direction: 'Direction',
  project: 'Projet',
  country: 'Pays',
  group: 'Groupe',
  temporary: 'Temporaire',
  restricted: 'Restreint',
};

const levelLabels: Record<string, string> = {
  viewer: 'Lecteur',
  guest: 'Invité',
  member: 'Membre',
  contributor: 'Contributeur',
  editor: 'Éditeur',
  manager: 'Gestionnaire',
  owner: 'Propriétaire',
};

function formatValidity(membership: WorkspaceMembership): string {
  const from = new Date(membership.valid_from).toLocaleDateString('fr-FR');
  if (!membership.valid_until) return `Depuis le ${from}`;
  const until = new Date(membership.valid_until).toLocaleDateString('fr-FR');
  return `${from} → ${until}`;
}

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
          <small>Espace actif</small>
          <strong>{active?.name ?? 'Aucun espace'}</strong>
          <em>{active ? kindLabels[active.kind] : 'Sélection requise'}</em>
        </span>
        <Icon name="chevron" />
      </button>
      {isOpen && (
        <div className="workspace-menu" role="listbox" aria-label="Choisir un espace de travail">
          <header>
            <strong>Changer de contexte</strong>
            <span>Seuls les espaces autorisés par vos droits sont proposés ici.</span>
          </header>
          {workspaces.length === 0 ? (
            <p className="workspace-menu-empty">Aucun espace accessible dans ce contexte.</p>
          ) : (
            workspaces.map((workspace) => (
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
                <Icon name={workspace.classification === 'restricted' ? 'shield' : 'people'} />
                <span>
                  <strong>{workspace.name}</strong>
                  <small>{kindLabels[workspace.kind]}</small>
                </span>
                {workspace.key === activeKey && <Icon name="check" />}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export function WorkspaceAccessPanel() {
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [listState, setListState] = useState<RequestState>('loading');
  const [listError, setListError] = useState('');
  const [selectedKey, setSelectedKey] = useState('');
  const [memberships, setMemberships] = useState<WorkspaceMembership[]>([]);
  const [membershipState, setMembershipState] = useState<RequestState>('ready');
  const [membershipError, setMembershipError] = useState('');

  useEffect(() => {
    let isActive = true;
    setListState('loading');
    setListError('');
    void platformRequest<{ items: WorkspaceSummary[] }>('/workspaces')
      .then((value) => {
        if (!isActive) return;
        setWorkspaces(value.items);
        setSelectedKey((current) =>
          value.items.some((workspace) => workspace.key === current)
            ? current
            : (value.items[0]?.key ?? ''),
        );
        setListState('ready');
      })
      .catch((failure: unknown) => {
        if (!isActive) return;
        setListError(
          failure instanceof Error ? failure.message : 'Les espaces sont indisponibles.',
        );
        setListState('error');
      });
    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedKey) {
      setMemberships([]);
      return;
    }
    let isActive = true;
    setMembershipState('loading');
    setMembershipError('');
    void platformRequest<{ items: WorkspaceMembership[] }>(
      `/workspaces/${encodeURIComponent(selectedKey)}/memberships`,
    )
      .then((value) => {
        if (!isActive) return;
        setMemberships(value.items);
        setMembershipState('ready');
      })
      .catch((failure: unknown) => {
        if (!isActive) return;
        setMembershipError(
          failure instanceof Error ? failure.message : 'Les membres sont indisponibles.',
        );
        setMembershipState('error');
      });
    return () => {
      isActive = false;
    };
  }, [selectedKey]);

  const selected = workspaces.find((workspace) => workspace.key === selectedKey) ?? null;

  return (
    <main className="workspace-page">
      <section className="workspace-intro" aria-labelledby="workspace-title">
        <div>
          <h1 id="workspace-title">Espaces et accès</h1>
          <p>
            Chaque espace est filtré par vos droits avant tout affichage. Les membres et leur
            fenêtre de validité proviennent directement du socle.
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
        {listState === 'loading' ? (
          <div className="catalog-state" role="status">
            <Icon name="activity" />
            <strong>Lecture des espaces…</strong>
          </div>
        ) : listState === 'error' ? (
          <div className="catalog-state" role="alert">
            <Icon name="lock" />
            <strong>Espaces indisponibles</strong>
            <p>{listError}</p>
          </div>
        ) : workspaces.length === 0 ? (
          <div className="catalog-state">
            <Icon name="catalog" />
            <strong>Aucun espace visible</strong>
            <p>Aucun espace n’est partagé avec votre unité active.</p>
          </div>
        ) : (
          workspaces.map((workspace) => (
            <button
              aria-current={workspace.key === selectedKey ? 'true' : undefined}
              key={workspace.key}
              type="button"
              onClick={() => {
                setSelectedKey(workspace.key);
              }}
            >
              <Icon name={workspace.classification === 'restricted' ? 'shield' : 'people'} />
              <span>
                <strong>{workspace.name}</strong>
                <small>{kindLabels[workspace.kind]}</small>
              </span>
              <StatusBadge
                tone={workspace.classification === 'restricted' ? 'restricted' : 'neutral'}
              >
                {workspace.classification}
              </StatusBadge>
            </button>
          ))
        )}
      </aside>

      <section className="access-detail" aria-labelledby="access-detail-title">
        {selected ? (
          <>
            <header>
              <div>
                <span>{kindLabels[selected.kind]}</span>
                <h2 id="access-detail-title">{selected.name}</h2>
                <p>{selected.classification} · contexte actif requis</p>
              </div>
            </header>

            <div className="access-proof">
              <Icon name="governance" />
              <div>
                <strong>Pourquoi vous voyez cet espace</strong>
                <p>
                  Ce résultat provient de la liste des espaces déjà autorisés par la politique
                  d’accès pour votre unité active. Une interdiction explicite reste toujours
                  prioritaire.
                </p>
              </div>
            </div>

            <div className="member-heading">
              <div>
                <h3>Membres et responsabilités</h3>
                <p>Les affectations temporaires expirent automatiquement.</p>
              </div>
              <button
                disabled
                title="Disponible après connexion de l’écriture à Neon"
                type="button"
              >
                Ajouter un membre · bientôt
              </button>
            </div>
            {membershipState === 'loading' ? (
              <div className="catalog-state" role="status">
                <Icon name="activity" />
                <strong>Lecture des membres…</strong>
              </div>
            ) : membershipState === 'error' ? (
              <div className="catalog-state" role="alert">
                <Icon name="lock" />
                <strong>Membres indisponibles</strong>
                <p>{membershipError}</p>
              </div>
            ) : memberships.length === 0 ? (
              <div className="catalog-state">
                <Icon name="catalog" />
                <strong>Aucun membre visible</strong>
                <p>Aucune affectation active n’est enregistrée pour cet espace.</p>
              </div>
            ) : (
              <div className="member-table" role="table" aria-label="Membres de l’espace">
                <div className="member-row member-row--head" role="row">
                  <span role="columnheader">Identifiant</span>
                  <span role="columnheader">Responsabilité</span>
                  <span role="columnheader">Validité</span>
                </div>
                {memberships.map((membership) => (
                  <div className="member-row" key={membership.principal_id} role="row">
                    <strong role="cell" title={membership.principal_id}>
                      {membership.principal_id.slice(0, 8)}…
                    </strong>
                    <span role="cell">{levelLabels[membership.level] ?? membership.level}</span>
                    <span role="cell">{formatValidity(membership)}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="catalog-state catalog-state--detail">
            <Icon name="catalog" />
            <h2 id="access-detail-title">Aucun espace sélectionné</h2>
            <p>Choisissez un espace pour afficher ses membres.</p>
          </div>
        )}
      </section>
    </main>
  );
}
