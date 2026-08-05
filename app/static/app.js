const state = { activeSessionId: null, sessions: [], documents: [], streaming: false, toastTimer: null, lastQuestion: null, abortController: null, sessionsExpanded: false };
const MAX_SESSIONS = 7; // batas daftar percakapan sebelum tombol "Tampilkan semua"
const $ = (selector) => document.querySelector(selector);
const els = {
  shell: $('#app-shell'), sessionList: $('#session-list'), documentList: $('#document-list'),
  sessionCount: $('#session-count'), sessionTitle: $('#session-title'), messages: $('#message-list'),
  empty: $('#empty-state'), status: $('#api-status'), sourceFilter: $('#source-filter'),
  mode: $('#context-mode'), topK: $('#top-k'), question: $('#question'), form: $('#query-form'),
  send: $('#send-button'), stopButton: $('#stop-button'), uploadDialog: $('#upload-dialog'), uploadForm: $('#upload-form'),
  uploadFeedback: $('#upload-feedback'), renameDialog: $('#rename-dialog'), renameForm: $('#rename-form'),
  renameInput: $('#rename-input'), commandDialog: $('#command-dialog'), commandInput: $('#command-input'), toast: $('#toast'),
  chatRegion: $('#chat-region'),
};

function api(path, options = {}) {
  return fetch(path, { headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options })
    .then(async (response) => { const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`); return body; });
}

function showToast(message) {
  clearTimeout(state.toastTimer);
  els.toast.textContent = message;
  els.toast.classList.add('is-visible');
  state.toastTimer = setTimeout(() => els.toast.classList.remove('is-visible'), 3200);
}

function setStatus(ok, label) {
  els.status.className = `status-line ${ok ? 'is-ok' : 'is-error'}`;
  els.status.lastElementChild.textContent = label;
}

function setTheme() {
  const dark = document.documentElement.dataset.theme === 'dark';
  document.documentElement.dataset.theme = dark ? '' : 'dark';
  localStorage.setItem('kb-theme', dark ? 'light' : 'dark');
  showToast(dark ? 'Tampilan terang aktif.' : 'Tampilan gelap aktif.');
}

// Ikon SVG — satu sistem stroke currentColor (defs ada di index.html)
function icon(name, cls = 'icon') {
  return `<svg class="${cls}" aria-hidden="true"><use href="#${name}"/></svg>`;
}

// Markdown & Highlighting Helper — output LLM adalah data tak tepercaya,
// jadi HTML hasil parse WAJIB disanitasi sebelum masuk innerHTML.
function renderMarkdown(content) {
  if (!content) return '';
  let html = '';
  if (window.marked) {
    try {
      html = window.marked.parse(content);
    } catch (e) {
      console.error('Markdown parse error:', e);
    }
  }
  if (!html) {
    const div = document.createElement('div');
    div.textContent = content;
    html = div.innerHTML.replace(/\n/g, '<br>');
  }
  if (window.DOMPurify) return DOMPurify.sanitize(html);
  // Fallback tanpa DOMPurify: teks polos saja — jangan pernah innerHTML mentah
  const div = document.createElement('div');
  div.textContent = content;
  return div.innerHTML.replace(/\n/g, '<br>');
}

function highlightCodeBlocks(container) {
  if (window.hljs && container) {
    container.querySelectorAll('pre code').forEach((block) => {
      window.hljs.highlightElement(block);
    });
  }
}

async function loadBootstrap() {
  try {
    await api('/health');
    setStatus(true, 'API terhubung');
    await Promise.all([loadDocuments(), loadSessions()]);
    if (!state.activeSessionId) await createSession();
  } catch (error) {
    setStatus(false, 'API tidak terhubung');
    showToast(`Tidak dapat memuat workspace: ${error.message}`);
  }
}

async function loadSessions({ preserve = true } = {}) {
  const data = await api('/sessions/list');
  state.sessions = data.sessions || [];
  els.sessionCount.textContent = state.sessions.length;
  if (!preserve || !state.sessions.some((item) => item.id === state.activeSessionId)) {
    state.activeSessionId = state.sessions[0]?.id || null;
  }
  renderSessions();
}

function renderSessions() {
  els.sessionList.replaceChildren();
  if (!state.sessions.length) {
    const note = document.createElement('p');
    note.className = 'empty-list';
    note.textContent = 'Belum ada chat.';
    els.sessionList.append(note);
    return;
  }

  // Batasi tampilan awal (MAX_SESSIONS) supaya sidebar tidak menumpuk;
  // tombol toggle memperluas ke seluruh daftar.
  const shown = state.sessionsExpanded ? state.sessions : state.sessions.slice(0, MAX_SESSIONS);

  // Time grouping logic
  const now = new Date();
  const groups = { 'Hari Ini': [], 'Kemarin': [], '7 Hari Terakhir': [], 'Sebelumnya': [] };

  for (const session of shown) {
    const sessionDate = session.created_at ? new Date(session.created_at) : now;
    const diffDays = Math.floor((now - sessionDate) / (1000 * 60 * 60 * 24));
    if (diffDays <= 0) groups['Hari Ini'].push(session);
    else if (diffDays === 1) groups['Kemarin'].push(session);
    else if (diffDays <= 7) groups['7 Hari Terakhir'].push(session);
    else groups['Sebelumnya'].push(session);
  }

  for (const [groupName, sessions] of Object.entries(groups)) {
    if (!sessions.length) continue;
    const header = document.createElement('div');
    header.className = 'time-group-label';
    header.textContent = groupName;
    els.sessionList.append(header);

    for (const session of sessions) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `session-button${session.id === state.activeSessionId ? ' is-active' : ''}`;
      button.dataset.id = session.id;
      const label = document.createElement('span');
      label.textContent = session.title;
      button.append(label);
      button.title = session.title;
      button.addEventListener('click', () => selectSession(session.id));
      els.sessionList.append(button);
    }
  }

  if (state.sessions.length > MAX_SESSIONS) {
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'expand-toggle';
    toggle.textContent = state.sessionsExpanded
      ? 'Tampilkan lebih sedikit'
      : `Tampilkan semua (${state.sessions.length})`;
    toggle.addEventListener('click', () => {
      state.sessionsExpanded = !state.sessionsExpanded;
      renderSessions();
    });
    els.sessionList.append(toggle);
  }
}

async function selectSession(id) {
  if (!id || state.streaming) return;
  state.activeSessionId = id;
  renderSessions();
  const session = state.sessions.find((item) => item.id === id);
  els.sessionTitle.textContent = session?.title || 'Chat baru';
  els.shell.classList.remove('is-sidebar-open');
  try {
    const data = await api(`/sessions/${encodeURIComponent(id)}/messages`);
    renderMessages(data.messages || []);
  } catch (error) {
    showToast(`Tidak dapat membuka chat: ${error.message}`);
  }
}

async function createSession() {
  const data = await api('/sessions/create', { method: 'POST' });
  state.activeSessionId = data.session.id;
  await loadSessions();
  await selectSession(data.session.id);
  els.question.focus();
}

async function renameSession() {
  if (!state.activeSessionId) return;
  const title = els.renameInput.value.trim();
  if (!title) return;
  try {
    await api(`/sessions/${encodeURIComponent(state.activeSessionId)}/rename`, { method: 'PUT', body: JSON.stringify({ title }) });
    els.renameDialog.close();
    await loadSessions();
    await selectSession(state.activeSessionId);
    showToast('Nama chat diperbarui.');
  } catch (error) {
    showToast(error.message);
  }
}

async function deleteSession() {
  const session = state.sessions.find((item) => item.id === state.activeSessionId);
  if (!session || !confirm(`Hapus chat “${session.title}”? Riwayatnya tidak dapat dikembalikan.`)) return;
  try {
    await api(`/sessions/${encodeURIComponent(session.id)}`, { method: 'DELETE' });
    state.activeSessionId = null;
    await loadSessions({ preserve: false });
    if (state.activeSessionId) await selectSession(state.activeSessionId);
    else await createSession();
    showToast('Chat dihapus.');
  } catch (error) {
    showToast(error.message);
  }
}

async function loadDocuments() {
  const data = await api('/documents');
  state.documents = data.documents || [];
  renderDocuments();
  renderSourceFilter();
}

function renderDocuments() {
  els.documentList.replaceChildren();
  if (!state.documents.length) {
    const note = document.createElement('p');
    note.className = 'empty-list';
    note.textContent = 'Belum ada PDF terindeks.';
    els.documentList.append(note);
    return;
  }
  for (const doc of state.documents) {
    const row = document.createElement('div');
    row.className = 'document-row';
    const button = document.createElement('button');
    button.className = 'document-button';
    button.type = 'button';
    const title = document.createElement('span');
    title.className = 'document-title';
    title.textContent = doc.source;
    const info = document.createElement('small');
    info.textContent = `${doc.chunks} chunk · ${doc.pages.length} hlm`;
    button.append(title, info);
    button.title = doc.source;
    button.addEventListener('click', () => {
      els.sourceFilter.value = doc.source;
      els.question.focus();
      showToast(`Filter dokumen set ke “${doc.source}”`);
    });
    const remove = document.createElement('button');
    remove.className = 'document-remove';
    remove.type = 'button';
    remove.innerHTML = icon('i-trash');
    remove.setAttribute('aria-label', `Hapus ${doc.source}`);
    remove.addEventListener('click', async () => {
      if (!confirm(`Hapus dokumen “${doc.source}” dari indeks?`)) return;
      try {
        await api(`/documents/${encodeURIComponent(doc.source)}`, { method: 'DELETE' });
        await loadDocuments();
        showToast('Dokumen dihapus dari indeks.');
      } catch (error) {
        showToast(error.message);
      }
    });
    row.append(button, remove);
    els.documentList.append(row);
  }
}

function renderSourceFilter() {
  const selected = els.sourceFilter.value;
  els.sourceFilter.replaceChildren(new Option('Semua dokumen', ''));
  for (const doc of state.documents) els.sourceFilter.add(new Option(doc.source, doc.source));
  els.sourceFilter.value = state.documents.some((doc) => doc.source === selected) ? selected : '';
}

function renderMessages(messages) {
  els.messages.replaceChildren();
  els.empty.hidden = messages.length > 0;
  for (const message of messages) els.messages.append(createMessage(message));
  highlightCodeBlocks(els.messages);
  requestAnimationFrame(() => els.chatRegion?.scrollTo?.({ top: els.chatRegion.scrollHeight }));
}

function createMessage(message) {
  const article = document.createElement('article');
  article.className = `message ${message.role}`;
  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  if (message.role === 'user') avatar.textContent = 'YOU';
  else avatar.innerHTML = icon('i-mark');

  const content = document.createElement('div');
  content.className = 'message-content';
  const meta = document.createElement('div');
  meta.className = 'message-meta';
  meta.textContent = message.role === 'user' ? 'PERTANYAAN' : 'JAWABAN';

  const body = document.createElement('div');
  body.className = 'message-text';
  if (message.role === 'assistant') {
    body.innerHTML = renderMarkdown(message.content || '');
  } else {
    body.textContent = message.content || '';
  }

  content.append(meta, body);

  if (message.cached) {
    const cache = document.createElement('span');
    cache.className = 'cache-note';
    cache.innerHTML = `${icon('i-zap')} dari semantic cache`;
    content.append(cache);
  }

  if (message.sources?.length) {
    content.append(createSources(message.sources));
  }

  article.append(avatar, content);
  return article;
}

// Collapsible Accordion for Sources
function createSources(sources) {
  const details = document.createElement('details');
  details.className = 'source-accordion';

  const summary = document.createElement('summary');
  summary.className = 'source-summary';
  summary.innerHTML = `
    <span class="source-summary-title">
      ${icon('i-file')} <span>Sumber Rujukan</span>
      <span class="source-badge">${sources.length}</span>
    </span>
    <span class="source-chevron">${icon('i-chevron')}</span>
  `;

  const list = document.createElement('div');
  list.className = 'source-list';

  for (const source of sources) {
    const card = document.createElement('div');
    card.className = 'source-card';
    const title = document.createElement('strong');
    title.textContent = source.heading || 'Bagian dokumen';
    const meta = document.createElement('small');
    meta.textContent = `${source.source} · halaman ${source.page}`;
    const excerpt = document.createElement('p');
    excerpt.textContent = (source.text || '').slice(0, 320);
    card.append(title, meta, excerpt);
    list.append(card);
  }

  details.append(summary, list);
  return details;
}

function autoGrow() {
  els.question.style.height = 'auto';
  els.question.style.height = `${Math.min(els.question.scrollHeight, 176)}px`;
}

function setStreaming(active) {
  state.streaming = active;
  els.send.disabled = active;
  els.question.disabled = active;
  els.stopButton.hidden = !active;
  els.chatRegion.setAttribute('aria-busy', String(active));
  const btnSpan = els.send.querySelector('span:first-child');
  if (btnSpan) btnSpan.textContent = active ? 'Menjawab...' : 'Kirim';
}

async function askQuestion(question) {
  if (!question.trim() || state.streaming) return;
  if (!state.activeSessionId) await createSession();
  els.empty.hidden = true;
  state.lastQuestion = question;

  const userNode = createMessage({ role: 'user', content: question });
  els.messages.append(userNode);
  els.question.value = '';
  autoGrow();
  setStreaming(true);

  const assistant = createMessage({ role: 'assistant', content: '' });
  els.messages.append(assistant);
  const body = assistant.querySelector('.message-text');
  let sources = [];
  let cached = false;
  let answer = '';
  state.abortController = new AbortController();

  try {
    const response = await fetch('/query/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        top_k: Number(els.topK.value),
        source: els.sourceFilter.value || null,
        session_id: state.activeSessionId,
        mode: els.mode.value,
      }),
      signal: state.abortController.signal,
    });
    if (!response.ok || !response.body) throw new Error((await response.json().catch(() => ({}))).detail || `HTTP ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const records = buffer.split('\n\n');
      buffer = records.pop() || '';

      for (const record of records) {
        const line = record.split('\n').find((item) => item.startsWith('data:'));
        if (!line) continue;
        const event = JSON.parse(line.slice(5));

        if (event.type === 'meta') {
          sources = event.sources || [];
          cached = event.cached;
        } else if (event.type === 'delta') {
          answer += event.text || '';
          body.innerHTML = renderMarkdown(answer);
          highlightCodeBlocks(body);
          els.chatRegion?.scrollTo?.({ top: els.chatRegion.scrollHeight });
        } else if (event.type === 'done') {
          answer = event.answer || answer;
          body.innerHTML = renderMarkdown(answer || '(Tidak ada jawaban)');
          highlightCodeBlocks(body);
          if (event.session) {
            await loadSessions();
            await selectSession(state.activeSessionId);
          }
        } else if (event.type === 'error') {
          const err = new Error(event.detail || 'Gagal mendapatkan jawaban.');
          err.isLLM = true;
          throw err;
        }
      }
    }

    if (cached) {
      const note = document.createElement('span');
      note.className = 'cache-note';
      note.innerHTML = `${icon('i-zap')} dari semantic cache`;
      assistant.querySelector('.message-content').append(note);
    }
    if (sources.length) {
      assistant.querySelector('.message-content').append(createSources(sources));
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      const text = answer.trim() ? `${answer}\n\n— Jawaban dihentikan.` : '(Jawaban dihentikan.)';
      body.innerHTML = renderMarkdown(text);
      body.classList.add('message-error');
    } else {
      body.innerHTML = '';
      const msg = document.createElement('p');
      msg.textContent = `Tidak dapat menjawab: ${error.message}`;
      body.append(msg);
      body.classList.add('message-error');
      // Retry hanya untuk error koneksi/HTTP — error LLM (isLLM) tidak di-retry
      if (!error.isLLM && state.lastQuestion) {
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.className = 'button button-secondary retry-button';
        retry.textContent = 'Coba lagi';
        retry.addEventListener('click', () => {
          userNode.remove();
          assistant.remove();
          askQuestion(state.lastQuestion);
        });
        body.append(retry);
      }
    }
  } finally {
    state.abortController = null;
    setStreaming(false);
    els.question.focus();
  }
}

