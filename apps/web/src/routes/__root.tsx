import { HeadContent, Outlet, Scripts, createRootRoute } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import '@kya/design-system/styles.css';
import '../styles/app.css';
import '../styles/signature.css';

const DIRECTION_CONTRACT =
  'THESIS: KYA-Platform est le nœud central gouverné du système numérique du Groupe, pas un tableau de bord métier ni un assistant IA intégré. OWN-WORLD: console de précision, rail vert profond, plan de travail blanc, lignes fines et couleurs KYA sémantiques. STORY: confirmer le contexte, lire le socle, traiter les décisions, atteindre les capacités puis auditer. FIRST VIEWPORT: contexte et recherche au-dessus du nœud central et des décisions. FORM: central control plane. FINISH: verified, documented, accessible.';

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: 'utf-8' },
      { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      { title: 'KYA-Platform — Socle numérique gouverné' },
      {
        name: 'description',
        content: 'Catalogue gouverné des capacités numériques de KYA-Energy Group.',
      },
    ],
  }),
  notFoundComponent: NotFound,
  component: RootComponent,
});

function NotFound() {
  return (
    <main className="not-found">
      <h1>Page introuvable</h1>
      <p>Cette destination n’est pas encore disponible dans KYA-Platform.</p>
      <a href="/">Revenir à l’accueil</a>
    </main>
  );
}

function RootComponent() {
  return (
    <RootDocument>
      <Outlet />
    </RootDocument>
  );
}

function RootDocument({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="fr">
      <head>
        <HeadContent />
      </head>
      <body data-direction-contract={DIRECTION_CONTRACT}>
        {/*
          THESIS: KYA-Platform est le nœud central gouverné du Groupe; il refuse le tableau de bord métier et l'assistant IA simulé.
          OWN-WORLD: Rail vert profond, plan de travail blanc, géométrie nette, lignes fines et couleurs KYA strictement sémantiques.
          STORY: Confirmer le contexte, lire l'état du socle, traiter les décisions, atteindre les capacités et vérifier la trace.
          FIRST VIEWPORT: Contexte et recherche au-dessus d'une colonne vertébrale du socle, avec les décisions humaines à droite.
          FORM: Central control plane, transposé du prototype HTML/CSS validé.
          FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
        */}
        {children}
        <Scripts />
      </body>
    </html>
  );
}
