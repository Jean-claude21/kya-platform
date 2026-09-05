import { useEffect, useState, type ReactNode, type SyntheticEvent } from 'react';

import { KyaMark } from '@kya/design-system';

import { authClient, getAccessToken } from './client';

type Mode = 'sign-in' | 'sign-up';

function messageOf(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return 'La demande n’a pas abouti. Vérifiez les informations puis réessayez.';
}

export function AuthGate({ children }: Readonly<{ children: ReactNode }>) {
  const session = authClient.useSession();
  const [mode, setMode] = useState<Mode>('sign-in');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [accountLinked, setAccountLinked] = useState(false);
  const [linkError, setLinkError] = useState('');

  useEffect(() => {
    if (!session.data?.user) {
      setAccountLinked(false);
      setLinkError('');
      return;
    }

    const controller = new AbortController();
    async function linkAccount() {
      try {
        const token = await getAccessToken();
        if (!token) throw new Error('Jeton de session indisponible.');
        const apiUrl = import.meta.env.VITE_KYA_API_URL;
        if (!apiUrl) throw new Error('API KYA non configurée.');
        const response = await fetch(`${apiUrl.replace(/\/$/, '')}/api/v1/account/me`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        if (!response.ok) throw new Error('Votre identité KYA n’a pas pu être initialisée.');
        setAccountLinked(true);
        setLinkError('');
      } catch (failure) {
        if (!controller.signal.aborted) setLinkError(messageOf(failure));
      }
    }

    void linkAccount();
    return () => {
      controller.abort();
    };
  }, [session.data?.user]);

  async function submit(event: SyntheticEvent<HTMLFormElement, SubmitEvent>) {
    event.preventDefault();
    setPending(true);
    setError('');
    const data = new FormData(event.currentTarget);
    const emailValue = data.get('email');
    const passwordValue = data.get('password');
    const nameValue = data.get('name');
    const email = typeof emailValue === 'string' ? emailValue.trim() : '';
    const password = typeof passwordValue === 'string' ? passwordValue : '';
    const name = typeof nameValue === 'string' ? nameValue.trim() : '';

    try {
      const result =
        mode === 'sign-up'
          ? await authClient.signUp.email({ email, password, name })
          : await authClient.signIn.email({ email, password });
      if (result.error) throw new Error(result.error.message);
    } catch (failure) {
      setError(messageOf(failure));
    } finally {
      setPending(false);
    }
  }

  if (session.isPending || (session.data?.user && !accountLinked && !linkError)) {
    return (
      <main className="auth-loading" aria-live="polite">
        <KyaMark />
        <p>
          {session.isPending ? 'Ouverture de votre espace KYA…' : 'Liaison de votre identité KYA…'}
        </p>
      </main>
    );
  }

  if (session.data?.user && accountLinked) return children;

  if (session.data?.user && linkError) {
    return (
      <main className="auth-loading" role="alert">
        <KyaMark />
        <p>{linkError}</p>
        <button
          type="button"
          onClick={() => {
            window.location.reload();
          }}
        >
          Réessayer
        </button>
      </main>
    );
  }

  return (
    <main className="auth-page">
      <section className="auth-story" aria-labelledby="auth-title">
        <KyaMark />
        <div>
          <h1 id="auth-title">Le patrimoine numérique KYA, accessible au bon rôle.</h1>
          <p>
            Retrouvez les Skills, MCP, applications et modèles validés pour votre Direction et votre
            contexte de travail.
          </p>
        </div>
        <ol aria-label="Fonctionnement de la plateforme">
          <li>
            <strong>Découvrez</strong>
            <span>les capacités autorisées pour vous</span>
          </li>
          <li>
            <strong>Comprenez</strong>
            <span>leur provenance et leurs conditions d’usage</span>
          </li>
          <li>
            <strong>Utilisez</strong>
            <span>depuis KYA Platform ou votre environnement IA</span>
          </li>
        </ol>
      </section>

      <section className="auth-panel" aria-labelledby="auth-form-title">
        <div className="auth-mode" role="tablist" aria-label="Accès au compte">
          <button
            aria-selected={mode === 'sign-in'}
            role="tab"
            type="button"
            onClick={() => {
              setMode('sign-in');
            }}
          >
            Se connecter
          </button>
          <button
            aria-selected={mode === 'sign-up'}
            role="tab"
            type="button"
            onClick={() => {
              setMode('sign-up');
            }}
          >
            Créer mon compte
          </button>
        </div>
        <div className="auth-copy">
          <h2 id="auth-form-title">
            {mode === 'sign-up' ? 'Créer votre accès KYA' : 'Bienvenue sur KYA Platform'}
          </h2>
          <p>
            {mode === 'sign-up'
              ? 'Utilisez votre adresse professionnelle. Vos droits seront appliqués séparément.'
              : 'Connectez-vous pour retrouver votre contexte, vos capacités et vos validations.'}
          </p>
        </div>
        <form
          onSubmit={(event) => {
            void submit(event);
          }}
        >
          {mode === 'sign-up' && (
            <label>
              Nom complet
              <input name="name" autoComplete="name" required minLength={2} />
            </label>
          )}
          <label>
            Adresse e-mail
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label>
            Mot de passe
            <input
              name="password"
              type="password"
              autoComplete={mode === 'sign-up' ? 'new-password' : 'current-password'}
              required
              minLength={8}
            />
          </label>
          {error && (
            <p className="auth-error" role="alert">
              {error}
            </p>
          )}
          <button className="auth-submit" type="submit" disabled={pending}>
            {pending
              ? 'Traitement en cours…'
              : mode === 'sign-up'
                ? 'Créer mon compte'
                : 'Se connecter'}
          </button>
        </form>
        <p className="auth-boundary">
          L’identité confirme qui vous êtes. KYA Platform vérifie ensuite, action par action, ce que
          votre rôle permet dans le contexte actif.
        </p>
      </section>
    </main>
  );
}
