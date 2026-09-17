'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const iconPaths = {
  grid: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>',
  'check-square': '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="m7 12 3 3 7-7"/>',
  panel: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
  'plus-circle': '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>',
  search: '<circle cx="10.5" cy="10.5" r="7.5"/><path d="m16 16 5 5"/>',
  library: '<path d="M4 3v18M9 3v18M14 4l2-1 4 17-3 1-3-17Z"/>',
  clipboard: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V2h6v2M9 9h6M9 13h6M9 17h4"/>',
  spark: '<path d="M12 2c1 5 3 7 8 8-5 1-7 3-8 8-1-5-3-7-8-8 5-1 7-3 8-8Z"/><path d="M19 16c.5 2 1.5 3 3 3.5-1.5.5-2.5 1.5-3 3.5-.5-2-1.5-3-3-3.5 1.5-.5 2.5-1.5 3-3.5Z"/>',
  code: '<path d="m8 5-6 7 6 7M16 5l6 7-6 7M14 2l-4 20"/>',
  users: '<circle cx="9" cy="7" r="3"/><path d="M3 21v-4a6 6 0 0 1 12 0v4M16 4a3 3 0 0 1 0 6M17 12a6 6 0 0 1 4 5.7V21"/>',
  folder: '<path d="M3 5h7l2 2h9v13H3V5Z"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19 13.5a7.8 7.8 0 0 0 0-3l2-1.5-2-3.5-2.4 1a8 8 0 0 0-2.6-1.5L13.7 2h-4L9.4 5a8 8 0 0 0-2.6 1.5l-2.4-1-2 3.5 2 1.5a7.8 7.8 0 0 0 0 3l-2 1.5 2 3.5 2.4-1A8 8 0 0 0 9.4 19l.3 3h4l.3-3a8 8 0 0 0 2.6-1.5l2.4 1 2-3.5-2-1.5Z"/>',
  chevron: '<path d="m8 10 4 4 4-4"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  x: '<path d="M5 5l14 14M19 5 5 19"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 20h16"/>',
  send: '<path d="m3 11 18-8-8 18-2-8-8-2ZM11 13l5-5"/>',
  arrow: '<path d="M4 12h16m-5-5 5 5-5 5"/>',
  document: '<path d="M5 2h10l4 4v16H5V2ZM15 2v5h4M9 11h6M9 15h6M9 19h4"/>',
  cube: '<path d="m12 2 9 5-9 5-9-5 9-5ZM3 7v10l9 5V12M21 7v10l-9 5"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 4 16 4 16 0V5M4 12v7c0 4 16 4 16 0v-7"/>',
  link: '<path d="m9 15 6-6M8 8l-2 2a4 4 0 1 0 6 6l2-2M16 16l2-2a4 4 0 1 0-6-6l-2 2"/>',
  palette: '<path d="M12 3a9 9 0 0 0 0 18h2a2 2 0 0 0 0-4h-1a2 2 0 0 1 0-4h4a4 4 0 0 0 4-4c0-4-4-6-9-6Z"/><circle cx="7.5" cy="10" r=".7"/><circle cx="10" cy="6.5" r=".7"/><circle cx="15" cy="7" r=".7"/>',
  play: '<path d="m8 5 11 7-11 7V5Z"/>',
  chart: '<path d="M4 20V9M10 20V4M16 20v-7M22 20V7M2 20h22"/>',
  shield: '<path d="m12 2 8 4v6c0 5-4.5 8-8 10-3.5-2-8-5-8-10V6l8-4Z"/><path d="m8.5 12 2.2 2.2L16 9"/>',
  rocket: '<path d="M14 4c3-2 6-2 7-1 1 1 1 4-1 7l-6 6-6-6 6-6ZM8 10l-4 1-2 4 6-1M14 16l-1 6 4-2 1-4"/><circle cx="16" cy="8" r="2"/>',
  form: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
  lightning: '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/>',
  eye: '<path d="M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/>',
  dots: '<circle cx="5" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1" fill="currentColor" stroke="none"/>',
  filter: '<path d="M4 6h16M7 12h10M10 18h4"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 10v7M12 7h.01"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  sunburst: '<path d="M12 1v22M1 12h22M4 4l16 16M4 20 20 4M8 1l8 22M1 16l22-8M1 8l22 8M8 23 16 1"/>'
};

