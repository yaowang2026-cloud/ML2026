// Application language only; source evidence and user-entered data stay unchanged.
let language = localStorage.getItem('dayone-language') === 'en' ? 'en' : 'fr';
const english = {"Assistant maternité": "Maternity assistant", "● En ligne": "● Online", "● Backend connecté": "● Backend connected", "● Backend indisponible": "● Backend unavailable", "Écrire un message...": "Type a message...", "Ajouter une photo": "Add a photo", "Traitement en cours… veuillez patienter": "Processing… please wait", "Nouvelle visite : ajoutez toutes les photos d’un même dossier, dans l’ordre.": "New visit: add all photos for one record, in page order.", "Prendre une photo": "Take a photo", "Choisir des images": "Choose images", "Analyser les pages": "Analyze pages", "Nouvelle visite": "New visit", "Envoi désactivé jusqu’à la fin du traitement.": "Sending is disabled until processing finishes.", "Veuillez patienter…": "Please wait…", "Analyse terminée. Vérifiez les résultats ci-dessous.": "Analysis complete. Review the results below.", "Analyse terminée. Les champs sont prêts à être vérifiés.": "Analysis complete. The fields are ready for review.", "Extraction des 31 champs à partir du texte…": "Extracting the 31 fields from the text…", "Vérification des valeurs et classement : acceptés / à vérifier / manquants…": "Validating values and grouping fields: accepted / review / missing…", "Acceptés": "Accepted", "À vérifier": "Review", "Manquants": "Missing", "Vérifié": "Verified", "Réponse requise": "Response required", "Valeur": "Value", "Preuve": "Evidence", "Votre correction (texte ou valeur)": "Your correction (text or value)", "Confirmer": "Confirm", "Interpréter ma correction": "Interpret my correction", "Laisser vide": "Leave blank", "Confirmer le dossier et enregistrer le CSV": "Confirm record and save CSV", "Correction interprétée. Confirmez la valeur proposée.": "Correction interpreted. Confirm the proposed value.", "Champ mis à jour.": "Field updated.", "Enregistrement du dossier dans le CSV…": "Saving the record to CSV…", "Dossier enregistré dans le CSV.": "Record saved to CSV.", "Dossier enregistré dans registry.csv.": "Record saved to registry.csv.", "Chargement du dossier…": "Loading record…", "Dossier chargé.": "Record loaded.", "Commencez une nouvelle visite pour analyser d’autres photos.": "Start a new visit to analyze more photos.", "Ajoutez au moins une photo.": "Add at least one photo.", "Commencer une nouvelle visite ? Le dossier actuel reste conservé sur le serveur.": "Start a new visit? The current record remains stored on the server.", "Saisissez votre réponse dans le champ concerné, puis choisissez « Interpréter ma correction ».": "Enter your response in the relevant field, then choose “Interpret my correction”.", "La recherche par patiente n’est pas encore connectée. Le dossier en cours est restauré lors du rechargement de cette page.": "Patient search is not connected yet. Reloading this page restores the current record.", "Saisissez une valeur valide ou choisissez « Laisser vide ».": "Enter a valid value or choose “Leave blank”.", "Confirmez la valeur interprétée.": "Confirm the interpreted value.", "Valeur ou preuve à vérifier.": "Value or evidence needs review.", "Une réponse de 1 à 4000 caractères est requise.": "A response of 1 to 4000 characters is required.", "Dossier introuvable.": "Record not found.", "Le traitement a échoué. Vérifiez Ollama et réessayez. Aucun succès de sauvegarde confirmé.": "Processing failed. Check Ollama and retry. Saving has not been confirmed.", "Dossier enregistré ou modifié. Rechargez le dossier.": "Record saved or changed. Reload the record.", "Le dossier a changé. Rechargez-le.": "The record changed. Reload it.", "Confirmez, corrigez ou laissez explicitement vide chaque champ à vérifier/manquant.": "Confirm, correct or explicitly leave blank every review/missing field."};
function tr(text) {
  if (language !== 'en') return text;
  if (english[text]) return english[text];
  return String(text)
    .replace(/^Analyse de (\d+) page\(s\) en cours…$/, 'Analyzing $1 page(s)…')
    .replace(/^(\d+) page\(s\) prête\(s\)\. Ajoutez d’autres pages ou lancez l’analyse\.$/, '$1 page(s) ready. Add more pages or start analysis.')
    .replace(/^(\d+) photo\(s\) reçue\(s\)\. Préparation des images…$/, '$1 photo(s) received. Preparing images…')
    .replace(/^Lecture de la page (\d+)\/(\d+) par le modèle…$/, 'Reading page $1/$2 with the model…')
    .replace(/^Page (\d+)\/(\d+) transcrite\.$/, 'Page $1/$2 transcribed.')
    .replace(/^Temps écoulé : /, 'Elapsed time: ')
    .replace(/^Interprétation de votre correction : /, 'Interpreting your correction: ')
    .replace(/^Validation du champ : /, 'Validating field: ')
    .replace(/^(\d+) accepté\(s\), (\d+) à vérifier, (\d+) manquant\(s\)\. (\d+) réponse\(s\) requise\(s\)\.$/, '$1 accepted, $2 for review, $3 missing. $4 response(s) required.')
    .replace(/^(Acceptés|À vérifier|Manquants)( \(\d+\))$/, (_, label, count) => english[label] + count)
    .replace(/^Page (\d+): image invalide\. Utilisez JPEG, PNG ou WebP\.$/, 'Page $1: invalid image. Use JPEG, PNG or WebP.');
}
function uiText(node, source) {
  node.dataset.uiText = source;
  node.textContent = tr(source);
}
function applyLanguage() {
  document.documentElement.lang = language;
  document.querySelectorAll('[data-ui-text]').forEach(node => { node.textContent = tr(node.dataset.uiText); });
  document.querySelector('.header-info small').textContent = tr('Assistant maternité');
  const toggle = document.getElementById('languageBtn');
  toggle.textContent = language === 'fr' ? 'EN' : 'FR';
  toggle.setAttribute('aria-label', language === 'fr' ? 'Switch to English' : 'Passer en français');
  document.getElementById('attachBtn').title = tr('Ajouter une photo');
  if (reviewPanel) {
    const activeField = progressNode?.closest('[data-field]')?.dataset.field || null;
    renderReview(activeField);
  }
  datasetLabels();
  setBusy(busy);
}
const chat = document.getElementById('chat');
const cameraInput = document.getElementById('cameraInput');
const galleryInput = document.getElementById('galleryInput');
const networkBtn = document.getElementById('networkBtn');
const messageInput = document.getElementById('messageInput');
let currentImages = [], currentExtraction = null, busy = false;
let reviewPanel = null;
let pendingFieldAction = null;
const dismissedFields = new Set();
const previews = [];
const defaultPlaceholder = messageInput.placeholder;
let progressTimer = null;
let progressNode = null;
let progressStarted = 0;
let progressStage = '';
function elapsedTime() {
  const seconds = Math.floor((performance.now() - progressStarted) / 1000);
  return `${Math.floor(seconds / 60)} min ${String(seconds % 60).padStart(2, '0')} s`;
}
function updateProcess(stage = progressStage) {
  progressStage = stage;
  if (!progressNode) return;
  uiText(progressNode.querySelector('.process-stage'), stage);
  uiText(progressNode.querySelector('.process-elapsed'), `Temps écoulé : ${elapsedTime()}`);
}
function beginProcess(message, host = null) {
  setBusy(true);
  if (host) {
    progressNode = document.createElement('div');
    progressNode.className = 'message system processing';
    progressNode.textContent = message;
    host.appendChild(progressNode);
  } else {
    progressNode = addMessage(message, 'system processing');
  }
  progressStarted = performance.now();
  delete progressNode.dataset.uiText;
  progressNode.replaceChildren();
  const title = document.createElement('strong');
  uiText(title, message);
  const stage = document.createElement('div');
  stage.className = 'process-stage';
  stage.setAttribute('role', 'status');
  stage.setAttribute('aria-live', 'polite');
  const elapsed = document.createElement('div');
  elapsed.className = 'process-elapsed';
  const hint = document.createElement('small');
  uiText(hint, 'Envoi désactivé jusqu’à la fin du traitement.');
  progressNode.append(title, stage, elapsed, hint);
  updateProcess('Veuillez patienter…');
  if (!host && !dismissedFields.size) chat.scrollTop = chat.scrollHeight;
  progressTimer = setInterval(() => updateProcess(), 1000);
}
function endProcess(message, failed = false) {
  clearInterval(progressTimer);
  if (progressNode) {
    progressNode.classList.remove('processing');
    uiText(progressNode, message);
    const duration = document.createElement('div');
    uiText(duration, `Temps écoulé : ${elapsedTime()}`);
    // Keep separate bound elements so language changes retain the duration.
    const resultText = document.createElement('div');
    uiText(resultText, message);
    delete progressNode.dataset.uiText;
    progressNode.replaceChildren(document.createTextNode(failed ? '❌ ' : '✓ '), resultText, duration);
  }
  progressNode = null;
  setBusy(false);
}
function watchProgress(id) {
  let stopped = false, count = 0, timer;
  async function poll() {
    try {
      const data = await api(`/api/progress/${encodeURIComponent(id)}`);
      if (stopped) return;
      for (const message of data.events.slice(count)) addMessage(message, 'system stage-message');
      if (data.events.length > count) updateProcess(data.events.at(-1));
      count = data.events.length;
    } catch { /* The main request reports errors; polling must not unlock the UI. */ }
    if (!stopped) timer = setTimeout(poll, 1000);
  }
  poll();
  return (finalEvents = []) => {
    stopped = true; clearTimeout(timer);
    for (const message of finalEvents.slice(count)) addMessage(message, 'system stage-message');
    if (finalEvents.length > count) updateProcess(finalEvents.at(-1));
    count = Math.max(count, finalEvents.length);
  };
}