async function uploadDocument(event) {
  event.preventDefault();
  const file = $('#pdf-file').files[0];
  if (!file) return;
  const feedback = els.uploadFeedback;
  feedback.className = 'form-feedback';
  feedback.textContent = 'Mengekstrak dan mengindeks dokumen…';
  const submit = $('#upload-submit');
  submit.disabled = true;

  try {
    const form = new FormData();
    form.append('file', file);
    if ($('#source-name').value.trim()) form.append('source', $('#source-name').value.trim());
    const data = await api('/upload', { method: 'POST', body: form });
    els.uploadDialog.close();
    els.uploadForm.reset();
    await loadDocuments();
    showToast(`${data.chunks} chunk dari “${data.source}” sudah terindeks.`);
  } catch (error) {
    feedback.className = 'form-feedback is-error';
    feedback.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
}

function openUpload() { els.uploadFeedback.textContent = ''; els.uploadDialog.showModal(); $('#pdf-file').focus(); }
function openCommand() { els.commandDialog.showModal(); els.commandInput.value = ''; els.commandInput.focus(); }

function wireEvents() {
  $('#new-chat').addEventListener('click', createSession);
  $('#open-upload').addEventListener('click', openUpload);
  $('#empty-upload').addEventListener('click', openUpload);
  $('#example-question').addEventListener('click', () => {
    els.question.value = 'Dokumen ini membahas apa?';
    autoGrow();
    els.question.focus();
  });
  $('#rename-session').addEventListener('click', () => {
    const current = state.sessions.find((item) => item.id === state.activeSessionId);
    els.renameInput.value = current?.title || '';
    els.renameDialog.showModal();
    els.renameInput.focus();
  });
  $('#delete-session').addEventListener('click', deleteSession);
  els.renameForm.addEventListener('submit', (event) => { event.preventDefault(); renameSession(); });
  els.uploadForm.addEventListener('submit', uploadDocument);
  els.form.addEventListener('submit', (event) => { event.preventDefault(); askQuestion(els.question.value); });
  els.stopButton.addEventListener('click', () => state.abortController?.abort());
  els.question.addEventListener('input', autoGrow);
  els.question.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      els.form.requestSubmit();
    }
  });

  $('#command-trigger').addEventListener('click', openCommand);
  $('#mobile-menu').addEventListener('click', () => els.shell.classList.add('is-sidebar-open'));
  $('#mobile-close').addEventListener('click', () => els.shell.classList.remove('is-sidebar-open'));

  $('#command-options').addEventListener('click', (event) => {
    const action = event.target.closest('button')?.value;
    if (!action) return;
    els.commandDialog.close();
    if (action === 'new') createSession();
    if (action === 'upload') openUpload();
    if (action === 'theme') setTheme();
  });

  document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (!els.commandDialog.open) openCommand();
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  document.documentElement.dataset.theme = localStorage.getItem('kb-theme') === 'dark' ? 'dark' : '';
  wireEvents();
  loadBootstrap();
});
