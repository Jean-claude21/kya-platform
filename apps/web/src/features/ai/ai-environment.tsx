import { useEffect, useState } from 'react';
import { Icon, StatusBadge } from '@kya/design-system';
import { platformRequest } from '../../platform/api';

function clientLabel(id: string): string {
  if (id === 'chatgpt') return 'ChatGPT';
  return id.charAt(0).toUpperCase() + id.slice(1);
}

type EffectiveProfile = {
  client_id: string;
  active_unit_key: string;
  tool_keys: string[];
  revision: string;
  shadow_diverged: boolean;
};

export function AiEnvironment() {
  const [clientId, setClientId] = useState('claude');
  const [profile, setProfile] = useState<EffectiveProfile | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setProfile(null);
    setError('');
    void platformRequest<EffectiveProfile>(
      `/mcp/me/effective-profile?client_id=${encodeURIComponent(clientId)}`,
    )
      .then((value) => {
        if (active) setProfile(value);
      })
      .catch((failure: unknown) => {
        if (active) setError(failure instanceof Error ? failure.message : 'Profil indisponible.');
      });
    return () => {
      active = false;
    };
  }, [clientId]);
  const tools = profile?.tool_keys ?? [];
  return (
    <main className="ai-page">
      <header className="page-lead">
        <div>
          <span className="eyebrow">Une identité · des droits contextualisés</span>
          <h1>Environnements IA</h1>
          <p>Voir exactement quelles capacités KYA-Platform expose à chaque connecteur autorisé.</p>
        </div>
        <StatusBadge tone={profile ? 'healthy' : 'neutral'}>
          {profile ? 'Profil calculé' : 'Lecture en cours'}
        </StatusBadge>
      </header>
      <div className="ai-layout">
        <aside className="connection-list" aria-label="Connecteurs IA">
          <h2>Connexions</h2>
          {['claude', 'chatgpt', 'codex'].map((client) => (
            <button
              aria-current={clientId === client ? 'page' : undefined}
              key={client}
              type="button"
              onClick={() => { setClientId(client); }}
            >
              <span className="ai-monogram">{client[0]?.toUpperCase()}</span>
              <span>
                <strong>
                  {clientLabel(client)}
                </strong>
                <small>
                  {clientId === client && profile ? 'Autorisation active' : 'Vérifier le profil'}
                </small>
              </span>
              <Icon name="chevron" />
            </button>
          ))}
        </aside>
        <section className="profile-panel">
          <header>
            <div>
              <span>Profil effectif</span>
              <h2>
                {clientLabel(clientId)}
              </h2>
            </div>
            <div className="context-proof">
              <Icon name="shield" />
              <span>
                <strong>Unité active</strong>
                {profile?.active_unit_key ?? 'group'}
              </span>
            </div>
          </header>
          {error ? (
            <div className="empty-state">
              <Icon name="lock" />
              <h3>Aucune autorisation active trouvée</h3>
              <p>{error}</p>
              <small>
                Créez d’abord le connecteur depuis Claude, ChatGPT ou Codex. KYA-Platform affichera
                ensuite son profil réel.
              </small>
            </div>
          ) : !profile ? (
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
                  <strong>{profile.revision}</strong>
                </div>
                <div>
                  <span>Écart détecté</span>
                  <strong>{profile.shadow_diverged ? 'Oui' : 'Non'}</strong>
                </div>
              </div>
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
            </>
          )}
        </section>
        <aside className="security-rail">
          <Icon name="key" />
          <h2>Une seule connexion</h2>
          <p>
            Le connecteur ne reçoit jamais les clés internes. Il obtient un jeton limité, révocable
            et évalué action par action.
          </p>
          <dl>
            <div>
              <dt>Identité</dt>
              <dd>Neon Auth</dd>
            </div>
            <div>
              <dt>Autorisation</dt>
              <dd>Rôle + unité + client</dd>
            </div>
            <div>
              <dt>Exécution</dt>
              <dd>Outils filtrés</dd>
            </div>
          </dl>
        </aside>
      </div>
    </main>
  );
}