function addMessage(text, type = 'bot') {
  const node = document.createElement('div');
  node.className = `message ${type}`;
  if (type === 'user') node.textContent = text;
  else uiText(node, text);
  const followBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 48;
  chat.appendChild(node);
  if (followBottom) chat.scrollTop = chat.scrollHeight;
  return node;
}
function button(label, action, parent) {
  const node = document.createElement('button');
  node.type = 'button'; uiText(node, label);
  node.addEventListener('click', () => { if (!busy) action(); });
  parent.appendChild(node);
  return node;
}
function actions(items, parent = chat) {
  const node = document.createElement('div'); node.className = 'actions';
  items.forEach(([label, action]) => button(label, action, node));
  parent.appendChild(node);
}
function setBusy(value) {
  busy = value;
  const analyze = document.getElementById('analyzeBatchBtn');
  if (analyze) analyze.dataset.locked = String(!currentImages.length || Boolean(currentExtraction));
  document.querySelectorAll('button, input').forEach(node => { node.disabled = node.dataset.undoAction === 'true' ? false : (pendingFieldAction ? true : !['languageBtn', 'datasetBtn', 'datasetClose', 'datasetRefresh', 'datasetPrev', 'datasetNext'].includes(node.id) && (value || node.dataset.locked === 'true')); });
  messageInput.placeholder = tr(value ? 'Traitement en cours… veuillez patienter' : defaultPlaceholder);
  const messageBar = document.querySelector('.message-bar');
  messageBar.setAttribute('aria-busy', String(value));
  messageBar.classList.toggle('is-busy', value);
}
async function api(url, body, form = false) {
  const options = body === undefined ? {} : {method: 'POST', body: form ? body : JSON.stringify(body)};
  if (body !== undefined && !form) options.headers = {'Content-Type': 'application/json'};
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Erreur ${response.status}`);
  return data;
}
function startVisit() {
  if (busy) return;
  if (currentExtraction && !currentExtraction.saved && !confirm(tr('Commencer une nouvelle visite ? Le dossier actuel reste conservé sur le serveur.'))) return;
  previews.splice(0).forEach(url => URL.revokeObjectURL(url));
  dismissedFields.clear();
  currentImages = []; currentExtraction = null;
  sessionStorage.removeItem('record_id'); chat.replaceChildren(); reviewPanel = null;
  addMessage('Nouvelle visite : ajoutez toutes les photos d’un même dossier, dans l’ordre.');
  setBusy(false);
}
function receive(input) {
  if (busy) { input.value = ''; return; }
  const selected = Array.from(input.files);
  input.value = '';
  // A cancelled picker must not discard the selected batch.
  if (!selected.length) return;
  // Every selection is an independent batch, never appended to a previous one.
  currentImages = selected;
  currentExtraction = null;
  dismissedFields.clear();
  sessionStorage.removeItem('record_id');
  if (reviewPanel) {
    // Keep prior results readable, without controls targeting the new batch.
    reviewPanel.querySelectorAll('button, input, .actions').forEach(node => node.remove());
    reviewPanel = null;
  }
  addMessage(language === 'en'
    ? `New batch: ${selected.length} photo(s). Only these photos will be analyzed.`
    : `Nouveau lot : ${selected.length} photo(s). Seules ces photos seront analysées.`, 'system');
  for (const [index, file] of selected.entries()) {
    const url = URL.createObjectURL(file); previews.push(url);
    const node = addMessage(`Page ${index + 1} : ${file.name}`, 'user');
    const image = document.createElement('img'); image.className = 'preview'; image.src = url; image.alt = `Page ${index + 1}`;
    node.appendChild(image);
  }
  setBusy(false);
  chat.scrollTop = chat.scrollHeight;
}
cameraInput.addEventListener('change', () => receive(cameraInput));
galleryInput.addEventListener('change', () => receive(galleryInput));
async function processImages() {
  if (busy || currentExtraction) return;
  if (!currentImages.length) return addMessage('Ajoutez au moins une photo.', 'system');
  beginProcess(`Analyse de ${currentImages.length} page(s) en cours…`);
  const form = new FormData(); currentImages.forEach(file => form.append('images', file));
  const progressId = crypto.randomUUID();
  form.append('progress_id', progressId);
  const stopProgress = watchProgress(progressId);
  let outcome = 'Analyse terminée. Vérifiez les résultats ci-dessous.', failed = false;
  try {
    currentExtraction = await api('/api/extract', form, true);
    currentImages = [];
    stopProgress(currentExtraction.progress_events || []);
    sessionStorage.setItem('record_id', currentExtraction.record_id);
    renderReview();
  } catch (error) { outcome = error.message; failed = true; }
  finally { stopProgress(); endProcess(outcome, failed); }
}
function renderReview(activeField = null) {
  const previousPanel = reviewPanel;
  const previousScroll = chat.scrollTop;
  const groupState = new Map();
  const drafts = new Map();
  let anchorName = null, anchorOffset = 0;
  if (previousPanel) {
    previousPanel.querySelectorAll('details').forEach(node => groupState.set(node.dataset.group, node.open));
    const cards = [...previousPanel.querySelectorAll('[data-field]')];
    cards.forEach(card => drafts.set(card.dataset.field, card.querySelector('input')?.value || ''));
    const viewport = chat.getBoundingClientRect();
    const visible = card => {
      const rect = card.getBoundingClientRect();
      return card.closest('details').open && rect.bottom > viewport.top && rect.top < viewport.bottom;
    };
    const anchor = cards.find(card => card.dataset.field === activeField && visible(card)) || cards.find(visible);
    if (anchor) {
      anchorName = anchor.dataset.field;
      anchorOffset = anchor.getBoundingClientRect().top - viewport.top;
    }
  }
  reviewPanel = document.createElement('section'); reviewPanel.className = 'review-panel';
  const heading = document.createElement('h3'); uiText(heading, currentExtraction.message); reviewPanel.appendChild(heading);
  for (const [group, title] of [['accepted', 'Acceptés'], ['review', 'À vérifier'], ['missing', 'Manquants']]) {
    const details = document.createElement('details'); details.dataset.group = group; details.open = groupState.get(group) ?? (group !== 'accepted');
    const summary = document.createElement('summary'); uiText(summary, `${title} (${currentExtraction[group].length})`); details.appendChild(summary);
    for (const field of currentExtraction[group]) {
      if (dismissedFields.has(field.name)) continue;
      const card = document.createElement('div'); card.className = 'field'; card.dataset.field = field.name;
      if (field.name === anchorName) details.open = true;
      const name = document.createElement('strong'); name.textContent = field.label; card.appendChild(name);
      const text = document.createElement('p');
      text.textContent = `${tr('Valeur')} : ${field.value ?? '—'}\n${tr(field.resolved ? 'Vérifié' : 'Réponse requise')}\n${field.evidence ? tr('Preuve') + ' : ' + field.evidence + '\n' : ''}${tr(field.reason || '')}\n${tr(field.question || '')}`;
      card.appendChild(text);
      if (!currentExtraction.saved) {
        const input = document.createElement('input'); input.type = 'text'; input.placeholder = tr('Votre correction (texte ou valeur)'); input.setAttribute('aria-label', `Correction : ${field.label}`); input.value = drafts.get(field.name) || ''; card.appendChild(input);
        if (group === 'missing') {
          attachInputFeedback(input, field.name, false);
          input.placeholder = language === 'en' ? 'Enter the missing value' : 'Saisissez la valeur manquante';
          input.addEventListener('input', () => input.setCustomValidity(''));
          actions([
            ['Confirmer', () => {
              const value = input.value.trim();
              if (!validateFieldInput(input, field.name)) { input.reportValidity(); return; }
              review(field.name, 'manual', value);
            }],
            ['Laisser vide', () => review(field.name, 'missing')]
          ], card);
        } else {
          actions([
            ['Confirmer', () => review(field.name, 'confirm')],
            ['Interpréter ma correction', () => review(field.name, 'modify', input.value)],
            ['Laisser vide', () => review(field.name, 'missing')]
          ], card);
        }
      }
      if (field.name === activeField && progressNode) card.appendChild(progressNode);
      details.appendChild(card);
    }
    reviewPanel.appendChild(details);
  }
  if (dismissedFields.size) {
    const restore = button(language === 'en' ? 'Show dismissed fields' : 'Afficher les champs masqués', () => {
      dismissedFields.clear(); renderReview();
    }, reviewPanel);
    const note = document.createElement('p');
    note.textContent = language === 'en'
      ? 'Interpreted corrections still need confirmation. Show dismissed fields to review them before saving.'
      : 'Les corrections interprétées doivent encore être confirmées. Affichez les champs masqués pour les vérifier avant l’enregistrement.';
    reviewPanel.appendChild(note);
  }
  if (!currentExtraction.saved) {
    const save = button('Confirmer le dossier et enregistrer le CSV', saveRecord, reviewPanel);
    save.dataset.locked = String(!currentExtraction.ready_to_save);
    save.disabled = !currentExtraction.ready_to_save;
  }
  button('Nouvelle visite', startVisit, reviewPanel);
  if (previousPanel) previousPanel.replaceWith(reviewPanel);
  else chat.appendChild(reviewPanel);
  setBusy(busy);
  if (previousPanel) {
    const anchor = [...reviewPanel.querySelectorAll('[data-field]')].find(card => card.dataset.field === anchorName);
    chat.scrollTop = anchor
      ? chat.scrollTop + anchor.getBoundingClientRect().top - chat.getBoundingClientRect().top - anchorOffset
      : previousScroll;
  }
}

const fieldInputRules = {"id": {"type": "text"}, "age (years)": {"type": "integer", "min": 0}, "education level (0=none/primary,1=secondary,2=higher)": {"type": "enum", "values": [0, 1, 2]}, "consanguinity": {"type": "enum", "values": [0, 1]}, "desired pregnancy": {"type": "enum", "values": [0, 1]}, "hypertension history": {"type": "enum", "values": [0, 1]}, "diabetes mellitus": {"type": "enum", "values": [0, 1]}, "gravidity (number)": {"type": "integer", "min": 0}, "parity (number)": {"type": "integer", "min": 0}, "abortions (number)": {"type": "integer", "min": 0}, "living children (number)": {"type": "integer", "min": 0}, "previous cesarean": {"type": "enum", "values": [0, 1]}, "bmi pregestational (kg/m2)": {"type": "number", "min": 0}, "mean systolic bp (mmhg)": {"type": "number", "min": 0}, "mean diastolic bp (mmhg)": {"type": "number", "min": 0}, "hemoglobin (g/dl)": {"type": "number", "min": 0}, "first fasting glucose (mg/dl)": {"type": "number", "min": 0}, "proteinuria": {"type": "enum", "values": [0, 1]}, "hiv test result": {"type": "enum", "values": [0, 1]}, "syphilis test result": {"type": "enum", "values": [0, 1]}, "hepatitis c test result": {"type": "enum", "values": [0, 1]}, "gestational age at enrollment (weeks)": {"type": "number", "min": 0}, "gestational dm": {"type": "enum", "values": [0, 1]}, "gestational age at birth (weeks)": {"type": "number", "min": 0}, "preterm birth": {"type": "enum", "values": [0, 1]}, "type of delivery (0=vaginal,1=cesarean)": {"type": "enum", "values": [0, 1]}, "newborn sex (0=female,1=male)": {"type": "enum", "values": [0, 1]}, "child birth weight (g)": {"type": "number", "min": 0}, "head circumference (cm)": {"type": "number", "min": 0}, "breastfeeding initiated": {"type": "enum", "values": [0, 1]}, "referral to higher care": {"type": "enum", "values": [0, 1]}};
function inputTypeHint(name) {
  const rule = fieldInputRules[name];
  const en = language === 'en';
  if (rule.type === 'text') return en ? 'Enter an identifier (text or numbers).' : 'Saisissez un identifiant (texte ou chiffres).';
  if (rule.type === 'enum') return (en ? 'Allowed codes: ' : 'Codes autorisés : ') + rule.values.join(', ') + '.';
  return rule.type === 'integer'
    ? (en ? 'Enter a whole number, 0 or greater.' : 'Saisissez un nombre entier supérieur ou égal à 0.')
    : (en ? 'Enter a number, 0 or greater. Decimal dot or comma allowed.' : 'Saisissez un nombre supérieur ou égal à 0. Point ou virgule décimale autorisé.');
}
function attachInputFeedback(input, name, allowBlank) {
  input.inputMode = fieldInputRules[name].type === 'text' ? 'text' : 'decimal';
  const hint = document.createElement('small'); hint.className = 'input-hint'; hint.textContent = inputTypeHint(name);
  const error = document.createElement('small'); error.className = 'input-error'; error.setAttribute('role', 'alert');
  error.id = `field-error-${crypto.randomUUID()}`; input.setAttribute('aria-describedby', error.id);
  input.insertAdjacentElement('afterend', hint); hint.insertAdjacentElement('afterend', error);
  input.validationFeedback = error;
  input.addEventListener('input', () => { input.setCustomValidity(''); input.removeAttribute('aria-invalid'); error.textContent = ''; });
  input.addEventListener('blur', () => { if (input.value.trim()) validateFieldInput(input, name, allowBlank); });
}
function validateFieldInput(input, name, allowBlank = false) {
  const value = input.value.trim();
  const rule = fieldInputRules[name];
  let error = '';
  if (!value) {
    if (!allowBlank) error = language === 'en' ? 'Enter a value, or choose Leave blank.' : 'Saisissez une valeur ou choisissez Laisser vide.';
  } else if (rule.type !== 'text') {
    const numeric = Number(value.replace(',', '.'));
    const syntax = /^[+-]?(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)$/.test(value);
    if (!syntax || !Number.isFinite(numeric) ||
        (rule.type === 'enum' ? !rule.values.includes(numeric) : numeric < 0 || (rule.type === 'integer' && !Number.isInteger(numeric)))) error = inputTypeHint(name);
  }
  input.setCustomValidity(error);
  input.setAttribute('aria-invalid', String(Boolean(error)));
  if (input.validationFeedback) input.validationFeedback.textContent = error;
  return !error;
}

function review(field, action, response) {
  if (busy || pendingFieldAction) return;
  const card = [...reviewPanel.querySelectorAll('[data-field]')].find(node => node.dataset.field === field);
  if (!card) return;
  const notice = document.createElement('div'); notice.className = 'undo-notice';
  notice.setAttribute('role', 'status');
  const countdown = document.createElement('span');
  const undo = document.createElement('button'); undo.type = 'button';
  undo.dataset.undoAction = 'true';
  undo.textContent = language === 'en' ? 'Undo' : 'Annuler';
  notice.append(countdown, undo); card.appendChild(notice);
  const deadline = performance.now() + 3000;
  const update = () => {
    const remaining = Math.max(0, Math.ceil((deadline - performance.now()) / 1000));
    countdown.textContent = language === 'en' ? `Card disappears in ${remaining}s` : `Le champ disparaît dans ${remaining}s`;
  };
  const pending = {timer: null, interval: null};
  pendingFieldAction = pending;
  setBusy(true); update();
  pending.interval = setInterval(update, 100);
  undo.addEventListener('click', () => {
    if (pendingFieldAction !== pending) return;
    clearTimeout(pending.timer); clearInterval(pending.interval);
    pendingFieldAction = null; notice.remove(); setBusy(false);
    // Nothing has been sent to the backend: the original value is untouched.
  });
  pending.timer = setTimeout(() => {
    if (pendingFieldAction !== pending) return;
    clearInterval(pending.interval); pendingFieldAction = null;
    notice.remove(); dismissedFields.add(field); card.remove();
    setBusy(false);
    commitReview(field, action, response);
  }, 3000);
}
async function commitReview(field, action, response) {
  if (busy) return;
  const card = [...reviewPanel.querySelectorAll('[data-field]')].find(node => node.dataset.field === field);
  beginProcess(action === 'modify' ? `Interprétation de votre correction : ${field}…` : `Validation du champ : ${field}…`, card);
  let outcome = action === 'modify' ? 'Correction interprétée. Confirmez la valeur proposée.' : 'Champ mis à jour.', failed = false;
  try {
    currentExtraction = action === 'manual'
      ? await api(`/api/records/${currentExtraction.record_id}/manual`, {revision: currentExtraction.revision, changes: {[field]: response}})
      : await api(`/api/records/${currentExtraction.record_id}/review`, {revision: currentExtraction.revision, field, action, response});
    renderReview(field);
  } catch (error) {
    outcome = error.message; failed = true;
    dismissedFields.delete(field); renderReview(field);
    if (action === 'manual' || action === 'modify') {
      const restored = [...reviewPanel.querySelectorAll('[data-field]')].find(node => node.dataset.field === field);
      if (restored?.querySelector('input')) restored.querySelector('input').value = response;
    }
  }
  finally { endProcess(outcome, failed); }
}
async function saveRecord() {
  if (!currentExtraction?.ready_to_save || busy) return;
  beginProcess('Enregistrement du dossier dans le CSV…');
  let outcome = 'Dossier enregistré dans le CSV.', failed = false;
  try {
    const result = await api(`/api/records/${currentExtraction.record_id}/finalize`, {confirm: true, revision: currentExtraction.revision});
    currentExtraction.saved = true; renderReview(); addMessage(result.message);
  } catch (error) { outcome = error.message; failed = true; }
  finally { endProcess(outcome, failed); }
}
function findPatient() { addMessage('La recherche par patiente n’est pas encore connectée. Le dossier en cours est restauré lors du rechargement de cette page.', 'system'); }
function sendMessage() {
  const text = messageInput.value.trim(); if (!text || busy) return;
  messageInput.value = ''; addMessage(text, 'user');
  addMessage('Saisissez votre réponse dans le champ concerné, puis choisissez « Interpréter ma correction ».');
}
document.getElementById('sendBtn').addEventListener('click', sendMessage);
messageInput.addEventListener('keydown', event => { if (event.key === 'Enter') sendMessage(); });
document.getElementById('attachBtn').addEventListener('click', () => { if (!busy) galleryInput.click(); });
networkBtn.addEventListener('click', async () => {
  try { await api('/api/health'); uiText(networkBtn, '● Backend connecté'); }
  catch { uiText(networkBtn, '● Backend indisponible'); }
});
async function initialize() {
  const id = sessionStorage.getItem('record_id');
  if (!id) { startVisit(); return; }
  beginProcess('Chargement du dossier…');
  let outcome = 'Dossier chargé.', failed = false;
  try { currentExtraction = await api(`/api/records/${encodeURIComponent(id)}`); chat.replaceChildren(); renderReview(); }
  catch (error) { outcome = error.message; failed = true; }
  finally { endProcess(outcome, failed); }
}

let datasetOffset = 0;
let datasetRequest = 0;
let datasetLoading = false;
let datasetSnapshot = null;
function datasetLabels() {
  const en = language === 'en';
  const labels = {datasetBtn: en ? 'View dataset' : 'Voir les données', datasetTitle: en ? 'Registry dataset' : 'Données du registre',
    datasetClose: en ? 'Close' : 'Fermer', datasetRefresh: en ? 'Refresh' : 'Actualiser',
    datasetDownload: en ? 'Download saved CSV' : 'Télécharger le CSV enregistré',
    datasetPrev: en ? 'Previous' : 'Précédent', datasetNext: en ? 'Next' : 'Suivant'};
  for (const [id, label] of Object.entries(labels)) document.getElementById(id).textContent = label;
  const options = document.getElementById('datasetStatus').options;
  options[0].textContent = en ? 'Saved records' : 'Dossiers enregistrés';
  options[1].textContent = en ? 'Pending review (not saved)' : 'À vérifier (non enregistrés)';
}
async function loadDataset() {
  const requestNumber = ++datasetRequest;
  datasetLoading = true;
  const en = language === 'en';
  const info = document.getElementById('datasetInfo');
  const area = document.getElementById('datasetTable');
  info.textContent = en ? 'Loading dataset…' : 'Chargement des données…';
  area.replaceChildren();
  document.getElementById('datasetPrev').disabled = true;
  document.getElementById('datasetNext').disabled = true;
  try {
    const status = document.getElementById('datasetStatus').value;
    const data = await api(`/api/dataset?status=${status}&offset=${datasetOffset}`);
    if (requestNumber !== datasetRequest) return;
    datasetSnapshot = data;
    info.textContent = `${data.saved_count} ${en ? 'saved' : 'enregistré(s)'} · ${data.draft_count} ${en ? 'pending review' : 'à vérifier'}. ` +
      (data.total ? `${datasetOffset + 1}–${datasetOffset + data.rows.length} / ${data.total}` : (en ? 'No records in this view. Finish review and save a record to populate the saved dataset.' : 'Aucun dossier dans cette vue. Terminez la vérification et enregistrez un dossier pour remplir les données enregistrées.'));
    if (status === 'draft') info.textContent += en ? ' These are unconfirmed candidates, excluded from the CSV.' : ' Valeurs proposées non confirmées, exclues du CSV.';
    const table = document.createElement('table');
    const head = table.createTHead().insertRow();
    for (const label of [en ? 'Actions' : 'Actions', en ? 'Record' : 'Dossier', en ? 'Unresolved' : 'À vérifier', ...data.columns]) {
      const cell = document.createElement('th'); cell.scope = 'col'; cell.textContent = label; head.appendChild(cell);
    }
    const body = table.createTBody();
    for (const record of data.rows) {
      const row = body.insertRow();
      const edit = document.createElement('button');
      edit.type = 'button'; edit.textContent = en ? 'Edit' : 'Modifier';
      edit.addEventListener('click', () => editDatasetRecord(record.record_id));
      const actionsCell = row.insertCell(); actionsCell.appendChild(edit);
      const remove = document.createElement('button'); remove.type = 'button';
      remove.className = 'delete-record'; remove.textContent = en ? 'Delete' : 'Supprimer';
      remove.setAttribute('aria-label', `${en ? 'Delete record' : 'Supprimer le dossier'} ${record.record_id}`);
      remove.addEventListener('click', () => deleteDatasetRecord(record));
      actionsCell.appendChild(remove);
      for (const value of [record.record_id, record.unresolved, ...data.columns.map(name => record.values[name])]) {
        row.insertCell().textContent = value === null || value === undefined ? '—' : String(value);
      }
    }
    if (data.rows.length) area.appendChild(table);
    document.getElementById('datasetPrev').disabled = datasetOffset === 0;
    document.getElementById('datasetNext').disabled = datasetOffset + data.rows.length >= data.total;
  } catch (error) { if (requestNumber === datasetRequest) info.textContent = tr(error.message); }
  finally { if (requestNumber === datasetRequest) datasetLoading = false; }
}
let datasetDeleting = false;
async function deleteDatasetRecord(record) {
  if (busy || datasetLoading || datasetDeleting || manualEditing) return;
  const en = language === 'en';
  const patientId = record.values.id ?? '—';
  if (!confirm(en
    ? `Delete record ${patientId} (${record.record_id})? This cannot be undone. Saved records will also be removed from the CSV.`
    : `Supprimer le dossier ${patientId} (${record.record_id}) ? Cette action est irréversible. Les dossiers enregistrés seront aussi retirés du CSV.`)) return;
  datasetDeleting = true;
  const dialog = document.getElementById('datasetDialog');
  const disabledState = [...dialog.querySelectorAll('button, select')].map(node => [node, node.disabled]);
  disabledState.forEach(([node]) => { node.disabled = true; });
  const info = document.getElementById('datasetInfo');
  info.textContent = en ? 'Deleting record…' : 'Suppression du dossier…';
  try {
    await api(`/api/records/${record.record_id}/delete`, {confirm: true, revision: record.revision});
    if (currentExtraction?.record_id === record.record_id) {
      currentExtraction = null; currentImages = []; dismissedFields.clear();
      reviewPanel?.remove(); reviewPanel = null;
      sessionStorage.removeItem('record_id');
      addMessage(en ? 'This record was deleted. Start a new visit to continue.' : 'Ce dossier a été supprimé. Commencez une nouvelle visite pour continuer.', 'system');
    } else if (sessionStorage.getItem('record_id') === record.record_id) sessionStorage.removeItem('record_id');
    if (datasetSnapshot?.rows.length === 1 && datasetOffset > 0) datasetOffset = Math.max(0, datasetOffset - 100);
    // Restore toolbar state before rendering the replacement rows and pagination.
    disabledState.forEach(([node, disabled]) => { node.disabled = disabled; });
    await loadDataset();
    info.textContent = (en ? 'Record deleted. ' : 'Dossier supprimé. ') + info.textContent;
  } catch (error) {
    disabledState.forEach(([node, disabled]) => { node.disabled = disabled; });
    info.textContent = tr(error.message);
  } finally { datasetDeleting = false; }
}
let manualEditing = false;
let manualSaving = false;
function exitManualEditor() {
  manualEditing = false;
  document.getElementById('datasetStatus').disabled = false;
  document.getElementById('datasetRefresh').disabled = false;
}
async function editDatasetRecord(recordId) {
  if (busy || manualEditing) return;
  manualEditing = true;
  document.getElementById('datasetStatus').disabled = true;
  document.getElementById('datasetRefresh').disabled = true;
  document.getElementById('datasetPrev').disabled = true;
  document.getElementById('datasetNext').disabled = true;
  const en = language === 'en';
  const area = document.getElementById('datasetTable');
  const info = document.getElementById('datasetInfo');
  info.textContent = en ? 'Loading editor…' : 'Chargement de l’éditeur…';
  try {
    const record = await api(`/api/records/${recordId}`);
    area.replaceChildren();
    info.textContent = en
      ? 'Edit values directly (no AI). Changed fields are confirmed on Save. Tick Confirm for unchanged or blank fields you have checked. Other pending fields remain unresolved.'
      : 'Modifiez directement les valeurs (sans IA). Les champs modifiés sont confirmés à l’enregistrement. Cochez Confirmer pour les champs inchangés ou vides vérifiés. Les autres restent à vérifier.';
    const form = document.createElement('form'); form.className = 'manual-editor'; form.noValidate = true;
    const controls = [];
    for (const field of record.fields) {
      const row = document.createElement('div'); row.className = 'manual-field';
      const label = document.createElement('label'); label.textContent = field.label;
      const input = document.createElement('input'); input.type = 'text'; input.value = field.value ?? '';
      input.setAttribute('aria-label', field.label); label.appendChild(input); row.appendChild(label);
      attachInputFeedback(input, field.name, true);
      const confirmLabel = document.createElement('label');
      const checked = document.createElement('input'); checked.type = 'checkbox'; checked.checked = field.resolved;
      confirmLabel.append(checked, document.createTextNode(en ? 'Confirm' : 'Confirmer'));
      row.appendChild(confirmLabel);
      const evidence = document.createElement('small'); evidence.textContent = field.evidence || (en ? 'No source evidence' : 'Aucune preuve source'); row.appendChild(evidence);
      controls.push({field, input, checked, original: String(field.value ?? '')});
      form.appendChild(row);
    }
    const footer = document.createElement('div'); footer.className = 'manual-footer';
    const save = document.createElement('button'); save.type = 'submit'; save.textContent = en ? 'Save changes' : 'Enregistrer les modifications';
    const cancel = document.createElement('button'); cancel.type = 'button'; cancel.textContent = en ? 'Cancel' : 'Annuler';
    cancel.addEventListener('click', () => { if (!manualSaving) { exitManualEditor(); loadDataset(); } });
    footer.append(save, cancel); form.appendChild(footer);
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (manualSaving || busy) return;
      const invalid = controls.filter(({field, input}) => !validateFieldInput(input, field.name, true));
      if (invalid.length) {
        info.textContent = language === 'en' ? 'Please correct the highlighted fields before saving.' : 'Corrigez les champs signalés avant d’enregistrer.';
        invalid[0].input.focus(); return;
      }
      const changes = {};
      for (const {field, input, checked, original} of controls) {
        if (input.value !== original || (checked.checked && !field.resolved)) changes[field.name] = input.value;
      }
      if (!Object.keys(changes).length) { info.textContent = en ? 'No changes to save.' : 'Aucune modification à enregistrer.'; return; }
      manualSaving = true;
      form.querySelectorAll('input, button').forEach(node => { node.disabled = true; });
      document.getElementById('datasetClose').disabled = true;
      info.textContent = en ? 'Saving changes…' : 'Enregistrement…';
      try {
        const updated = await api(`/api/records/${recordId}/manual`, {revision: record.revision, changes});
        if (currentExtraction?.record_id === recordId) { currentExtraction = updated; renderReview(); }
        exitManualEditor();
        await loadDataset();
        info.textContent = (en ? 'Changes saved. ' : 'Modifications enregistrées. ') + info.textContent;
      } catch (error) {
        info.textContent = error.message;
        form.querySelectorAll('input, button').forEach(node => { node.disabled = false; });
      } finally { manualSaving = false; document.getElementById('datasetClose').disabled = false; }
    });
    area.appendChild(form); area.scrollTop = 0;
  } catch (error) { exitManualEditor(); info.textContent = error.message; }
}
document.getElementById('datasetDialog').addEventListener('cancel', event => {
  if (datasetDeleting || manualSaving || (manualEditing && !confirm(language === 'en' ? 'Discard unsaved edits?' : 'Abandonner les modifications ?'))) event.preventDefault();
  else exitManualEditor();
});
document.getElementById('datasetBtn').addEventListener('click', () => {
  datasetLabels(); document.getElementById('datasetDialog').showModal(); loadDataset();
});
document.getElementById('datasetClose').addEventListener('click', () => {
  if (datasetDeleting || manualSaving || (manualEditing && !confirm(language === 'en' ? 'Discard unsaved edits?' : 'Abandonner les modifications ?'))) return;
  exitManualEditor(); document.getElementById('datasetDialog').close();
});
document.getElementById('datasetRefresh').addEventListener('click', loadDataset);
document.getElementById('datasetStatus').addEventListener('change', () => { datasetOffset = 0; loadDataset(); });
document.getElementById('datasetPrev').addEventListener('click', () => { if (!datasetLoading && datasetOffset > 0) { datasetOffset -= 100; loadDataset(); } });
document.getElementById('datasetNext').addEventListener('click', () => { if (!datasetLoading && datasetSnapshot && datasetOffset + 100 < datasetSnapshot.total) { datasetOffset += 100; loadDataset(); } });

document.getElementById('languageBtn').addEventListener('click', () => {
  language = language === 'fr' ? 'en' : 'fr';
  localStorage.setItem('dayone-language', language);
  applyLanguage();
});
const photoActions = document.getElementById('photoActions');
button('Prendre une photo', () => cameraInput.click(), photoActions);
button('Choisir des images', () => galleryInput.click(), photoActions);
const analyzeBatchButton = button('Analyser les pages', processImages, photoActions);
analyzeBatchButton.id = 'analyzeBatchBtn';
uiText(networkBtn, '● En ligne');
applyLanguage();
initialize();