const icon = (name) => `<svg aria-hidden="true" viewBox="0 0 24 24">${iconPaths[name] || iconPaths.document}</svg>`;
const workspace = $('#workspace');
const drawer = $('#detail-drawer');
const drawerContent = $('#drawer-content');
const installMenu = $('#install-menu');
const toast = $('#toast');

const capabilities = [
  { id: 'core', name: 'KYA Core', type: 'Application', version: 'v3.1.0', icon: 'cube', description: 'Organisation, identités, droits et référentiels du Groupe.', owner: 'Équipe Plateforme' },
  { id: 'frappe', name: 'Frappe', type: 'Application', version: 'v1.8.0', icon: 'settings', description: 'Gestion métier référencée dans KYA-Platform.', owner: 'Équipe Business' },
  { id: 'documents', name: 'Documents KYA', type: 'Application', version: 'v2.4.0', icon: 'document', description: 'Modèles et contenus documentaires du Groupe.', owner: 'Direction Administrative' },
  { id: 'design', name: 'KYA Design System', type: 'Skill', version: 'v1.2.0', icon: 'palette', description: 'Composants, guides et ressources pour concevoir des interfaces KYA cohérentes.', owner: 'Équipe Produit' },
  { id: 'studio', name: 'Studio', type: 'Application', version: 'v0.9.0', icon: 'play', description: 'Créer, tester et soumettre des capacités.', owner: 'Équipe Plateforme' },
  { id: 'spaces', name: 'Espaces', type: 'Application', version: 'v1.0.0', icon: 'users', description: 'Collaborer dans les équipes et les projets.', owner: 'KYA-Platform' },
  { id: 'data', name: 'Données énergie', type: 'Donnée', version: 'v1.0.0', icon: 'database', description: 'Jeux de données autorisés dans le contexte actif.', owner: 'Équipe Data' },
  { id: 'mcp', name: 'MCP', type: 'MCP', version: 'v2.0.0', icon: 'link', description: 'Connecteurs et outils gouvernés pour les environnements IA.', owner: 'Équipe Plateforme' },
  { id: 'skills', name: 'Skills', type: 'Skill', version: 'v1.1.0', icon: 'shield', description: 'Méthodes réutilisables et versionnées.', owner: 'Équipe Produit' },
  { id: 'analysis', name: 'Analyse documentaire', type: 'Skill', version: 'v1.1.0', icon: 'document', description: 'Extraire et structurer les informations autorisées.', owner: 'Équipe Data' },
  { id: 'sig', name: 'Connecteur SIG', type: 'MCP', version: 'v2.0.0', icon: 'link', description: 'Accès contrôlé aux données géographiques.', owner: 'Équipe Data' },
  { id: 'watch', name: 'Veille réglementaire', type: 'Application', version: 'v1.3.0', icon: 'chart', description: 'Suivre les publications et changements réglementaires.', owner: 'Stratégie' },
  { id: 'esg', name: 'Rapports ESG', type: 'Application', version: 'v1.0.0', icon: 'document', description: 'Préparer les rapports ESG gouvernés.', owner: 'RSE' }
];

const state = { view: 'applications', navKey: '', query: '', filter: 'Tout', toastTimer: null, returnFocus: null };

function decorateIcons(root = document) {
  $$('[data-icon]', root).forEach((node) => {
    if (node.querySelector('svg')) return;
    const carriesLabel = node.matches('button') && node.textContent.trim().length > 0;
    if (carriesLabel) node.insertAdjacentHTML('afterbegin', icon(node.dataset.icon));
    else node.innerHTML = icon(node.dataset.icon);
  });
}

function head(title, subtitle, actionLabel, actionAttrs = 'data-install-menu') {
  return `<header class="page-head"><div><h1>${title}</h1>${subtitle ? `<p>${subtitle}</p>` : ''}</div>${actionLabel ? `<button type="button" class="page-action" aria-label="${actionLabel}" ${actionAttrs}>${icon(actionAttrs.includes('audit') ? 'document' : actionAttrs.includes('import') ? 'download' : 'download')}<span>${actionLabel}</span>${actionAttrs.includes('install') ? icon('chevron') : ''}</button>` : ''}</header>`;
}

function tile(item, featured = false) {
  return `<button type="button" class="launch-tile${featured ? ' featured' : ''}" data-item="${item.id}"><span class="tile-icon">${icon(item.icon)}</span><span><strong>${item.name}</strong>${featured && item.description ? `<p>${item.description}</p>` : ''}${!featured && item.version ? `<small>${item.type} · ${item.version}</small>` : ''}</span></button>`;
}

