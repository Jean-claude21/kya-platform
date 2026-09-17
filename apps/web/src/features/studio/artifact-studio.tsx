import { useEffect, useMemo, useState } from 'react';

import { Icon, StatusBadge } from '@kya/design-system';
import type { IconName, StatusTone } from '@kya/design-system';

import { idempotencyKey, platformRequest } from '../../platform/api';
import type { WorkspaceMembership, WorkspaceSummary } from '../workspaces/workspace-control';
import {
  buildArtifactTree,
  collectFolderPaths,
  fileName,
  type ArtifactTreeFile,
  type ArtifactTreeNode,
} from './artifact-tree';
import { designSystemPackage } from './design-system-package.gen';

type ProposalStatus =
  | 'submitted'
  | 'in_review'
  | 'approved'
  | 'rejected'
  | 'pull_request_open'
  | 'merged'
  | 'closed_without_merge';

type Proposal = {
  id: string;
  target_workspace_id: string;
  slug: string;
  artifact_type: string;
  artifact_id: string | null;
  requested_by: string;
  requested_at: string;
  status: ProposalStatus;
  reviewer_id: string | null;
  review_reason: string | null;
  reviewed_at: string | null;
  business_owner_id: string | null;
  technical_owner_id: string | null;
  pull_request_url: string | null;
  merged_commit_sha: string | null;
};

type ProposalSummary = Proposal & { file_count: number; package_size: number };
type ProposalFile = ArtifactTreeFile;
type ProposalEvidence = {
  code: string;
  status: 'passed' | 'pending' | 'failed';
  summary: string;
};
type ProposalReview = {
  proposal: Proposal;
  files: ProposalFile[];
  evidence: ProposalEvidence[];
};
type LoadState = 'loading' | 'ready' | 'empty' | 'error';
type ActionState = 'idle' | 'working' | 'success' | 'error';
type AccountView = { principal_id: string; email: string | null };

const isPreview = import.meta.env.DEV && import.meta.env.VITE_KYA_PREVIEW_MODE === 'app';
const PREVIEW_WORKSPACE = '019914b2-1a40-7000-8000-000000000071';
const PREVIEW_PROPOSAL = '019914b2-1a40-7000-8000-0000000000c1';

const statusLabels: Record<ProposalStatus, string> = {
  submitted: 'À examiner',
  in_review: 'En revue',
  approved: 'Approuvée',
  rejected: 'Rejetée',
  pull_request_open: 'PR ouverte',
  merged: 'Fusionnée',
  closed_without_merge: 'Fermée',
};

function statusTone(status: ProposalStatus): StatusTone {
  if (status === 'approved' || status === 'merged') return 'healthy';
  if (status === 'submitted' || status === 'in_review') return 'attention';
  if (status === 'rejected' || status === 'closed_without_merge') return 'restricted';
  return 'neutral';
}

function iconFor(path: string): IconName {
  if (path.endsWith('.yaml') || path.endsWith('.json') || path.endsWith('.css')) return 'code';
  return 'file';
}

