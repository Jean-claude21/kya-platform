import { useCallback, useEffect, useMemo, useState } from 'react';
import { Icon, StatusBadge } from '@kya/design-system';
import { platformRequest } from '../../platform/api';

export type ActiveConnector = {
  client_id: string;
  client_name: string;
  scopes: string[];
  connected_at: string;
  expires_at: string;
};

export type EffectiveProfile = {
  client_id: string;
  active_unit_key: string;
  tool_keys: string[];
  revision: string;
  shadow_diverged: boolean;
};

type RequestState = 'loading' | 'ready' | 'error';

type AiEnvironmentViewProps = {
  connectors: ActiveConnector[];
  connectorsState: RequestState;
  selectedConnector: ActiveConnector | null;
  profile: EffectiveProfile | null;
  profileState: RequestState;
  error: string;
  onRetry: () => void;
  onSelect: (clientId: string) => void;
};

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('');
}

function formatExpiry(value: string): string {
  return new Intl.DateTimeFormat('fr-FR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value));
}

export function AiEnvironmentView({
  connectors,
  connectorsState,
  selectedConnector,
  profile,
  profileState,
  error,
  onRetry,
  onSelect,
}: AiEnvironmentViewProps) {
  const tools = profile?.tool_keys ?? [];
  const isReady = profileState === 'ready' && profile !== null;
  const status =
    connectorsState === 'error'
      ? 'Service indisponible'
      : isReady
        ? 'Profil calculé'
        : connectorsState === 'ready' && connectors.length === 0
          ? 'Aucune connexion'
          : 'Lecture en cours';

  return (
    <main className="ai-page">
      <header className="page-lead">
        <div>
          <h1>Environnements IA</h1>
          <p>Connexions actives et capacités réellement exposées par KYA-Platform.</p>
        </div>
        <StatusBadge
          tone={isReady ? 'healthy' : connectorsState === 'error' ? 'attention' : 'neutral'}
        >
          {status}
        </StatusBadge>
      </header>
      <div className="ai-layout">
        <aside className="connection-list" aria-label="Connexions MCP actives">
          <h2>Connexions</h2>
          {connectorsState === 'loading' ? (
            <p className="loading-line">Découverte des connexions…</p>
          ) : connectorsState === 'error' ? (
            <button type="button" onClick={onRetry}>
              <Icon name="activity" />
              <span>
                <strong>Réessayer</strong>
                <small>Le service n’a pas répondu</small>
              </span>
            </button>
          ) : connectors.length === 0 ? (
            <p className="connection-list-empty">Aucun client MCP actif dans cette unité.</p>
          ) : (
            connectors.map((connector) => (
              <button
                aria-current={
                  selectedConnector?.client_id === connector.client_id ? 'page' : undefined
                }
                key={connector.client_id}
                type="button"
                onClick={() => {
                  onSelect(connector.client_id);
                }}
              >
                <span className="ai-monogram">{initials(connector.client_name)}</span>
                <span>
                  <strong>{connector.client_name}</strong>
                  <small>{connector.scopes.length} autorisation(s) OAuth</small>
                </span>
                <Icon name="chevron" />
              </button>
            ))
          )}
        </aside>
        <section className="profile-panel">
          <header>
            <div>
              <span>Profil effectif</span>
              <h2>{selectedConnector?.client_name ?? 'Connexion MCP'}</h2>
            </div>
            <div className="context-proof">
              <Icon name="shield" />
              <span>
                <strong>Unité active</strong>
                {profile?.active_unit_key ?? '—'}
              </span>
            </div>
          </header>
          {connectorsState === 'error' || profileState === 'error' ? (
            <div className="empty-state">
              <Icon name="lock" />
              <h3>Profil indisponible</h3>
              <p>{error}</p>
              <button className="signature-outline" type="button" onClick={onRetry}>
                Réessayer
              </button>
            </div>
          ) : connectorsState === 'ready' && connectors.length === 0 ? (
            <div className="empty-state">
              <Icon name="command" />
              <h3>Aucune connexion MCP active</h3>
              <p>Connectez KYA-Platform depuis Claude, ChatGPT ou un autre client compatible.</p>
              <small>La connexion apparaîtra ici après la validation OAuth.</small>
            </div>
          ) : profileState === 'loading' || !profile ? (
            <p className="loading-line">Calcul du profil autorisé…</p>
          ) : (
            <>
              <div className="profile-summary">
                <div>
                  <span>Outils exposés</span>
                  <strong>{tools.length}</strong>
                </div>
                <div>
                  <span>Révision</span>
                  <strong title={profile.revision}>{profile.revision.slice(0, 8)}</strong>
                </div>
                <div>
                  <span>Écart shadow</span>
                  <strong>{profile.shadow_diverged ? 'À examiner' : 'Aucun'}</strong>
                </div>
              </div>
              {tools.length === 0 ? (
                <div className="empty-state compact">
                  <Icon name="shield" />
                  <h3>Aucun outil exposé</h3>
                  <p>Le profil est valide, mais aucune capacité ne satisfait toutes les règles.</p>
                </div>
              ) : (
                <div className="tool-table">
                  <div className="tool-row tool-row--head">
                    <span>Outil</span>
                    <span>Origine</span>
                    <span>État</span>
                  </div>
                  {tools.map((tool) => (
                    <div className="tool-row" key={tool}>
                      <span>
                        <Icon name="command" />
                        <strong>{tool}</strong>
                      </span>
                      <span>Profil gouverné</span>
                      <StatusBadge tone="healthy">Disponible</StatusBadge>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </section>
        <aside className="security-rail">
          <Icon name="key" />
          <h2>Connexion gouvernée</h2>
          <p>
            Le client reçoit un jeton limité et révocable. Les secrets internes ne quittent jamais
            KYA-Platform.
          </p>
          <dl>
            <div>
              <dt>Identité</dt>
              <dd>Neon Auth</dd>
            </div>
            <div>
              <dt>Scopes accordés</dt>
              <dd>{selectedConnector?.scopes.join(', ') || '—'}</dd>
            </div>
            <div>
              <dt>Expiration</dt>
              <dd>{selectedConnector ? formatExpiry(selectedConnector.expires_at) : '—'}</dd>
            </div>
          </dl>
        </aside>
      </div>
    </main>
  );
}

export function AiEnvironment() {
  const [connectors, setConnectors] = useState<ActiveConnector[]>([]);
  const [connectorsState, setConnectorsState] = useState<RequestState>('loading');
  const [selectedClientId, setSelectedClientId] = useState('');
  const [profile, setProfile] = useState<EffectiveProfile | null>(null);
  const [profileState, setProfileState] = useState<RequestState>('loading');
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const selectedConnector = useMemo(
    () => connectors.find((connector) => connector.client_id === selectedClientId) ?? null,
    [connectors, selectedClientId],
  );

  const retry = useCallback(() => {
    setReloadKey((value) => value + 1);
  }, []);

  useEffect(() => {
    let isActive = true;
    setConnectorsState('loading');
    setError('');
    void platformRequest<ActiveConnector[]>('/mcp/me/connectors')
      .then((value) => {
        if (!isActive) return;
        setConnectors(value);
        setConnectorsState('ready');
        setSelectedClientId((current) =>
          value.some((connector) => connector.client_id === current)
            ? current
            : (value[0]?.client_id ?? ''),
        );
      })
      .catch((failure: unknown) => {
        if (!isActive) return;
        setConnectors([]);
        setConnectorsState('error');
        setError(failure instanceof Error ? failure.message : 'Connexions indisponibles.');
      });
    return () => {
      isActive = false;
    };
  }, [reloadKey]);

  useEffect(() => {
    if (!selectedClientId) {
      setProfile(null);
      setProfileState('ready');
      return;
    }
    let isActive = true;
    setProfile(null);
    setProfileState('loading');
    setError('');
    void platformRequest<EffectiveProfile>(
      `/mcp/me/effective-profile?client_id=${encodeURIComponent(selectedClientId)}`,
    )
      .then((value) => {
        if (!isActive) return;
        setProfile(value);
        setProfileState('ready');
      })
      .catch((failure: unknown) => {
        if (!isActive) return;
        setProfileState('error');
        setError(failure instanceof Error ? failure.message : 'Profil indisponible.');
      });
    return () => {
      isActive = false;
    };
  }, [reloadKey, selectedClientId]);

  return (
    <AiEnvironmentView
      connectors={connectors}
      connectorsState={connectorsState}
      error={error}
      profile={profile}
      profileState={profileState}
      selectedConnector={selectedConnector}
      onRetry={retry}
      onSelect={setSelectedClientId}
    />
  );
}
