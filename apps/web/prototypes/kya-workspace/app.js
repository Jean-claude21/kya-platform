const $ = (selector) => document.querySelector(selector);
const icon = (name) => `<svg aria-hidden="true"><use href="../kya-command/icons.svg#${name}"/></svg>`;
const resources = [
  {id:'design',name:'KYA Design System',type:'Skill',icon:'spark',owner:'Communication · CVSI',version:'0.1.0',description:'L’identité KYA dans chaque interface et chaque document.',state:'Mise à jour',tone:'review',action:'Voir le paquet',favorite:true},
  {id:'platform',name:'KYA-Platform MCP',type:'MCP',icon:'link',owner:'CVSI',version:'0.1.0',description:'Vos capacités autorisées depuis Claude, ChatGPT ou Codex.',state:'Connecté',tone:'',action:'Configurer le profil',favorite:true},
  {id:'frappe',name:'Frappe / ERPNext',type:'App',icon:'cube',owner:'Équipe Systèmes',version:'Référencé',description:'Accéder au système métier et à ses espaces de travail.',state:'Disponible',tone:'',action:'Voir l’application',favorite:false},
  {id:'documents',name:'Documents KYA',type:'Skill',icon:'doc',owner:'Communication',version:'0.1.0',description:'Préparer des documents conformes aux modèles du Groupe.',state:'En revue',tone:'review',action:'Examiner la méthode',favorite:false},
  {id:'projects',name:'Référentiel projets',type:'Donnée',icon:'folder',owner:'KYA Core',version:'Référence partagée',description:'Retrouver les projets et leurs informations de référence.',state:'Lecture',tone:'neutral',action:'Consulter le contrat',favorite:false},
];
const contexts = [
  {name:'KYA-Energy Group',unit:'Groupe · CVSI',role:'Administrateur du socle',title:'Vous travaillez au niveau Groupe'},
  {name:'KYA-Energy Togo',unit:'Direction Solutions & Technologies',role:'Contributeur',title:'Vous travaillez dans KYA-Energy Togo'},
  {name:'KYA-Energy Group',unit:'Espace stagiaires',role:'Lecteur',title:'Vous travaillez dans l’espace stagiaires'},
];
let filter = 'all', view = 'all', activeContext = 0, toastTimer;
const detail = $('#detail-dialog');
function notify(message){$('#toast').textContent=message;$('#toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),3000)}
function show(content){$('#detail-content').innerHTML=`<div class="detail-body">${content}<div class="detail-note">Prototype de design. Les données sont illustratives ; aucune action n’est envoyée à un service réel.</div></div>`;if(!detail.open)detail.showModal()}
function render(){
  const query=$('#filter').value.trim().toLocaleLowerCase('fr');
  const visible=resources.filter(r=>(filter==='all'||r.type===filter)&&(view!=='favorite'||r.favorite)&&`${r.name} ${r.description} ${r.owner}`.toLocaleLowerCase('fr').includes(query));
  $('#capability-list').innerHTML=visible.map(r=>`<article class="resource"><button class="resource-main" data-resource="${r.id}"><span class="resource-icon ${r.type==='Skill'?'skill':r.type==='App'?'app':r.type==='Donnée'?'data':''}">${icon(r.icon)}</span><span class="resource-copy"><strong>${r.name}</strong><small>${r.description}</small><span class="resource-meta">${r.type}<i>·</i>${r.owner}</span></span></button><span class="state ${r.tone}"><i></i>${r.state}</span><div class="row-actions"><button class="icon-button favorite" data-favorite="${r.id}" aria-label="${r.favorite?'Retirer des':'Ajouter aux'} favoris : ${r.name}" aria-pressed="${r.favorite}">${icon('pin')}</button><button class="icon-button" data-resource="${r.id}" aria-label="Voir ${r.name}">${icon('right')}</button></div></article>`).join('');
  $('#empty').hidden=visible.length>0;$('#result-count').textContent=`${visible.length} ressource${visible.length!==1?'s':''}`;$('#favorite-count').textContent=resources.filter(r=>r.favorite).length;
  document.querySelectorAll('[data-filter]').forEach(b=>{const active=b.dataset.filter===filter;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active))});
}
function setView(next){view=next;filter=['App','MCP','Skill','Donnée'].includes(next)?next:'all';$('#filter').value='';const names={all:'Mon espace',catalog:'Catalogue',favorite:'Mes favoris',App:'Applications',MCP:'MCP & connexions',Skill:'Skills',Donnée:'Données'};$('#breadcrumb-page').textContent=names[next];$('#page-title').textContent=next==='all'?'Votre espace de travail.':names[next];$('#capabilities-title').textContent=next==='favorite'?'Mes favoris':next==='catalog'?'Explorer les capacités':'Mes capacités';document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===next);if(b.dataset.view===next)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});closeMenu();render()}
function openContext(){ $('#contexts').innerHTML=contexts.map((c,i)=>`<button class="context-option" data-context="${i}" aria-pressed="${i===activeContext}">${icon('org')}<span><strong>${c.name}</strong><small>${c.unit} · ${c.role}</small></span>${i===activeContext?icon('check'):icon('right')}</button>`).join('');$('#context-dialog').showModal() }
function connect(client){show(`<span class="resource-icon">${icon('link')}</span><h2>${client?`Connecter ${client}`:'Votre IA, vos outils KYA.'}</h2><p>Choisissez votre environnement. KYA-Platform détermine les outils disponibles selon votre contexte.</p>${client?`<dl><div><dt>Environnement</dt><dd>${client}</dd></div><div><dt>Entité</dt><dd>${contexts[activeContext].name}</dd></div><div><dt>Accès</dt><dd>Selon votre rôle</dd></div></dl><h3>Une connexion, des accès maîtrisés</h3><ul><li>Authentification avec votre compte KYA.</li><li>Choix des outils parmi ceux autorisés.</li><li>Révocation depuis votre espace.</li></ul><button class="button primary" data-simulate="Le parcours de connexion sera branché après validation du design.">Prévisualiser la connexion</button>`:['Claude','ChatGPT','Codex'].map(c=>`<button class="client-choice" data-client="${c}"><span class="client-logo">${c.slice(0,1)}</span><span>${c}</span>${icon('right')}</button>`).join('')}`)}
const pages={
  studio:['Studio Skills & MCP','Transformer une méthode ou un service en capacité réutilisable.','Structure du paquet, ressources, code, tests, revue et publication.'],
  organization:['Organisation & équipes','Représenter les entités, les unités et les affectations.','Arborescence du Groupe, équipes, responsabilités et périodes de validité.'],
  permissions:['Identités & accès','Comprendre qui peut agir, sur quelle ressource et dans quel contexte.','Rôles, politiques, accès temporaires et provenance des droits.'],
  data:['Données & contrats','Partager des références dont la provenance et la structure sont connues.','Sources, schémas, contrats, ingestion et traçabilité.'],
  audit:['Activité & audit','Retrouver les actions et les décisions du socle.','Acteur, contexte, ressource, résultat et preuve.'],
  secrets:['Intégrations & secrets','Administrer les connexions techniques.','Références de secrets, périmètres et usages autorisés. Les valeurs restent dans le coffre.'],
  versions:['Versions & publications','Examiner les capacités avant leur mise à disposition.','Brouillons, validations, approbations, versions publiées et retrait.'],
  deploy:['Déploiements','Suivre les environnements des applications.','Branches, tests et état des déploiements autorisés.'],
  help:['Aide & documentation','Comprendre comment utiliser et construire avec KYA-Platform.','Guides de prise en main, modèles maîtres, conventions et références.'],
  profile:['Votre compte','Jean-Claude Messan','Le rôle affiché provient du contexte de démonstration sélectionné.'],
  review:['KYA Design System','Une version est proposée à votre revue.','Examiner les modifications, les résultats des tests et les médias avant toute approbation.'],
  access:['Demande d’accès au référentiel projets','Équipe Solutions & Technologies','Vérifier le périmètre, la durée et les ressources demandées avant de décider.'],
  notifications:['À votre attention','Deux exemples de décisions à examiner.','Publication du KYA Design System et demande d’accès au référentiel projets.'],
};
function closeMenu(){$('.sidebar').classList.remove('open');$('#mobile-scrim').hidden=true;$('#menu-button').setAttribute('aria-expanded','false')}
document.addEventListener('click',event=>{
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.filter){filter=button.dataset.filter;render()}
  if(button.dataset.view)setView(button.dataset.view);
  if(button.dataset.resource){const r=resources.find(x=>x.id===button.dataset.resource);show(`<span class="resource-icon ${r.type==='Skill'?'skill':''}">${icon(r.icon)}</span><h2>${r.name}</h2><p>${r.description}</p><dl><div><dt>Type</dt><dd>${r.type}</dd></div><div><dt>Responsable</dt><dd>${r.owner}</dd></div><div><dt>Version de démonstration</dt><dd>${r.version}</dd></div><div><dt>État</dt><dd>${r.state}</dd></div></dl><h3>Contexte d’utilisation</h3><p>${contexts[activeContext].name} · ${contexts[activeContext].unit}</p><button class="button primary" data-simulate="La destination métier sera reliée après validation de cette interface.">${r.action}${icon('right')}</button>`)}
  if(button.dataset.favorite){const r=resources.find(x=>x.id===button.dataset.favorite);r.favorite=!r.favorite;render();notify(r.favorite?'Capacité ajoutée à vos favoris.':'Capacité retirée de vos favoris.')}
  if(button.dataset.context!==undefined){activeContext=Number(button.dataset.context);const c=contexts[activeContext];$('#scope-name').textContent=c.name;$('#scope-unit').textContent=c.unit;$('#profile-role').textContent=c.role;$('#context-title').textContent=c.title;$('#context-description').textContent=`${c.unit} · ${c.role}`;$('#context-dialog').close();notify('Contexte de démonstration modifié.')}
  if(button.dataset.client)connect(button.dataset.client);
  if(button.dataset.detail){const [title,description,body]=pages[button.dataset.detail];show(`<span class="resource-icon">${icon('shield')}</span><h2>${title}</h2><p>${description}</p><h3>Ce que vous retrouverez ici</h3><p>${body}</p>`)}
  if(button.dataset.simulate)notify(button.dataset.simulate);
});
$('#filter').addEventListener('input',render);
$('#reset').addEventListener('click',()=>{filter='all';$('#filter').value='';render()});
$('#scope-button').addEventListener('click',openContext);$('#change-context').addEventListener('click',openContext);
$('#connect-button').addEventListener('click',()=>connect());
$('#search-launch').addEventListener('click',()=>{$('#filter').focus();$('#filter').scrollIntoView({block:'center'})});
$('#catalog-button').addEventListener('click',()=>setView('catalog'));
$('#list-settings').addEventListener('click',()=>notify('Favoris, filtres et détails sont interactifs dans cette maquette.'));
$('#foundation-toggle').addEventListener('click',()=>{const extra=$('#admin-extra');extra.hidden=!extra.hidden;$('#foundation-toggle').setAttribute('aria-expanded',String(!extra.hidden))});
$('#admin-nav').addEventListener('click',()=>{closeMenu();$('#admin-extra').hidden=false;$('#foundation-toggle').setAttribute('aria-expanded','true');$('#foundation').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'center'})});
$('#menu-button').addEventListener('click',()=>{const open=!$('.sidebar').classList.contains('open');$('.sidebar').classList.toggle('open',open);$('#mobile-scrim').hidden=!open;$('#menu-button').setAttribute('aria-expanded',String(open))});
$('#mobile-scrim').addEventListener('click',closeMenu);
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#filter').focus();$('#filter').scrollIntoView({block:'center'})}if(e.key==='Escape')closeMenu()});
render();