function wideTile(iconName, title, description, attrs = '') {
  return `<button type="button" class="wide-tile" ${attrs}><span class="tile-icon">${icon(iconName)}</span><span><strong>${title}</strong><small>${description}</small></span></button>`;
}

function applicationsPage() {
  const ordered = capabilities.slice(0, 9);
  return `${head('Applications', '', 'Installer une capacité', 'data-install-menu')}
    <section class="section" aria-labelledby="apps-title"><h2 id="apps-title" hidden>Applications disponibles</h2>
      <div class="launcher-grid">${tile(ordered[0], true)}${ordered.slice(1).map((item) => tile(item)).join('')}</div>
      <div class="section-title"><span></span><button class="section-link" type="button" data-view="catalog">Toutes les capacités ${icon('arrow')}</button></div>
    </section>
    <section class="section" aria-labelledby="ai-title"><div class="section-title"><h2 id="ai-title">Utiliser dans vos environnements IA</h2></div>
      <div class="wide-grid">
        ${wideTile('sunburst', 'KYA-Platform pour Claude', 'Connexion et outils autorisés', 'data-panel="claude"')}
        ${wideTile('spark', 'KYA-Platform pour ChatGPT', 'Connexion et outils autorisés', 'data-panel="chatgpt"')}
        ${wideTile('code', 'KYA-Platform pour Codex', 'Connexion et outils autorisés', 'data-panel="codex"')}
      </div>
    </section>
    <section class="section" aria-labelledby="categories-title"><div class="section-title"><h2 id="categories-title">Explorer par catégorie</h2></div>
      <div class="chips">${['Applications métier','Données','Automatisation','IA & connecteurs','Administration'].map((label) => `<button type="button" class="chip" data-view="catalog">${label}</button>`).join('')}</div>
    </section>`;
}

function workPage() {
  return `${head('Bonjour Jean-Claude', '', 'Nouvelle création', 'data-view="create" data-import')}
    <section class="section" aria-labelledby="resume-title"><div class="section-title"><h2 id="resume-title">Reprendre</h2></div>
      <div class="work-grid">
        <button class="work-card featured" type="button" data-panel="deployment"><span class="tile-icon">${icon('document')}</span><span><strong>Plan de déploiement 2026</strong><small>Document · Modifié aujourd’hui</small><p>Feuille de route et jalons pour le déploiement de la plateforme KYA.</p></span></button>
        ${wideTile('palette', 'KYA Design System', 'Espace · Consulté récemment', 'data-item="design"').replace('wide-tile','work-card')}
        ${wideTile('chart', 'Veille solaire', 'Document · Modifié hier', 'data-panel="watch"').replace('wide-tile','work-card')}
        ${wideTile('users', 'Espace Direction des Systèmes', 'Espace · Consulté récemment', 'data-panel="systems"').replace('wide-tile','work-card')}
        ${wideTile('sunburst', 'Connexion Claude', 'Configuration · Modifiée il y a 2 jours', 'data-panel="claude"').replace('wide-tile','work-card')}
      </div>
      <div class="section-title"><span></span><button class="section-link" type="button" data-toast="Liste complète simulée">Voir tout mon travail ${icon('arrow')}</button></div>
    </section>
    <section class="section" aria-labelledby="today-title"><div class="section-title"><h2 id="today-title">À faire aujourd’hui</h2></div>
      <div class="wide-grid">
        ${wideTile('clipboard', '2 décisions à examiner', 'Demandes de validation en attente', 'data-panel="decisions"')}
        ${wideTile('settings', '1 installation à terminer', 'Finaliser la configuration', 'data-panel="installation"')}
        ${wideTile('users', '1 demande d’accès', 'À traiter aujourd’hui', 'data-panel="access"')}
      </div>
    </section>
    <section class="section" aria-labelledby="quick-title"><div class="section-title"><h2 id="quick-title">Accès rapides</h2></div>
      <div class="chips">${[['grid','Applications'],['shield','Skills'],['link','MCP'],['database','Données'],['users','Espaces']].map(([iconName,label]) => `<button class="chip" type="button" data-view="${label === 'Applications' ? 'applications' : 'catalog'}">${icon(iconName)}${label}</button>`).join('')}</div>
    </section>`;
}