function humanSize(size: number): string {
  if (size < 1024) return `${String(size)} o`;
  return `${(size / 1024).toFixed(1)} Ko`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function decodeText(value: string): string {
  try {
    const bytes = Uint8Array.from(atob(value), (character) => character.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  } catch {
    return 'Le contenu texte ne peut pas être décodé.';
  }
}

function encodeText(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function fileFormat(path: string): string {
  const extension = fileName(path).split('.').at(-1);
  return extension && extension !== fileName(path) ? extension.toUpperCase() : 'TEXTE';
}

type ArtifactFileTreeProps = {
  files: ProposalFile[];
  selectedPath: string;
  onSelect: (path: string) => void;
};

function ArtifactFileTree({ files, selectedPath, onSelect }: ArtifactFileTreeProps) {
  const nodes = useMemo(() => buildArtifactTree(files), [files]);
  const folderPaths = useMemo(() => collectFolderPaths(nodes), [nodes]);
  const folderKey = folderPaths.join('\u0000');
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(folderPaths));

  useEffect(() => {
    setExpanded(new Set(folderPaths));
  }, [folderKey]);

  function toggle(path: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  function renderNodes(items: ArtifactTreeNode[], depth = 0) {
    return (
      <ul className="review-tree-level">
        {items.map((node) => {
          if (node.kind === 'folder') {
            const isExpanded = expanded.has(node.path);
            return (
              <li key={node.path}>
                <button
                  className="review-tree-folder"
                  type="button"
                  aria-expanded={isExpanded}
                  style={{ paddingLeft: `${String(10 + depth * 16)}px` }}
                  onClick={() => {
                    toggle(node.path);
                  }}
                >
                  <span className="review-tree-chevron" aria-hidden="true">
                    <Icon name="chevron" />
                  </span>
                  <Icon name="folder" />
                  <span>{node.name}</span>
                  <small>{node.children.length}</small>
                </button>
                {isExpanded && renderNodes(node.children, depth + 1)}
              </li>
            );
          }
          return (
            <li key={node.path}>
              <button
                className="review-tree-file"
                type="button"
                aria-current={node.path === selectedPath ? 'page' : undefined}
                style={{ paddingLeft: `${String(30 + depth * 16)}px` }}
                title={node.path}
                onClick={() => {
                  onSelect(node.path);
                }}
              >
                <Icon name={iconFor(node.path)} />
                <span>{node.name}</span>
                <small>{humanSize(node.file.size)}</small>
              </button>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <section className="review-file-explorer" aria-labelledby="review-files-title">
      <header>
        <div>
          <h3 id="review-files-title">Arborescence</h3>
          <p>{files.length} fichiers dans ce paquet</p>
        </div>
        {folderPaths.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setExpanded(expanded.size === folderPaths.length ? new Set() : new Set(folderPaths));
            }}
          >
            {expanded.size === folderPaths.length ? 'Réduire' : 'Tout ouvrir'}
          </button>
        )}
      </header>
      <nav className="review-files" aria-label="Arborescence des fichiers de la proposition">
        {renderNodes(nodes)}
      </nav>
    </section>
  );
}

function previewReview(status: ProposalStatus = 'submitted'): ProposalReview {
  const now = new Date().toISOString();
  const files = designSystemPackage.map((file) => ({
    path: file.path,
    kind: file.kind,
    size: file.size,
    contentBase64: file.kind === 'binary' ? '' : encodeText(file.content ?? ''),
  }));
  return {
    proposal: {
      id: PREVIEW_PROPOSAL,
      target_workspace_id: PREVIEW_WORKSPACE,
      slug: 'kya-design-system',
      artifact_type: 'skill',
      artifact_id: null,
      requested_by: '019914b2-1a40-7000-8000-000000000031',
      requested_at: now,
      status,
      reviewer_id: status === 'submitted' ? null : '019914b2-1a40-7000-8000-000000000032',
      review_reason: null,
      reviewed_at: status === 'submitted' ? null : now,
      business_owner_id: null,
      technical_owner_id: null,
      pull_request_url: null,
      merged_commit_sha: null,
    },
    files,
    evidence: [
      {
        code: 'admission_validation',
        status: 'passed',
        summary: 'Le paquet satisfait les contrôles d’admission déterministes.',
      },
      {
        code: 'file_inventory',
        status: 'passed',
        summary: `${String(files.length)} fichiers présents dans le paquet de démonstration.`,
      },
      {
        code: 'human_review',
        status: status === 'submitted' ? 'pending' : 'passed',
        summary:
          status === 'submitted'
            ? 'La décision d’un réviseur habilité est requise.'
            : 'La décision humaine est enregistrée.',
      },
    ],
  };
}

function previewSummary(review: ProposalReview): ProposalSummary {
  return {
    ...review.proposal,
    file_count: review.files.length,
    package_size: review.files.reduce((total, file) => total + file.size, 0),
  };
}

export function ArtifactStudio() {
  const preview = useMemo(() => previewReview(), []);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>(
    isPreview
      ? [
          {
            id: PREVIEW_WORKSPACE,
            key: 'kya-platform',
            name: 'KYA-Platform',
            kind: 'team',
            classification: 'internal',
          },
        ]
      : [],
  );
  const [workspaceId, setWorkspaceId] = useState(isPreview ? PREVIEW_WORKSPACE : '');
  const [proposals, setProposals] = useState<ProposalSummary[]>(
    isPreview ? [previewSummary(preview)] : [],
  );
  const [selectedId, setSelectedId] = useState(isPreview ? PREVIEW_PROPOSAL : '');
  const [review, setReview] = useState<ProposalReview | null>(isPreview ? preview : null);
  const [selectedPath, setSelectedPath] = useState(preview.files[0]?.path ?? '');
  const [listState, setListState] = useState<LoadState>(isPreview ? 'ready' : 'loading');
  const [detailState, setDetailState] = useState<LoadState>(isPreview ? 'ready' : 'empty');
  const [error, setError] = useState('');
  const [actionState, setActionState] = useState<ActionState>('idle');
  const [actionMessage, setActionMessage] = useState('');
  const [businessOwner, setBusinessOwner] = useState('');
  const [technicalOwner, setTechnicalOwner] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [account, setAccount] = useState<AccountView | null>(null);
  const [memberships, setMemberships] = useState<WorkspaceMembership[]>([]);
  const [membersState, setMembersState] = useState<LoadState>('empty');
  const [wrapLines, setWrapLines] = useState(true);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle');

  useEffect(() => {
    if (isPreview) return;
    let active = true;
    setListState('loading');
    void Promise.all([
      platformRequest<{ items: WorkspaceSummary[] }>('/workspaces'),
      platformRequest<AccountView>('/account/me'),
    ])
      .then(([response, currentAccount]) => {
        if (!active) return;
        setAccount(currentAccount);
        setWorkspaces(response.items);
        setWorkspaceId(response.items[0]?.id ?? '');
        if (response.items.length === 0) setListState('empty');
      })
      .catch((failure: unknown) => {
        if (!active) return;
        setError(failure instanceof Error ? failure.message : 'Les espaces sont indisponibles.');
        setListState('error');
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (isPreview || !workspaceId) return;
    const workspace = workspaces.find((item) => item.id === workspaceId);
    if (!workspace) return;
    let active = true;
    setMembersState('loading');
    void platformRequest<{ items: WorkspaceMembership[] }>(
      `/workspaces/${encodeURIComponent(workspace.key)}/memberships`,
    )
      .then((response) => {
        if (!active) return;
        const now = Date.now();
        const eligible = response.items.filter(
          (membership) =>
            new Date(membership.valid_from).getTime() <= now &&
            (!membership.valid_until || new Date(membership.valid_until).getTime() > now),
        );
        setMemberships(eligible);
        setMembersState(eligible.length > 0 ? 'ready' : 'empty');
      })
      .catch(() => {
        if (!active) return;
        setMemberships([]);
        setMembersState('error');
      });
    return () => {
      active = false;
    };
  }, [workspaceId, workspaces]);

  useEffect(() => {
    if (isPreview || !workspaceId) return;
    let active = true;
    setListState('loading');
    setError('');
    void platformRequest<{ items: ProposalSummary[] }>(
      `/proposals?target_workspace_id=${encodeURIComponent(workspaceId)}&limit=100`,
    )
      .then((response) => {
        if (!active) return;
        setProposals(response.items);
        setSelectedId((current) =>
          response.items.some((item) => item.id === current)
            ? current
            : (response.items[0]?.id ?? ''),
        );
        setListState(response.items.length === 0 ? 'empty' : 'ready');
      })
      .catch((failure: unknown) => {
        if (!active) return;
        setError(failure instanceof Error ? failure.message : 'La file de revue est indisponible.');
        setListState('error');
      });
    return () => {
      active = false;
    };
  }, [workspaceId]);

  useEffect(() => {
    if (isPreview || !selectedId) return;
    let active = true;
    setDetailState('loading');
    setActionMessage('');
    void platformRequest<ProposalReview>(`/proposals/${encodeURIComponent(selectedId)}/review`)
      .then((response) => {
        if (!active) return;
        setReview(response);
        setSelectedPath(response.files[0]?.path ?? '');
        setDetailState('ready');
      })
      .catch((failure: unknown) => {
        if (!active) return;
        setError(failure instanceof Error ? failure.message : 'La proposition est indisponible.');
        setDetailState('error');
      });
    return () => {
      active = false;
    };
  }, [selectedId]);

  const selectedFile = review?.files.find((file) => file.path === selectedPath) ?? review?.files[0];
  const selectedText = useMemo(
    () =>
      selectedFile && selectedFile.kind !== 'binary' ? decodeText(selectedFile.contentBase64) : '',
    [selectedFile],
  );
  const selectedLines = useMemo(() => selectedText.split('\n'), [selectedText]);
  const canDecide =
    review?.proposal.status === 'submitted' || review?.proposal.status === 'in_review';
  const canOpenPullRequest = review?.proposal.status === 'approved';
  const isOwnProposal = Boolean(
    account && review && account.principal_id === review.proposal.requested_by,
  );

  useEffect(() => {
    if (!account || isOwnProposal || memberships.length === 0) return;
    const currentIsMember = memberships.some(
      (membership) => membership.principal_id === account.principal_id,
    );
    if (!currentIsMember) return;
    setBusinessOwner((current) => current || account.principal_id);
    setTechnicalOwner((current) => current || account.principal_id);
  }, [account, isOwnProposal, memberships]);

  useEffect(() => {
    setCopyState('idle');
  }, [selectedPath]);

  async function copySelectedFile() {
    if (!selectedText) return;
    try {
      await navigator.clipboard.writeText(selectedText);
      setCopyState('copied');
    } catch {
      setCopyState('error');
    }
  }

  async function runAction(action: 'approve' | 'reject' | 'pull-request' | 'merge-status') {
    if (!review) return;
    if (isPreview) {
      const nextStatus: ProposalStatus =
        action === 'approve'
          ? 'approved'
          : action === 'reject'
            ? 'rejected'
            : action === 'pull-request'
              ? 'pull_request_open'
              : review.proposal.status;
      const reviewCompleted = nextStatus === 'approved' || nextStatus === 'rejected';
      const updated: ProposalReview = {
        ...review,
        proposal: {
          ...review.proposal,
          status: nextStatus,
          reviewer_id: reviewCompleted ? 'preview-reviewer' : review.proposal.reviewer_id,
          reviewed_at: reviewCompleted
            ? (review.proposal.reviewed_at ?? new Date().toISOString())
            : review.proposal.reviewed_at,
          review_reason:
            nextStatus === 'rejected' ? rejectionReason : review.proposal.review_reason,
          pull_request_url:
            nextStatus === 'pull_request_open'
              ? 'https://github.com/kya-energy/kya-platform/pull/preview'
              : review.proposal.pull_request_url,
        },
        evidence: review.evidence.map((item) =>
          item.code === 'human_review' && reviewCompleted
            ? { ...item, status: 'passed', detail: 'Décision humaine enregistrée dans cet aperçu.' }
            : item,
        ),
      };
      setReview(updated);
      setProposals([previewSummary(updated)]);
      setActionState('success');
      setActionMessage('Action simulée dans l’aperçu local. Aucune donnée n’a été modifiée.');
      return;
    }

    const proposalId = encodeURIComponent(review.proposal.id);
    let path = `/proposals/${proposalId}/merge-status`;
    let body: Record<string, string> = {};
    if (action === 'approve') {
      path = `/proposals/${proposalId}/approvals`;
      body = { business_owner_id: businessOwner, technical_owner_id: technicalOwner };
    } else if (action === 'reject') {
      path = `/proposals/${proposalId}/rejections`;
      body = { reason: rejectionReason };
    } else if (action === 'pull-request') {
      path = `/proposals/${proposalId}/pull-request`;
    }
    setActionState('working');
    setActionMessage('');
    try {
      await platformRequest<Proposal>(path, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey(`proposal-${action}`),
        },
        body: JSON.stringify(body),
      });
      const refreshed = await platformRequest<ProposalReview>(`/proposals/${proposalId}/review`);
      setReview(refreshed);
      setProposals((current) =>
        current.map((item) =>
          item.id === refreshed.proposal.id ? { ...item, ...refreshed.proposal } : item,
        ),
      );
      setActionState('success');
      setActionMessage(
        action === 'pull-request'
          ? 'La pull request GitHub a été ouverte par l’identité de service.'
          : 'La décision a été enregistrée dans la piste d’audit.',
      );
    } catch (failure) {
      setActionState('error');
      setActionMessage(failure instanceof Error ? failure.message : 'L’action a échoué.');
    }
  }

  return (
    <main className="signature-review-studio">
      <header className="review-studio-lead">
        <div>
          <h1>Studio de revue</h1>
          <p>
            Examinez le contenu et les preuves avant toute décision. GitHub ne reçoit le paquet
            qu’après approbation humaine.
          </p>
        </div>
        <label className="review-workspace-select">
          <span>Espace de revue</span>
          <select
            value={workspaceId}
            disabled={workspaces.length < 2}
            onChange={(event) => {
              setWorkspaceId(event.target.value);
              setReview(null);
              setSelectedId('');
            }}
          >
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </label>
      </header>

      {isPreview && (
        <p className="review-preview-note">
          Aperçu local : les décisions sont simulées et ne créent aucune pull request.
        </p>
      )}

      <div className="review-studio-layout">
        <aside className="review-queue" aria-label="Propositions à examiner">
          <header>
            <div>
              <h2>Propositions</h2>
              <p>{proposals.length} dans cet espace</p>
            </div>
            <StatusBadge tone={proposals.length > 0 ? 'attention' : 'neutral'}>
              {proposals.filter((item) => item.status === 'submitted').length} en attente
            </StatusBadge>
          </header>
          {listState === 'loading' ? (
            <div className="review-state" role="status">
              <Icon name="activity" />
              <strong>Lecture de la file…</strong>
            </div>
          ) : listState === 'error' ? (
            <div className="review-state" role="alert">
              <Icon name="lock" />
              <strong>File indisponible</strong>
              <p>{error}</p>
            </div>
          ) : listState === 'empty' ? (
            <div className="review-state">
              <Icon name="check" />
              <strong>Aucune proposition</strong>
              <p>Les nouvelles soumissions apparaîtront ici.</p>
            </div>
          ) : (
            <nav>
              {proposals.map((proposal) => (
                <button
                  key={proposal.id}
                  type="button"
                  aria-current={proposal.id === selectedId ? 'page' : undefined}
                  onClick={() => {
                    setSelectedId(proposal.id);
                    if (isPreview) {
                      setReview(preview);
                      setSelectedPath(preview.files[0]?.path ?? '');
                    }
                  }}
                >
                  <Icon name={proposal.artifact_type === 'skill' ? 'skill' : 'code'} />
                  <span>
                    <strong>{proposal.slug}</strong>
                    <small>
                      {proposal.artifact_type} · {proposal.file_count} fichiers ·{' '}
                      {humanSize(proposal.package_size)}
                    </small>
                    <small>{formatDate(proposal.requested_at)}</small>
                  </span>
                  <StatusBadge tone={statusTone(proposal.status)}>
                    {statusLabels[proposal.status]}
                  </StatusBadge>
                </button>
              ))}
            </nav>
          )}
        </aside>

        <section className="review-workbench" aria-labelledby="review-title">
          {detailState === 'loading' ? (
            <div className="review-state review-state--large" role="status">
              <Icon name="activity" />
              <h2 id="review-title">Lecture du paquet…</h2>
            </div>
          ) : detailState === 'error' ? (
            <div className="review-state review-state--large" role="alert">
              <Icon name="lock" />
              <h2 id="review-title">Proposition indisponible</h2>
              <p>{error}</p>
            </div>
          ) : review ? (
            <>
              <header className="review-workbench-head">
                <div>
                  <span>{review.proposal.artifact_type}</span>
                  <h2 id="review-title">{review.proposal.slug}</h2>
                  <p>
                    Soumise le {formatDate(review.proposal.requested_at)} · auteur{' '}
                    <code>{review.proposal.requested_by.slice(0, 8)}…</code>
                  </p>
                </div>
                <StatusBadge tone={statusTone(review.proposal.status)}>
                  {statusLabels[review.proposal.status]}
                </StatusBadge>
              </header>
              <div className="review-files-layout">
                <ArtifactFileTree
                  files={review.files}
                  selectedPath={selectedFile?.path ?? ''}
                  onSelect={setSelectedPath}
                />
                <article className="review-file-view">
                  <header>
                    <div className="review-file-heading">
                      <div className="review-file-path" aria-label="Chemin du fichier">
                        {selectedFile?.path.split('/').map((segment, index, segments) => (
                          <span key={`${segment}-${String(index)}`}>
                            {segment}
                            {index < segments.length - 1 && <i aria-hidden="true">/</i>}
                          </span>
                        ))}
                      </div>
                      <p>
                        {selectedFile ? humanSize(selectedFile.size) : ''}
                        {selectedFile?.kind !== 'binary' &&
                          ` · ${String(selectedLines.length)} lignes`}
                      </p>
                    </div>
                    {selectedFile?.kind !== 'binary' && (
                      <div className="review-reader-actions">
                        <span>{selectedFile ? fileFormat(selectedFile.path) : ''}</span>
                        <button
                          type="button"
                          aria-pressed={wrapLines}
                          onClick={() => {
                            setWrapLines((current) => !current);
                          }}
                        >
                          {wrapLines ? 'Retour auto.' : 'Lignes longues'}
                        </button>
                        <button type="button" onClick={() => void copySelectedFile()}>
                          {copyState === 'copied'
                            ? 'Copié'
                            : copyState === 'error'
                              ? 'Échec de copie'
                              : 'Copier'}
                        </button>
                      </div>
                    )}
                  </header>
                  {selectedFile?.kind === 'binary' ? (
                    <div className="review-binary">
                      <Icon name="file" />
                      <strong>Fichier binaire</strong>
                      <p>Le paquet conserve ce fichier intact. Aucun aperçu texte n’est produit.</p>
                    </div>
                  ) : (
                    <div className="review-code" data-wrap={wrapLines ? 'true' : 'false'}>
                      <ol aria-label={`Contenu de ${selectedFile?.path ?? 'ce fichier'}`}>
                        {selectedLines.map((line, index) => (
                          <li key={`${String(index)}-${line.slice(0, 12)}`}>
                            <code>{line || ' '}</code>
                          </li>
                        ))}
                      </ol>
                    </div>
                  )}
                </article>
              </div>
            </>
          ) : (
            <div className="review-state review-state--large">
              <Icon name="catalog" />
              <h2 id="review-title">Sélectionnez une proposition</h2>
              <p>Son contenu, ses preuves et les actions autorisées apparaîtront ici.</p>
            </div>
          )}
        </section>

        <aside className="review-decision" aria-label="Preuves et décision">
          <section>
            <h2>Preuves</h2>
            <div className="review-evidence">
              {review?.evidence.map((evidence) => (
                <div key={evidence.code} data-state={evidence.status}>
                  <Icon name={evidence.status === 'passed' ? 'check' : 'clock'} />
                  <span>
                    <strong>
                      {evidence.status === 'passed'
                        ? 'Vérifié'
                        : evidence.status === 'failed'
                          ? 'Échec'
                          : 'En attente'}
                    </strong>
                    <small>{evidence.summary}</small>
                  </span>
                </div>
              ))}
            </div>
          </section>

          {review && canDecide && (
            <section className="review-decision-form">
              <h2>Décision</h2>
              {isOwnProposal && (
                <p className="review-duty-warning" role="note">
                  Cette proposition a été soumise avec votre identité. Une autre personne habilitée
                  doit l’approuver ou la rejeter.
                </p>
              )}
              <label>
                <span>Responsable métier</span>
                <select
                  value={businessOwner}
                  disabled={membersState !== 'ready' || isOwnProposal}
                  onChange={(event) => {
                    setBusinessOwner(event.target.value);
                  }}
                >
                  <option value="">Choisir un membre actif</option>
                  {memberships.map((membership) => (
                    <option
                      key={`business-${membership.principal_id}`}
                      value={membership.principal_id}
                    >
                      {membership.principal_id === account?.principal_id
                        ? `${account.email ?? 'Mon compte'} · ${membership.level}`
                        : `${membership.principal_id.slice(0, 8)}… · ${membership.level}`}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Responsable technique</span>
                <select
                  value={technicalOwner}
                  disabled={membersState !== 'ready' || isOwnProposal}
                  onChange={(event) => {
                    setTechnicalOwner(event.target.value);
                  }}
                >
                  <option value="">Choisir un membre actif</option>
                  {memberships.map((membership) => (
                    <option
                      key={`technical-${membership.principal_id}`}
                      value={membership.principal_id}
                    >
                      {membership.principal_id === account?.principal_id
                        ? `${account.email ?? 'Mon compte'} · ${membership.level}`
                        : `${membership.principal_id.slice(0, 8)}… · ${membership.level}`}
                    </option>
                  ))}
                </select>
              </label>
              {membersState === 'error' && (
                <p className="review-field-error" role="alert">
                  Les membres de cet espace sont indisponibles. Réessayez après actualisation.
                </p>
              )}
              <button
                className="signature-primary"
                type="button"
                disabled={
                  actionState === 'working' ||
                  isOwnProposal ||
                  (!isPreview && (!businessOwner.trim() || !technicalOwner.trim()))
                }
                onClick={() => void runAction('approve')}
              >
                <Icon name="check" />
                Approuver
              </button>
              <label>
                <span>Motif de rejet</span>
                <textarea
                  value={rejectionReason}
                  placeholder="Expliquez la correction attendue"
                  onChange={(event) => {
                    setRejectionReason(event.target.value);
                  }}
                />
              </label>
              <button
                className="review-reject"
                type="button"
                disabled={
                  actionState === 'working' || isOwnProposal || rejectionReason.trim().length < 3
                }
                onClick={() => void runAction('reject')}
              >
                Rejeter avec motif
              </button>
            </section>
          )}

          {review && canOpenPullRequest && (
            <section className="review-pr-action">
              <h2>GitHub</h2>
              <p>Le dépôt et la branche cible sont imposés par la configuration du serveur.</p>
              <button
                className="signature-primary"
                type="button"
                disabled={actionState === 'working'}
                onClick={() => void runAction('pull-request')}
              >
                <Icon name="branch" />
                Ouvrir la pull request
              </button>
            </section>
          )}

          {review?.proposal.status === 'pull_request_open' && (
            <section className="review-pr-action">
              <h2>Pull request ouverte</h2>
              {review.proposal.pull_request_url && (
                <a href={review.proposal.pull_request_url} target="_blank" rel="noreferrer">
                  Voir sur GitHub
                </a>
              )}
              <button
                className="signature-outline"
                type="button"
                disabled={actionState === 'working'}
                onClick={() => void runAction('merge-status')}
              >
                Vérifier la fusion
              </button>
            </section>
          )}

          {actionMessage && (
            <p
              className="review-action-message"
              role={actionState === 'error' ? 'alert' : 'status'}
            >
              {actionMessage}
            </p>
          )}
        </aside>
      </div>
    </main>
  );
}
