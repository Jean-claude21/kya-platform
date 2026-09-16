import { useEffect, useRef, useState } from 'react';
import { Icon } from '@kya/design-system';
import type { IconName } from '@kya/design-system';
import { PersonalHome } from '../features/home/personal-home';
import { CatalogWorkbench } from '../features/catalog/catalog-workbench';
import { ArtifactStudio } from '../features/studio/artifact-studio';
import { AiEnvironment } from '../features/ai/ai-environment';
import { ControlCenter, type AdminTarget } from '../features/admin/control-center';
import { OrganizationAdmin } from '../features/admin/organization-admin';
import { CoreAdministration } from '../features/admin/core-administration';
import { WorkspaceAccessPanel } from '../features/workspaces/workspace-control';
import { PublicationWorkbench } from '../features/publication/publication-workbench';
import { SystemAuthorityWorkbench } from '../features/systems/system-authority-workbench';
import { SecretAccessWorkbench } from '../features/secrets/secret-access-workbench';
import { AuditTimeline } from '../features/audit/audit-timeline';
import { authClient } from '../auth/client';
import { platformRequest } from '../platform/api';
import { getActiveUnitId, setActiveUnitId } from '../platform/active-context';

export type Module =
  'Accueil' | 'Catalogue' | 'Apps' | 'MCP' | 'Skills' | 'Studio' | 'Administration' | AdminTarget;
const navigation: Array<{ target: Module; label: string; icon: IconName }> = [
  { target: 'Accueil', label: 'Accueil', icon: 'home' },
  { target: 'Catalogue', label: 'Catalogue', icon: 'catalog' },
  { target: 'MCP', label: 'Mes connexions', icon: 'network' },
  { target: 'Espaces', label: 'Espaces', icon: 'people' },
  { target: 'Studio', label: 'Studio', icon: 'code' },
];
const isPreview = import.meta.env.DEV && import.meta.env.VITE_KYA_PREVIEW_MODE === 'app';

type ShellUnit = {
  key: string;
  name: string;
  type_key: string;
};

const previewUnits: ShellUnit[] = [
  { key: 'direction-systemes', name: 'Direction des Systèmes', type_key: 'direction' },
  { key: 'communication', name: 'Communication', type_key: 'direction' },
  { key: 'stagiaires', name: 'Espace stagiaires', type_key: 'team' },
];
const previewDefaultUnit: ShellUnit = {
  key: 'direction-systemes',
  name: 'Direction des Systèmes',
  type_key: 'direction',
};