function catalogPage() {
  const filtered = capabilities.filter((item) => {
    const matchesType = state.filter === 'Tout' || state.filter === 'Disponibles pour moi' || item.type === state.filter;
    const haystack = `${item.name} ${item.type} ${item.description} ${item.owner}`.toLocaleLowerCase('fr');
    return matchesType && haystack.includes(state.query);
  });
  const featured = filtered.find((item) => item.id === 'design') || filtered[0];
  const rest = filtered.filter((item) => item !== featured).slice(0, 8);
  return `${head('Catalogue', '', 'Demander une capacité', 'data-panel="request"')}
    <label class="search-box">${icon('search')}<input id="catalog-search" type="search" value="${state.query.replaceAll('"','&quot;')}" placeholder="Rechercher une application, un Skill, un MCP ou une donnée…" aria-label="Rechercher dans le catalogue"></label>
    <div class="chips" role="group" aria-label="Filtrer le catalogue">${['Tout','Application','Skill','MCP','Donnée','Disponibles pour moi'].map((label) => `<button type="button" class="chip${state.filter === label ? ' active' : ''}" data-filter="${label}">${label === 'Application' ? 'Applications' : label === 'Donnée' ? 'Données' : label}</button>`).join('')}</div>
    <section class="section" aria-label="Résultats du catalogue">
      ${featured ? `<div class="launcher-grid catalog-grid">${tile(featured, true)}${rest.map((item) => tile(item)).join('')}</div><div class="section-title"><span></span><button class="section-link" type="button" data-toast="Chargement de la suite simulé">Afficher toutes les capacités ${icon('arrow')}</button></div>` : `<div class="empty-state"><h2>Aucun résultat</h2><p>Modifiez la recherche ou choisissez un autre type de capacité.</p></div>`}
    </section>
    <section class="section" aria-labelledby="collections-title"><div class="section-title"><h2 id="collections-title">Collections</h2></div>
      <div class="wide-grid">${wideTile('users','Productivité','Applications et Skills pour mieux travailler au quotidien','data-filter="Application"')}${wideTile('database','Énergie & données','Données, analyses et outils autour de la transition énergétique','data-filter="Donnée"')}${wideTile('code','Outils pour les développeurs','SDK, connecteurs et ressources techniques KYA','data-filter="MCP"')}</div>
    </section>`;
}

function createPage() {
  const templates = [
    ['mcp','MCP','link'], ['application','Application','grid'], ['api','API','settings'], ['dataset','Dataset','database'],
    ['form','Formulaire','form'], ['dashboard','Dashboard','chart'], ['automation','Automatisation','lightning'], ['model','Modèle','cube']
  ];
  const skill = { id: 'new-skill', name: 'Skill', icon: 'cube', description: 'Encodez une méthode réutilisable avec ses instructions, références, scripts et médias.' };
  return `${head('Créer', 'Transformez une méthode, une intégration ou une idée en capacité gouvernée.', 'Importer un projet', 'data-toast="Import de projet simulé" data-import')}
    <section class="section" aria-label="Modèles de création"><div class="launcher-grid create-grid"><article class="launch-tile featured"><span class="tile-icon">${icon(skill.icon)}</span><span><strong>${skill.name}</strong><p>${skill.description}</p></span><button type="button" class="button-primary" data-panel="new-skill">Créer un Skill</button></article>${templates.map(([id,name,iconName]) => tile({id:`new-${id}`,name,icon:iconName})).join('')}</div>
      <div class="section-title"><span></span><button class="section-link" type="button" data-toast="Bibliothèque de modèles simulée">Voir tous les modèles ${icon('arrow')}</button></div>
    </section>
    <section class="section" aria-labelledby="draft-title"><div class="section-title"><h2 id="draft-title">Reprendre vos brouillons</h2></div>
      <div class="wide-grid">${wideTile('palette','KYA Design System 0.1.2','Modifié il y a 2 heures','data-item="design"')}${wideTile('link','Connecteur météo','Modifié hier','data-panel="weather"')}${wideTile('document','Rapports ESG','Modifié il y a 3 jours','data-item="esg"')}</div>
    </section>
    <section class="section" aria-labelledby="process-title"><div class="section-title"><h2 id="process-title">Processus de publication</h2></div>
      <div class="process">${[['Brouillon','Créez et documentez votre capacité.'],['Tester','Vérifiez le bon fonctionnement.'],['Faire valider','Soumettez pour revue et approbation.'],['Publier','Rendez la capacité disponible dans vos espaces.']].map(([title,text], index) => `<article class="process-step"><span class="step-number">${index + 1}</span><strong>${title}</strong><p>${text}</p></article>`).join('')}</div>
    </section>`;
}

