'use strict';
const byId = identity => document.getElementById(identity);
const tabs = ['intake', 'brief', 'paths', 'court', 'research'];
const terminalStates = new Set(['completed', 'failed', 'cancelled', 'interrupted']);
const dateFields = ['cheque_date', 'presented_on', 'valid_until', 'memo_received_on', 'notice_sent_on', 'notice_received_on', 'complaint_filed_on'];
const state = {config: null, current: null, history: [], activeId: null, tab: 'intake', busy: false, poll: null, preview: null, previewVersion: 0, selectionVersion: 0, selectedSource: null, sources: new Map(), playback: null, playing: false, turnIndex: 0, courtPath: 1};
const node = (tag, text, className) => { const element = document.createElement(tag); if (text !== undefined) element.textContent = text; if (className) element.className = className; return element; };
const icon = name => { const element = node('i'); element.dataset.lucide = name; element.setAttribute('aria-hidden', 'true'); return element; };
const icons = () => MisofishAssets.createIcons({icons: MisofishAssets.icons});
const localDate = (offset = 0) => { const value = new Date(); value.setDate(value.getDate() + offset); return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`; };
const formatDate = value => value ? new Intl.DateTimeFormat('en-IN', {day: 'numeric', month: 'short', year: 'numeric'}).format(new Date(value + 'T12:00:00')) : 'Not confirmed';
const assessmentLabel = value => ({supported: 'Supported in rehearsal', contested: 'Contested', needs_evidence: 'Evidence needed', pending: 'Pending', running: 'In progress'}[value] || value);
const statusLabel = value => ({researching: 'Analysis in progress', completed: 'Brief ready', failed: 'Analysis stopped', cancelled: 'Stopped', interrupted: 'Interrupted'}[value] || 'New case');
function error(message) { byId('app-error').textContent = message; byId('app-error').hidden = !message; }
async function api(path, body) {
  const response = await fetch(path, {...(body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}), signal: AbortSignal.timeout(20000)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
  return result;
}
function facts() {
  const form = byId('case-form');
  return Object.fromEntries([...dateFields, 'debt_evidence', 'payment_received'].map(name => [name, form.elements.namedItem(name).value]));
}
function controls() {
  const run = state.current, active = Boolean(state.activeId), selectedActive = run?.id === state.activeId;
  byId('analyse-case').disabled = !state.config?.configured || !state.config?.legal_corpus.available || state.busy || active;
  byId('analyse-label').textContent = run ? 'Analyse as new case' : 'Analyse case';
  byId('stop-analysis').hidden = !selectedActive;
  byId('stop-analysis').disabled = state.busy;
  byId('delete-case').hidden = !run;
  byId('delete-case').disabled = state.busy || selectedActive;
  byId('download-brief').hidden = !run;
  if (run) byId('download-brief').href = `/api/cases/${run.id}/export`;
}
function showTab(name, focus = false) {
  if (name !== 'court') { state.playing = false; clearTimeout(state.playback); }
  state.tab = name;
  for (const tab of tabs) {
    byId('view-' + tab).hidden = tab !== name;
    byId('tab-' + tab).setAttribute('aria-selected', String(tab === name));
    byId('tab-' + tab).tabIndex = tab === name ? 0 : -1;
  }
  byId('page-title').textContent = {intake: 'Case details', brief: 'Case-readiness brief', paths: 'Argument paths', court: 'Courtroom rehearsal', research: 'Research & sources'}[name];
  if (focus) byId('tab-' + name).focus();
  if (name === 'court') { renderCourt(); ConversationRoom.wake(); }
}
function sourceButton(identity, label) {
  const button = node('button', label || identity, 'source-link'); button.type = 'button';
  button.addEventListener('click', () => inspectSource(identity)); return button;
}
function renderCalendar(host, timeline) {
  host.replaceChildren(); if (!timeline) return;
  const counts = node('div', undefined, 'calendar-counts');
  for (const [key, label] of [['checked', 'Input checks met'], ['attention', 'Need review'], ['missing', 'To confirm']]) {
    const item = node('div'); item.append(node('strong', String(timeline[key]), 'text-' + key), node('span', label)); counts.append(item);
  }
  host.append(counts);
  for (const item of timeline.checks) {
    const row = node('div', undefined, 'check-row'), content = node('div'), symbol = icon({checked: 'check-circle-2', attention: 'triangle-alert', missing: 'circle-help'}[item.status]);
    symbol.classList.add('text-' + item.status);
    content.append(node('span', {checked: 'Supplied input meets base check', attention: 'Professional review needed', missing: 'Not confirmed'}[item.status], 'check-state text-' + item.status), node('h3', item.title), node('p', item.detail), sourceButton(item.source_id, item.source_id.includes('s142') ? 'NI Act · Section 142' : 'NI Act · Section 138'));
    row.append(symbol, content); host.append(row);
  }
  if (timeline.deadlines.length) {
    const heading = node('h3', 'Base calendar dates'); heading.className = 'section-break'; host.append(heading);
    for (const item of timeline.deadlines) {
      const row = node('div', undefined, 'deadline-row'), title = node('span', item.title);
      title.append(node('small', item.days_remaining < 0 ? `${Math.abs(item.days_remaining)} days before assessment` : `${item.days_remaining} days from assessment`));
      row.append(title, node('strong', formatDate(item.date))); host.append(row);
    }
  }
  host.append(node('p', timeline.caution, 'calendar-caution')); icons();
}
async function previewCalendar() {
  const version = ++state.previewVersion, asOf = byId('assessment-date').value;
  if (!asOf) { byId('calendar-preview').replaceChildren(); byId('calendar-error').textContent = 'An assessment date is required.'; byId('calendar-error').hidden = false; return; }
  try {
    const timeline = await api('/api/cases/timeline', {facts: facts(), as_of: asOf});
    if (version !== state.previewVersion) return;
    byId('calendar-error').hidden = true; renderCalendar(byId('calendar-preview'), timeline);
  } catch (exception) {
    if (version !== state.previewVersion) return;
    byId('calendar-preview').replaceChildren(); byId('calendar-error').textContent = exception.message; byId('calendar-error').hidden = false;
  }
}
function renderHistory() {
  const host = byId('case-history'); host.replaceChildren();
  if (!state.history.length) host.append(node('p', 'No saved cases.', 'muted'));
  for (const run of state.history) {
    const button = node('button', undefined, 'history-case'); button.type = 'button'; button.setAttribute('aria-current', String(state.current?.id === run.id));
    button.append(node('strong', run.title), node('small', `${statusLabel(run.status)} · ${run.side === 'complainant' ? 'Recipient' : 'Issuer'}`));
    button.addEventListener('click', () => selectCase(run.id)); host.append(button);
  }
}
async function refreshHistory() {
  state.history = await api('/api/cases');
  state.activeId = state.history.find(run => !terminalStates.has(run.status))?.id || null;
  renderHistory(); controls();
}
function fillForm(request) {
  const form = byId('case-form'); form.reset();
  byId('assessment-date').value = request?.as_of || localDate();
  if (request) {
    form.elements.namedItem('side').value = request.side; byId('case-scenario').value = request.scenario; byId('case-evidence').value = request.evidence;
    for (const [key, value] of Object.entries(request.facts)) form.elements.namedItem(key).value = value;
  }
  byId('case-consent').checked = false; byId('file-status').textContent = 'Text extracts only. Original documents are not authenticated.';
  previewCalendar();
}
function listSection(title, values) {
  const section = node('section', undefined, 'brief-section'), list = node('ul'); section.append(node('h2', title));
  for (const value of values) list.append(node('li', value)); section.append(list); return section;
}
function renderBrief() {
  const host = byId('brief-content'), run = state.current; host.replaceChildren(); host.className = '';
  if (!run) { host.className = 'empty-state'; host.append(icon('clipboard-list'), node('h2', 'No case brief yet')); return; }
  const layout = node('div', undefined, 'brief-layout'), main = node('div'), side = node('aside', undefined, 'brief-sidebar');
  if (run.brief) {
    const brief = run.brief, branch = run.branches.find(item => item.id === brief.recommended_branch);
    main.append(node('p', brief.summary, 'brief-lead'));
    const recommendation = node('div', undefined, 'recommendation'); recommendation.append(node('p', 'Preparation priority', 'eyebrow'), node('h3', branch ? `Path ${branch.id} · ${branch.title}` : 'Further evidence required'), node('p', brief.recommendation_reason));
    const open = node('button', undefined, 'text-button'); open.type = 'button'; open.append(icon('git-branch'), node('span', 'Review argument paths')); open.addEventListener('click', () => showTab('paths')); recommendation.append(open); main.append(recommendation);
    main.append(listSection('Evidence & next steps', brief.next_steps), listSection('Questions for your advocate', brief.questions_for_lawyer));
    for (const [title, text] of [['Voluntary resolution', brief.settlement_option], ['Limits of this analysis', brief.limitations]]) { const section = node('section', undefined, 'brief-section'); section.append(node('h2', title), node('p', text)); main.append(section); }
  } else {
    main.append(node('h2', terminalStates.has(run.status) ? 'No completed brief' : 'Preparing the case brief'), node('p', run.error || run.phase, 'muted'));
    if (run.error) main.append(node('p', 'Saved calendar checks, sources, and completed statements remain available.', 'small muted'));
  }
  side.append(node('h2', 'Supplied inputs & timing')); const calendar = node('div'); side.append(calendar); renderCalendar(calendar, run.timeline); layout.append(main, side); host.append(layout);
}
function quoteDetails(citations) {
  const details = node('details', undefined, 'citation-quotes'), matched = citations.filter(item => item.matched).length;
  details.append(node('summary', `${citations.length} source quotation${citations.length === 1 ? '' : 's'} · ${matched} text matched`));
  if (!citations.length) details.append(node('p', 'No source quotation supplied for this statement.', 'quote-note'));
  for (const citation of citations) {
    details.append(sourceButton(citation.source_id), node('span', citation.matched ? ' · Quote matched' : ' · Unmatched quotation', 'quote-state' + (citation.matched ? '' : ' unmatched')), node('blockquote', citation.quote), node('p', citation.note, 'quote-note'));
  }
  return details;
}
function statement(turn) {
  const host = node('article', undefined, 'path-turn'), heading = node('div', undefined, 'turn-heading');
  heading.append(node('strong', turn.role), node('span', assessmentLabel(turn.assessment), 'assessment ' + turn.assessment)); host.append(heading, node('p', turn.text));
  for (const guardrail of turn.guardrails || []) host.append(node('p', guardrail, 'alert warning'));
  const preparation = node('div', undefined, 'preparation-point'); preparation.append(node('strong', 'What to prepare'), node('p', turn.what_to_say), node('p', turn.why_it_matters, 'small muted')); host.append(preparation, quoteDetails(turn.citations)); return host;
}
function renderPaths() {
  const host = byId('paths-content'), branches = state.current?.branches || []; host.replaceChildren(); host.className = branches.length ? '' : 'empty-state';
  if (!branches.length) { host.append(node('h2', 'No argument paths yet')); return; }
  for (const branch of branches) {
    const recommended = state.current.brief?.recommended_branch === branch.id, article = node('article', undefined, 'path-card' + (recommended ? ' recommended' : ''));
    const heading = node('div', undefined, 'path-header'), title = node('div'); title.append(node('span', `Path ${branch.id}${recommended ? ' / Preparation priority' : ''}`, 'path-number'), node('h2', branch.title));
    heading.append(title, node('span', assessmentLabel(branch.assessment || branch.status), 'assessment ' + (branch.assessment || branch.status))); article.append(heading, node('p', branch.question, 'path-question'));
    const context = node('div', undefined, 'path-facts');
    for (const [label, values] of [['Hypotheses, not facts', branch.assumptions], ['Evidence needed', branch.evidence_needed]]) { const section = node('div'), list = node('ul'); section.append(node('h3', label)); for (const value of values) list.append(node('li', value)); section.append(values.length ? list : node('p', 'No additional assumptions stated.', 'muted')); context.append(section); }
    article.append(context);
    for (const turn of branch.turns) article.append(statement(turn));
    const play = node('button', undefined, 'text-button'); play.type = 'button'; play.disabled = !branch.turns.length; play.append(icon('play'), node('span', 'Open courtroom rehearsal')); play.addEventListener('click', () => { state.courtPath = branch.id; state.turnIndex = 0; state.playing = false; ConversationRoom.restartSpeech(); showTab('court'); }); article.append(play); host.append(article);
  }
}
function renderSourceList() {
  const host = byId('source-list'), query = byId('source-search').value.toLowerCase(), kind = byId('source-kind').value; host.replaceChildren();
  const sources = [...state.sources.values()].filter(source => (kind === 'all' || source.kind === kind) && [source.title, source.court, source.id, source.citation].join(' ').toLowerCase().includes(query));
  for (const source of sources) {
    const button = node('button', undefined, 'source-item'); button.type = 'button'; button.setAttribute('aria-pressed', String(state.selectedSource === source.id));
    button.append(node('strong', source.title), node('small', source.kind === 'statute' ? `Statute · Section ${source.section_number || 'not stated'}` : `${source.court || 'Court not stated'} · ${source.citation || 'Citation not stated'}`), node('small', source.id)); button.addEventListener('click', () => inspectSource(source.id)); host.append(button);
  }
  if (!sources.length) host.append(node('p', state.sources.size ? 'No matching sources.' : 'No sources retrieved.', 'muted'));
}
async function inspectSource(identity) {
  showTab('research'); state.selectedSource = identity; const host = byId('source-detail'); host.replaceChildren(node('h3', 'Opening source'));
  try {
    const source = state.sources.get(identity) || await api('/api/authorities/' + encodeURIComponent(identity));
    if (state.selectedSource !== identity) return; state.sources.set(source.id, source);
    host.replaceChildren(node('p', source.kind === 'statute' ? 'Statutory text' : 'Judgment extract', 'eyebrow'), node('h3', source.title), node('p', source.court || `Section ${source.section_number || 'not stated'}`, 'small muted'), node('p', source.id, 'source-id'), node('pre', source.text));
    if (source.source_url) { const url = new URL(source.source_url); if (url.protocol === 'https:') { const link = node('a', 'Original source'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; host.append(link); } }
    host.append(node('p', 'Extract from the local corpus. Citation treatment and current legal validity require professional review.', 'quote-note')); renderSourceList();
  } catch (exception) { if (state.selectedSource === identity) host.replaceChildren(node('h3', 'Source unavailable'), node('p', exception.message, 'muted')); }
}
function renderResearch() {
  const run = state.current, quotes = (run?.actions || []).flatMap(turn => turn.citations), matched = quotes.filter(item => item.matched).length;
  byId('quote-summary').textContent = quotes.length ? `${matched}/${quotes.length} quotations text-matched · legal interpretation unchecked` : 'No quotations recorded';
  renderSourceList(); const host = byId('agent-trace'); host.replaceChildren();
  const trace = run?.trace || []; byId('tool-count').textContent = `${trace.length} tool results`;
  for (const item of trace) {
    const row = node('li'), content = node('div'); content.append(node('h3', {check_deadlines: 'Calendar tool', read_authority: 'Read authority', search_statutes: 'Statute search', search_precedents: 'Precedent search'}[item.tool] || item.tool), node('p', item.summary));
    for (const identity of item.source_ids || []) content.append(sourceButton(identity)); row.append(node('span', String(item.id), 'trace-marker'), content, node('small', item.branch ? `Path ${item.branch}` : 'Research')); host.append(row);
  }
  if (!trace.length) host.append(node('li', 'No tool results recorded.', 'muted'));
}
function courtTurns() { return (state.current?.actions || []).filter(turn => turn.round === state.courtPath); }
function renderCourt() {
  clearTimeout(state.playback); const run = state.current;
  const select = byId('court-path'); select.replaceChildren();
  for (const branch of run?.branches || []) select.append(new Option(`Path ${branch.id} · ${branch.title}`, String(branch.id)));
  if (!select.options.length) select.append(new Option('No paths recorded', '1'));
  select.value = String(state.courtPath); const turns = courtTurns(); state.turnIndex = Math.min(state.turnIndex, Math.max(0, turns.length - 1));
  const turn = turns[state.turnIndex];
  if (run) ConversationRoom.render(run, [], turn || null, {paused: !state.playing, speed: Number(byId('court-speed').value)});
  byId('court-statement').replaceChildren(turn ? statement(turn) : node('p', 'No statements recorded.', 'muted'));
  byId('court-position').textContent = turn ? `${state.turnIndex + 1} / ${turns.length} · ${turn.role}` : 'No statements recorded';
  byId('court-play').replaceChildren(icon(state.playing ? 'pause' : 'play')); byId('court-play').setAttribute('aria-label', state.playing ? 'Pause rehearsal' : 'Play rehearsal'); byId('court-play').title = state.playing ? 'Pause rehearsal' : 'Play rehearsal'; byId('court-play').disabled = !turn;
  byId('court-next').disabled = !turn || state.turnIndex >= turns.length - 1; icons();
  if (state.playing && turn) state.playback = setTimeout(advanceCourt, Math.max(100, ConversationRoom.remaining()));
}
function advanceCourt() {
  if (state.tab !== 'court') return;
  if (ConversationRoom.remaining() > 100) { state.playback = setTimeout(advanceCourt, Math.max(100, ConversationRoom.remaining())); return; }
  if (state.turnIndex < courtTurns().length - 1) state.turnIndex++; else state.playing = false; renderCourt();
}
function renderRun() {
  const run = state.current; byId('case-status').textContent = statusLabel(run?.status);
  byId('case-subtitle').textContent = run ? `${run.side === 'complainant' ? 'Cheque recipient' : 'Cheque issuer'} · Assessed ${formatDate(run.request.as_of)}` : 'Cheque dishonour';
  byId('analysis-progress').hidden = !run || terminalStates.has(run.status);
  if (run) { byId('analysis-phase').textContent = run.phase; byId('analysis-count').textContent = `${run.actions.length}/9 turns · ${run.model_calls} model calls`; byId('analysis-meter').value = run.actions.length; for (const source of run.sources) state.sources.set(source.id, source); }
  renderBrief(); renderPaths(); renderResearch(); if (state.tab === 'court') renderCourt(); controls(); icons();
}
async function pollActive() {
  clearTimeout(state.poll); const identity = state.activeId; if (!identity) return;
  try {
    const run = await api('/api/cases/' + identity);
    if (state.current?.id === identity) { state.current = run; renderRun(); if (run.error) error(run.error); }
    if (terminalStates.has(run.status)) { await refreshHistory(); return; }
  } catch (exception) { error(exception.message); }
  if (state.activeId) state.poll = setTimeout(pollActive, 1800);
}
async function selectCase(identity) {
  const version = ++state.selectionVersion;
  state.busy = true; controls(); error('');
  try {
    const run = await api('/api/cases/' + identity); if (version !== state.selectionVersion) return;
    state.current = run; state.sources.clear(); state.selectedSource = null; state.turnIndex = 0; state.courtPath = 1; state.playing = false; ConversationRoom.reset();
    byId('source-detail').replaceChildren(node('h3', 'No source selected')); fillForm(run.request); renderRun(); renderHistory(); showTab('brief');
    history.replaceState(null, '', '?case=' + encodeURIComponent(identity));
  } catch (exception) { if (version === state.selectionVersion) error(exception.message); }
  finally { if (version === state.selectionVersion) { state.busy = false; controls(); } }
}
function newCase() {
  state.selectionVersion++; state.busy = false;
  state.current = null; state.sources.clear(); state.selectedSource = null; state.playing = false; clearTimeout(state.playback); ConversationRoom.reset();
  byId('source-detail').replaceChildren(node('h3', 'No source selected')); fillForm(null); error(''); renderRun(); renderHistory(); showTab('intake'); history.replaceState(null, '', '/');
}
for (const tab of tabs) byId('tab-' + tab).addEventListener('click', () => { if (tab !== 'court') { state.playing = false; clearTimeout(state.playback); } showTab(tab); });
byId('case-form').addEventListener('change', () => { clearTimeout(state.preview); state.preview = setTimeout(previewCalendar, 100); });
document.querySelector('.case-tabs').addEventListener('keydown', event => {
  if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault(); const current = tabs.indexOf(state.tab); const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length; showTab(tabs[next], true);
});
byId('new-case').addEventListener('click', newCase);
byId('refresh-cases').addEventListener('click', () => refreshHistory().then(pollActive).catch(exception => error(exception.message)));
byId('load-sample').addEventListener('click', () => {
  fillForm({side: 'complainant', as_of: localDate(), scenario: 'A small textile supplier received a post-dated cheque for unpaid invoices. The cheque was returned with a stop-payment instruction. The customer says it was only a security cheque and disputes the quality of the goods. The supplier reports that a written demand notice was delivered and payment remains unpaid. The supplied dates need confirmation against the original bank and dispatch records.', evidence: 'Reported records: supply agreement, invoices, delivery acknowledgements and bank return memo. The customer disputes the quality of goods. Notice service and the outstanding balance need documentary confirmation.', facts: {cheque_date: localDate(-75), presented_on: localDate(-45), valid_until: localDate(10), memo_received_on: localDate(-44), notice_sent_on: localDate(-20), notice_received_on: localDate(-17), complaint_filed_on: '', debt_evidence: 'available', payment_received: 'no'}});
});
byId('evidence-file').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  if (file.size > 64000 || !/\.(txt|md|csv)$/i.test(file.name)) { error('Choose a text, Markdown or CSV extract under 64 KB.'); event.target.value = ''; return; }
  const text = await file.text(); if (text.length > 16000) { error('The supporting text must contain at most 16,000 characters.'); return; }
  byId('case-evidence').value = text; byId('file-status').textContent = `${file.name} · ${text.length.toLocaleString()} characters`; error('');
});
byId('case-form').addEventListener('submit', async event => {
  event.preventDefault(); if (!event.target.reportValidity() || state.busy || state.activeId) return;
  state.busy = true; error(''); controls();
  try {
    const body = {scenario: byId('case-scenario').value, side: event.target.elements.namedItem('side').value, facts: facts(), as_of: byId('assessment-date').value, evidence: byId('case-evidence').value, consent: byId('case-consent').checked};
    const run = await api('/api/cases', body); state.current = run; state.activeId = run.id; state.sources.clear(); state.selectedSource = null; state.courtPath = 1; state.turnIndex = 0; state.playing = false; ConversationRoom.reset(); renderRun(); showTab('brief'); history.replaceState(null, '', '?case=' + run.id); await refreshHistory(); pollActive();
  } catch (exception) { error(exception.message); }
  finally { state.busy = false; controls(); }
});
byId('stop-analysis').addEventListener('click', async () => {
  if (!state.current) return; state.busy = true; controls();
  try { const result = await api(`/api/cases/${state.current.id}/cancel`, {}); byId('analysis-phase').textContent = result.message; } catch (exception) { error(exception.message); } finally { state.busy = false; controls(); }
});
byId('delete-case').addEventListener('click', () => byId('delete-dialog').showModal());
byId('confirm-delete').addEventListener('click', async () => {
  if (!state.current || state.current.id === state.activeId) return;
  const button = byId('confirm-delete'); button.disabled = true;
  try { await api(`/api/cases/${state.current.id}/delete`, {}); byId('delete-dialog').close(); newCase(); await refreshHistory(); } catch (exception) { error(exception.message); byId('delete-dialog').close(); } finally { button.disabled = false; }
});
byId('source-search').addEventListener('input', renderSourceList); byId('source-kind').addEventListener('change', renderSourceList);
byId('court-path').addEventListener('change', event => { state.courtPath = Number(event.target.value); state.turnIndex = 0; state.playing = false; ConversationRoom.restartSpeech(); renderCourt(); });
byId('court-play').addEventListener('click', () => { state.playing = !state.playing; renderCourt(); });
byId('court-next').addEventListener('click', () => { state.turnIndex++; state.playing = false; renderCourt(); });
byId('court-speed').addEventListener('change', renderCourt);
window.addEventListener('persona-select', event => {
  const index = courtTurns().findIndex(turn => turn.agent_id === event.detail);
  if (index < 0) return;
  state.turnIndex = index; state.playing = false; ConversationRoom.select(event.detail); renderCourt();
});
async function initialize() {
  icons(); fillForm(null);
  try {
    state.config = await api('/api/config'); byId('provider-warning').hidden = state.config.configured;
    byId('provider-state').textContent = state.config.configured ? state.config.model : 'AI provider not configured';
    byId('corpus-state').textContent = state.config.legal_corpus.available ? `${state.config.legal_corpus.judgment_cases.toLocaleString()} local precedents` : 'Legal corpus unavailable';
    await refreshHistory(); const identity = new URLSearchParams(location.search).get('case') || state.activeId || state.history[0]?.id;
    if (identity) await selectCase(identity); pollActive();
  } catch (exception) { error(exception.message); }
  controls();
}
initialize();