export function PlatformShell() {
  const [activeModule, setActiveModule] = useState<Module>('Accueil');
  const [activeUnit, setActiveUnit] = useState<ShellUnit>(
    isPreview
      ? previewDefaultUnit
      : { key: getActiveUnitId(), name: 'Contexte en cours…', type_key: 'group' },
  );
  const [availableUnits, setAvailableUnits] = useState<ShellUnit[]>(isPreview ? previewUnits : []);
  const [query, setQuery] = useState('');
  const [catalogQuery, setCatalogQuery] = useState('');
  const [email, setEmail] = useState('Compte KYA');
  const [accountError, setAccountError] = useState('');
  const [panel, setPanel] = useState<'menu' | 'account' | 'notifications' | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const content = useRef<HTMLDivElement>(null);
  const dialogTitle = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (isPreview) return;
    let active = true;
    void platformRequest<{ email: string | null; active_unit_id: string }>('/account/me')
      .then(async (account) => {
        setActiveUnitId(account.active_unit_id);
        const [current, children] = await Promise.all([
          platformRequest<ShellUnit>(`/core/organization/${account.active_unit_id}`),
          platformRequest<{ items: ShellUnit[] }>(
            `/core/organization/${account.active_unit_id}/children?limit=100`,
          ),
        ]);
        if (active) {
          setEmail(account.email ?? 'Compte KYA');
          setActiveUnit(current);
          setAvailableUnits([current, ...children.items]);
        }
      })
      .catch(() => {
        if (active) setAccountError('Les informations du compte sont indisponibles.');
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    const handle = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        dialog.current?.close();
        setPanel(null);
        search.current?.focus();
      }
    };
    window.addEventListener('keydown', handle);
    return () => {
      window.removeEventListener('keydown', handle);
    };
  }, []);
  useEffect(() => {
    if (panel) {
      dialog.current?.showModal();
      dialogTitle.current?.focus();
    }
  }, [panel]);

  function navigate(target: Module) {
    setActiveModule(target);
    dialog.current?.close();
    setPanel(null);
    window.scrollTo({ top: 0, behavior: 'instant' });
    requestAnimationFrame(() => content.current?.focus());
  }
  let screen;
  if (activeModule === 'Accueil')
    screen = (
      <PersonalHome
        onNavigate={navigate}
        unit={activeUnit.name}
        query={query}
        preview={isPreview}
      />
    );
  else if (activeModule === 'Catalogue' || activeModule === 'Apps' || activeModule === 'Skills') {
    screen = (
      <CatalogWorkbench
        key={activeModule + catalogQuery}
        initialQuery={catalogQuery}
        {...(activeModule === 'Apps'
          ? { typeFilter: 'App' as const }
          : activeModule === 'Skills'
            ? { typeFilter: 'Skill' as const }
            : {})}
      />
    );
  } else if (activeModule === 'MCP') screen = <AiEnvironment />;
  else if (activeModule === 'Studio') screen = <ArtifactStudio />;
  else if (activeModule === 'Espaces') screen = <WorkspaceAccessPanel />;
  else if (activeModule === 'Administration') screen = <ControlCenter onOpen={navigate} />;
  else if (activeModule === 'Organisation') screen = <OrganizationAdmin />;
  else if (activeModule === 'Core') screen = <CoreAdministration />;
  else if (activeModule === 'Systèmes') screen = <SystemAuthorityWorkbench />;
  else if (activeModule === 'Secrets') screen = <SecretAccessWorkbench />;
  else if (activeModule === 'Publications') screen = <PublicationWorkbench />;
  else screen = <AuditTimeline workspaceKey="platform" />;

  const navButtons = navigation.map((item) => (
    <button
      key={item.target}
      type="button"
      aria-current={activeModule === item.target ? 'page' : undefined}
      onClick={() => {
        navigate(item.target);
      }}
    >
      <Icon name={item.icon} />
      <span>{item.label}</span>
    </button>
  ));
  return (
    <div className="signature-app">
      <a className="signature-skip" href="#workspace-content">
        Aller au contenu
      </a>
      <header className="signature-topbar">
        <button
          className="signature-menu signature-icon"
          type="button"
          aria-label="Ouvrir la navigation"
          onClick={() => {
            setPanel('menu');
          }}
        >
          <Icon name="catalog" />
        </button>
        <a className="signature-brand" href="/">
          <img src="/brand/kya-energy-group-logo.png" alt="KYA-Energy Group" />
          <strong>KYA-Platform</strong>
        </a>
        <div className="signature-context">
          <label>
            <span>Organisation</span>
            <select aria-label="Organisation active" value="KYA-Energy Group" disabled>
              <option>KYA-Energy Group</option>
            </select>
          </label>
          <label>
            <span>Unité{isPreview ? ' · aperçu' : ' active'}</span>
            <select
              aria-label="Unité active"
              value={activeUnit.key}
              disabled={availableUnits.length < 2}
              onChange={(event) => {
                const selected = availableUnits.find((unit) => unit.key === event.target.value);
                if (!selected) return;
                setActiveUnitId(selected.key);
                setActiveUnit(selected);
              }}
            >
              {availableUnits.map((unit) => (
                <option key={unit.key} value={unit.key}>
                  {unit.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <form
          className="signature-search"
          role="search"
          onSubmit={(event) => {
            event.preventDefault();
            setCatalogQuery(query);
            navigate('Catalogue');
          }}
        >
          <Icon name="search" />
          <input
            ref={search}
            aria-label="Rechercher une capacité"
            type="search"
            value={query}
            placeholder="Rechercher…"
            onChange={(event) => {
              setQuery(event.target.value);
            }}
          />
          <kbd>Ctrl K</kbd>
        </form>
        <button
          className="signature-icon signature-bell"
          type="button"
          aria-label="Notifications"
          onClick={() => {
            setPanel('notifications');
          }}
        >
          <Icon name="bell" />
        </button>
        <button
          className="signature-avatar"
          type="button"
          aria-label="Ouvrir le compte"
          onClick={() => {
            setPanel('account');
          }}
        >
          <Icon name="user" />
        </button>
      </header>
      <div className="signature-layout">
        <aside className="signature-sidebar">
          <nav aria-label="Navigation principale">{navButtons}</nav>
          <div className="signature-sidebar-bottom">
            <button
              type="button"
              aria-current={activeModule === 'Administration' ? 'page' : undefined}
              onClick={() => {
                navigate('Administration');
              }}
            >
              <Icon name="shield" />
              <span>Administration</span>
              <Icon name="chevron" />
            </button>
            <button
              type="button"
              onClick={() => {
                setPanel('account');
              }}
            >
              <Icon name="user" />
              <span>
                Mon compte<small>{isPreview ? 'Aperçu local' : 'Session authentifiée'}</small>
              </span>
            </button>
          </div>
        </aside>
        <div
          className="signature-content"
          id="workspace-content"
          ref={content}
          tabIndex={-1}
          key={`${activeModule}-${activeUnit.key}`}
        >
          {activeModule !== 'Accueil' && (
            <button
              type="button"
              className="signature-back"
              onClick={() => {
                navigate('Accueil');
              }}
            >
              Accueil /{' '}
              {navigation.find((item) => item.target === activeModule)?.label ?? activeModule}
            </button>
          )}
          {screen}
        </div>
      </div>
      <dialog
        className="signature-dialog"
        ref={dialog}
        onClose={() => {
          setPanel(null);
        }}
        aria-labelledby="signature-dialog-title"
      >
        <button className="signature-close" type="button" onClick={() => dialog.current?.close()}>
          Fermer
        </button>
        <h2 id="signature-dialog-title" ref={dialogTitle} tabIndex={-1}>
          {panel === 'menu' ? 'Navigation' : panel === 'account' ? 'Mon compte' : 'Notifications'}
        </h2>
        {panel === 'menu' && (
          <nav aria-label="Navigation mobile">
            {navButtons}
            <button
              type="button"
              onClick={() => {
                navigate('Administration');
              }}
            >
              <Icon name="shield" />
              Administration
            </button>
          </nav>
        )}
        {panel === 'notifications' && (
          <p>
            La boîte de notifications personnelle n’est pas encore reliée. Aucun compteur d’activité
            n’est simulé.
          </p>
        )}
        {panel === 'account' && (
          <>
            <p>{isPreview ? 'Mode de validation visuelle — aucune session requise.' : email}</p>
            <p>
              {accountError ||
                'Les autorisations sont vérifiées par le serveur pour chaque action. Le contexte d’aperçu ne change aucun droit.'}
            </p>
            <button
              className="signature-primary"
              type="button"
              disabled={isPreview}
              onClick={() => {
                void authClient
                  .signOut()
                  .then((result) => {
                    if (result.error) setAccountError('La déconnexion a échoué. Réessayez.');
                    else window.location.assign('/');
                  })
                  .catch(() => {
                    setAccountError('La déconnexion a échoué. Réessayez.');
                  });
              }}
            >
              Se déconnecter
            </button>
          </>
        )}
      </dialog>
    </div>
  );
}