function adminPage() {
  const areas = [
    ['Identités & accès','users'],['Rôles & politiques','shield'],['Catalogue & versions','document'],['Publications','send'],
    ['Intégrations & secrets','link'],['Environnements IA','database'],['Déploiements','rocket'],['Audit','clipboard']
  ];
  const organisation = { id: 'organisation', name: 'Organisation', icon: 'cube', description: 'Filiales, agences, directions, équipes et contextes actifs.' };
  return `${head('Administration', 'Configurez le socle, les accès et les capacités de KYA-Platform.', 'Ouvrir le journal d’audit', 'data-panel="audit" data-audit')}
    <section class="section" aria-label="Domaines d’administration"><div class="launcher-grid">${tile(organisation, true)}${areas.map(([name,iconName], index) => tile({id:`admin-${index}`,name,icon:iconName})).join('')}</div>
      <div class="section-title"><span></span><button class="section-link" type="button" data-toast="Administration complète simulée">Toute l’administration ${icon('arrow')}</button></div>
    </section>
    <section class="section" aria-labelledby="health-title"><div class="section-title"><h2 id="health-title">État du socle</h2></div>
      <div class="wide-grid">
        ${wideTile('users','Identité et autorisation','Opérationnel','data-panel="identity"')}
        ${wideTile('database','Catalogue','Opérationnel','data-panel="catalog-health"')}
        ${wideTile('document','Publications','À vérifier','data-panel="publication-health"')}
      </div>
    </section>
    <section class="section" aria-labelledby="admin-decisions-title"><div class="section-title"><h2 id="admin-decisions-title">Décisions administratives</h2></div>
      <table class="admin-table"><thead><tr><th>Demande</th><th>Objet</th><th>Demandeur</th><th>Statut</th><th>Date</th><th><span class="sr-only">Actions</span></th></tr></thead><tbody>
        <tr><td>Demande de rôle</td><td>Accès équipe Data — Lecteur</td><td>Profil illustratif</td><td><span class="status-label warning"><span class="status-dot warning"></span>En attente</span></td><td>Date illustrative</td><td><button class="more-button" data-panel="role-request" aria-label="Examiner la demande de rôle">${icon('dots')}</button></td></tr>
        <tr><td>Demande de publication</td><td>Modèle de prévision solaire</td><td>Profil illustratif</td><td><span class="status-label"><span class="status-dot"></span>Approuvée</span></td><td>Date illustrative</td><td><button class="more-button" data-panel="publication-request" aria-label="Examiner la demande de publication">${icon('dots')}</button></td></tr>
      </tbody></table>
    </section>`;
}

