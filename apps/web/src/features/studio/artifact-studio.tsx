import { useMemo, useState } from 'react';
import { Icon, StatusBadge } from '@kya/design-system';
import type { IconName } from '@kya/design-system';
import { designSystemPackage } from './design-system-package.gen';

const LOGO = 'assets/brand/kya-energy-group-logo.png';

function iconFor(path: string): IconName {
  if (path.endsWith('.png') || path.startsWith('assets/')) return 'file';
  if (path.endsWith('.md')) return 'file';
  if (path.endsWith('.yaml') || path.endsWith('.json')) return 'code';
  return 'file';
}

function humanSize(size: number): string {
  if (size < 1024) return `${String(size)} o`;
  return `${(size / 1024).toFixed(1)} Ko`;
}

export function ArtifactStudio() {
  const files = designSystemPackage;
  const [selectedPath, setSelectedPath] = useState(files[0]?.path ?? LOGO);
  const selected = useMemo(
    () => files.find((file) => file.path === selectedPath) ?? files[0],
    [files, selectedPath],
  );
  const manifest = files.find((file) => file.path === 'artifact.manifest.json');
  const version = manifest?.content?.match(/"version":\s*"([^"]+)"/)?.[1] ?? '0.1.0';

  return (
    <main className="signature-studio">
      <header className="signature-studio-lead">
        <div>
          <h1>Studio — Skills &amp; MCP</h1>
          <p>
            Le paquet réel de la capacité, tel qu&rsquo;il sera versionné et publié. Contenu lu
            depuis le dépôt, sans donnée inventée.
          </p>
        </div>
        <div className="signature-studio-actions">
          <StatusBadge tone="attention">Paquet local</StatusBadge>
          <button
            className="signature-primary"
            type="button"
            disabled
            title="La soumission sera reliée au registre gouverné dans un prochain incrément"
          >
            Soumettre · bientôt
          </button>
        </div>
      </header>
      <div className="signature-studio-grid">
        <aside className="signature-studio-tree" aria-label="Fichiers du paquet">
          <header>
            <img src="/brand/kya-energy-group-logo.png" alt="" />
            <span>
              <strong>KYA Design System</strong>
              <small>skill · v{version}</small>
            </span>
          </header>
          <nav>
            {files.map((file) => (
              <button
                key={file.path}
                type="button"
                aria-current={file.path === selected?.path ? 'page' : undefined}
                onClick={() => {
                  setSelectedPath(file.path);
                }}
              >
                <Icon name={iconFor(file.path)} />
                <span>{file.path}</span>
                <small>{humanSize(file.size)}</small>
              </button>
            ))}
          </nav>
          <footer>
            <Icon name="branch" />
            <span>
              <strong>feat-kya-signature-integration</strong>
              <small>Travail isolé avant revue</small>
            </span>
          </footer>
        </aside>
        <section className="signature-studio-view" aria-labelledby="studio-file-title">
          <header>
            <div>
              <h2 id="studio-file-title">{selected?.path}</h2>
              <small>
                {selected ? humanSize(selected.size) : ''} ·{' '}
                {selected?.kind === 'binary' ? 'binaire' : 'texte'}
              </small>
            </div>
          </header>
          {selected?.path === LOGO ? (
            <div className="signature-studio-asset">
              <img src="/brand/kya-energy-group-logo.png" alt="Logo officiel KYA-Energy Group" />
              <p>Logo officiel intact, copié tel quel dans le paquet.</p>
            </div>
          ) : selected?.kind === 'binary' ? (
            <div className="signature-studio-asset">
              <p>Fichier binaire ({humanSize(selected.size)}).</p>
            </div>
          ) : (
            <pre>{selected?.content}</pre>
          )}
        </section>
        <aside className="signature-studio-rail">
          <h2>Cycle de publication</h2>
          <ol className="signature-lifecycle">
            {[
              ['Structure', 'Paquet maître conforme', true],
              ['Tests', 'Validation locale', true],
              ['Revue métier', 'Décision humaine', false],
              ['Publication', 'Version immuable', false],
            ].map(([title, detail, done]) => (
              <li key={title as string} className={done ? 'done' : ''}>
                <span aria-hidden="true">{done ? '✓' : ''}</span>
                <div>
                  <strong>{title as string}</strong>
                  <small>{detail as string}</small>
                </div>
              </li>
            ))}
          </ol>
          <div className="signature-studio-policy">
            <Icon name="shield" />
            <p>
              <strong>L&rsquo;IA raisonne, le logiciel exécute.</strong>
              La publication reste déterministe, tracée et soumise à revue humaine.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}