function render() {
  const pages = { applications: applicationsPage, work: workPage, catalog: catalogPage, create: createPage, admin: adminPage };
  workspace.innerHTML = (pages[state.view] || applicationsPage)();
  workspace.dataset.currentView = state.view;
  decorateIcons(workspace);
  $$('.nav-item').forEach((button) => {
    const key = button.dataset.view === 'catalog' ? (button.hasAttribute('data-focus-search') ? 'search' : 'library') : button.dataset.view;
    const active = Boolean(key && key === state.navKey);
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
}

function setView(view, source) {
  state.view = view;
  state.navKey = view === 'catalog' ? (source?.hasAttribute('data-focus-search') ? 'search' : 'library') : view === 'applications' ? '' : view;
  closeInstallMenu();
  render();
  workspace.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (source?.hasAttribute('data-focus-search')) requestAnimationFrame(() => $('#catalog-search')?.focus());
  $('#sidebar').classList.remove('mobile-open');
}

function showDrawer(title, description, lines = [], primary = 'Fermer') {
  state.returnFocus = document.activeElement;
  drawerContent.innerHTML = `<h2 id="drawer-title" tabindex="-1">${title}</h2><p>${description}</p><div class="drawer-meta"><p><strong>Contexte actif</strong><br>KYA-Energy Group · Groupe</p><p><strong>Accès</strong><br>Évalué selon votre profil et votre espace actif.</p></div>${lines.length ? `<ul class="drawer-list">${lines.map((line) => `<li>${icon('document')}<span>${line}</span></li>`).join('')}</ul>` : ''}<div class="drawer-actions"><button type="button" class="button-primary" data-close-dialog>${primary}</button><button type="button" class="button-secondary" data-toast="Action secondaire simulée">Voir la documentation</button></div>`;
  if (!drawer.open) drawer.showModal();
  document.body.style.overflow = 'hidden';
  $('#drawer-title')?.focus({ preventScroll: true });
}

function closeDrawer() {
  if (drawer.open) drawer.close();
}

drawer.addEventListener('close', () => {
  document.body.style.overflow = '';
  if (state.returnFocus instanceof HTMLElement) state.returnFocus.focus({ preventScroll: true });
});

drawer.addEventListener('click', (event) => {
  if (event.target !== drawer) return;
  const rect = drawer.getBoundingClientRect();
  if (event.clientX < rect.left) closeDrawer();
});

function itemDrawer(id) {
  if (id.startsWith('new-')) {
    const label = id.replace('new-', '');
    showDrawer(`Créer : ${label}`, 'Ce modèle prépare une capacité gouvernée dans votre espace personnel.', ['Choisir le contexte et le propriétaire', 'Générer la structure depuis le template maître', 'Tester avant toute soumission'], 'Commencer');
    return;
  }
  if (id.startsWith('admin-') || id === 'organisation') {
    const item = id === 'organisation' ? { name: 'Organisation', description: 'Structurez les filiales, agences, directions, équipes et affectations.' } : { name: 'Administration du socle', description: 'Cette zone est visible uniquement lorsque vos droits effectifs le permettent.' };
    showDrawer(item.name, item.description, ['Autorité et système de référence', 'Historique et validité temporelle', 'Droits effectifs et preuve d’accès'], 'Consulter');
    return;
  }
  const item = capabilities.find((entry) => entry.id === id);
  if (!item) return;
  showDrawer(item.name, item.description, [`Type : ${item.type}`, `Version illustrative : ${item.version}`, `Propriétaire : ${item.owner}`], item.type === 'Application' ? 'Ouvrir' : 'Consulter');
}

const panelContent = {
  claude: ['Claude', 'Connectez KYA-Platform à Claude pour utiliser uniquement les outils autorisés dans votre contexte.', ['Authentification KYA', 'Profil d’outils effectif', 'Révocation et historique']],
  chatgpt: ['ChatGPT', 'Connectez KYA-Platform à ChatGPT avec un profil calculé par identité, contexte et politique.', ['Authentification KYA', 'Capacités compatibles', 'Révocation et historique']],
  codex: ['Codex', 'Connectez KYA-Platform à Codex pour rechercher, créer et administrer selon vos droits.', ['Authentification KYA', 'Profil d’outils effectif', 'Révocation et historique']],
  systems: ['Direction des Systèmes', 'Espace récent visible dans votre contexte actif.', ['Membres et responsabilités', 'Capacités partagées', 'Historique des activités']],
  data: ['Équipe Data', 'Espace de collaboration consacré aux contrats, jeux de données et intégrations.', ['Membres et responsabilités', 'Capacités partagées', 'Demandes en attente']],
  solar: ['Projet solaire', 'Espace de projet illustratif.', ['Documents et données autorisés', 'Capacités du projet', 'Membres temporaires']],
  account: ['Jean-Claude', 'Profil de démonstration du prototype.', ['Profil : CVSI', 'Contexte : Groupe', 'Session : illustrée']],
  request: ['Demander une capacité', 'Décrivez le besoin et le contexte. La demande sera dirigée vers le propriétaire approprié.', ['Nom ou résultat attendu', 'Équipe ou espace concerné', 'Justification et durée']],
  audit: ['Journal d’audit', 'Consultez les événements relevant de votre mandat.', ['Identité et contexte', 'Action et ressource', 'Résultat et corrélation']],
  deployment: ['Plan de déploiement 2026', 'Reprenez le travail illustratif là où vous l’avez laissé.', ['Contexte : Studio', 'État : brouillon', 'Dernière modification : aujourd’hui']],
  watch: ['Veille solaire', 'Contenu de veille illustratif.', ['Sources autorisées', 'Extraits et provenance', 'Historique']],
  decisions: ['Décisions', 'Deux décisions illustratives attendent votre examen.', ['Publication d’une capacité', 'Demande d’accès']],
  installation: ['Installation à terminer', 'Une installation illustrative doit être confirmée.', ['Vérifier le package', 'Activer dans l’environnement', 'Enregistrer le reçu']],
  access: ['Demande d’accès', 'Une demande illustrative doit être examinée.', ['Identité et contexte', 'Rôle demandé', 'Durée et justification']],
  'new-skill': ['Créer un Skill', 'Démarrez depuis le template maître KYA-Platform.', ['SKILL.md et métadonnées', 'Références, scripts, médias et tests', 'Validation et publication']],
  weather: ['Connecteur météo', 'Brouillon de connecteur illustratif.', ['Contrat MCP', 'Outils et permissions', 'Tests de compatibilité']],
  identity: ['Identité et autorisation', 'État opérationnel illustratif.', ['Authentification', 'Décisions de politiques', 'Sessions actives']],
  'catalog-health': ['Catalogue', 'État opérationnel illustratif.', ['Recherche filtrée par droits', 'Versions publiées', 'Provenance']],
  'publication-health': ['Publications', 'Un élément illustratif reste à vérifier.', ['Contrôles déterministes', 'Revues métier et technique', 'Signature et immutabilité']],
  'role-request': ['Demande de rôle', 'Examinez la portée, la durée et les droits résultants avant décision.', ['Équipe Data', 'Rôle : Lecteur', 'Décision auditée']],
  'publication-request': ['Demande de publication', 'Publication illustrative déjà approuvée.', ['Portée : Groupe', 'Version immuable', 'Preuve de validation']]
};

function showPanel(name) {
  const [title, description, lines] = panelContent[name] || ['Information', 'Élément de démonstration du prototype.', []];
  showDrawer(title, description, lines, name === 'request' ? 'Préparer la demande' : 'Fermer');
}

function notify(message) {
  toast.textContent = `${message} — prototype, aucune action réelle.`;
  toast.classList.add('visible');
  window.clearTimeout(state.toastTimer);
  state.toastTimer = window.setTimeout(() => toast.classList.remove('visible'), 3800);
}

function showInstallMenu(button) {
  const rect = button.getBoundingClientRect();
  installMenu.hidden = false;
  installMenu.style.top = `${Math.min(rect.bottom + 8, window.innerHeight - installMenu.offsetHeight - 16)}px`;
  installMenu.style.left = `${Math.max(16, rect.right - installMenu.offsetWidth)}px`;
  installMenu.querySelector('button')?.focus();
}

function closeInstallMenu() { installMenu.hidden = true; }

document.addEventListener('click', (event) => {
  const view = event.target.closest('[data-view]');
  const item = event.target.closest('[data-item]');
  const panel = event.target.closest('[data-panel]');
  const filter = event.target.closest('[data-filter]');
  const installer = event.target.closest('[data-install-menu]');
  const close = event.target.closest('[data-close-dialog]');
  const toastButton = event.target.closest('[data-toast]');
  const mobileMenu = event.target.closest('.mobile-menu');
  const railToggle = event.target.closest('.rail-toggle');

  if (!event.target.closest('#install-menu') && !installer) closeInstallMenu();
  if (installer) showInstallMenu(installer);
  else if (mobileMenu) $('#sidebar').classList.toggle('mobile-open');
  else if (railToggle) {
    document.documentElement.classList.toggle('collapsed');
    const expanded = !document.documentElement.classList.contains('collapsed');
    railToggle.setAttribute('aria-expanded', String(expanded));
    railToggle.setAttribute('aria-label', expanded ? 'Réduire la navigation' : 'Déployer la navigation');
  }
  else if (close) closeDrawer();
  else if (view) setView(view.dataset.view, view);
  else if (item) itemDrawer(item.dataset.item);
  else if (panel) showPanel(panel.dataset.panel);
  else if (filter) { state.filter = filter.dataset.filter; render(); }
  else if (toastButton) notify(toastButton.dataset.toast);
});

document.addEventListener('input', (event) => {
  if (!event.target.matches('#catalog-search')) return;
  state.query = event.target.value.trim().toLocaleLowerCase('fr');
  const position = event.target.selectionStart;
  render();
  const search = $('#catalog-search');
  search?.focus();
  search?.setSelectionRange(position, position);
});

document.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    state.view = 'catalog';
    state.navKey = 'search';
    render();
    $('#catalog-search')?.focus();
  }
  if (event.key === 'Escape' && !installMenu.hidden) closeInstallMenu();
});

decorateIcons();
render();
