// Поиск в ВНД — диалог по содержанию документа

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8011'
    : '';

const SEARCH_QA_WELCOME =
    'Документ загружен. Задайте вопрос по его содержанию — ' +
    'отвечу строго на основании текста ВНД.';

const SEARCH_QA_WELCOME_WITH_ANALYSIS =
    'Документ и отчёт анализа подключены. Задайте вопрос по содержанию ВНД ' +
    'или по выявленным недостаткам из отчёта.';

const SEARCH_QA_WAIT_DOCUMENT =
    'Выберите или загрузите документ ВНД, чтобы начать диалог.';

let searchState = {
    documentText: '',
    analysisText: '',
    title: '',
    filename: '',
    source: '',
    analysisFilename: '',
    analysisSource: '',
    analysisAutoMatched: false,
    messages: [],
};
let searchSending = false;
let searchUploadInProgress = false;

document.addEventListener('DOMContentLoaded', () => {
    loadVndDatabaseList();
    bindSearchEvents();
    initSearchPageLayout();
});

function hasSearchDocument() {
    return Boolean((searchState.documentText || '').trim());
}

function updateSearchChatControls() {
    const isActive = hasSearchDocument();
    const box = document.querySelector('.search-chat-box');
    const input = document.getElementById('search-chat-input');
    const sendBtn = document.getElementById('btn-search-send');

    if (box) box.classList.toggle('search-chat-inactive', !isActive);
    if (input) {
        input.disabled = !isActive;
        input.placeholder = isActive
            ? 'Ваш вопрос по документу...'
            : 'Сначала загрузите или выберите документ ВНД';
    }
    if (sendBtn) sendBtn.disabled = !isActive || searchSending;
}

function initSearchPageLayout() {
    const chatPanel = document.getElementById('search-chat-panel');
    if (chatPanel) chatPanel.hidden = false;

    if (!hasSearchDocument()) {
        searchState.messages = [{ role: 'assistant', content: SEARCH_QA_WAIT_DOCUMENT }];
        const titleEl = document.getElementById('search-doc-title');
        const analysisEl = document.getElementById('search-analysis-title');
        if (titleEl) titleEl.textContent = 'Документ: не выбран';
        if (analysisEl) {
            analysisEl.textContent = '';
            analysisEl.style.display = 'none';
        }
        renderSearchMessages();
    }
    updateSearchChatControls();
}

function bindSearchEvents() {
    document.getElementById('btn-search-upload')?.addEventListener('click', uploadSearchDocument);
    document.getElementById('btn-search-from-db')?.addEventListener('click', loadSearchFromDatabase);
    document.getElementById('btn-search-send')?.addEventListener('click', sendSearchMessage);
    document.getElementById('btn-search-finish')?.addEventListener('click', finishSearchDialog);
    document.getElementById('btn-search-new')?.addEventListener('click', startNewSearchDialog);
    document.getElementById('btn-search-save')?.addEventListener('click', saveSearchDialog);
    document.getElementById('btn-search-back')?.addEventListener('click', onSearchBack);

    const vndInput = document.getElementById('search-file-input');
    if (vndInput) {
        vndInput.addEventListener('change', () => {
            if (isSearchSetupLocked()) return;
            if (vndInput.files?.[0]) {
                uploadSearchDocument();
            }
        });
    }

    const analysisInput = document.getElementById('search-analysis-input');
    if (analysisInput) {
        analysisInput.addEventListener('change', () => {
            if (isSearchSetupLocked()) return;
            const vndFile = document.getElementById('search-file-input')?.files?.[0];
            if (analysisInput.files?.[0] && vndFile && !searchUploadInProgress) {
                uploadSearchDocument();
            }
        });
    }

    const dbSelect = document.getElementById('search-db-select');
    if (dbSelect) {
        dbSelect.addEventListener('change', () => {
            refreshAnalysisCandidates(dbSelect.value);
        });
    }

    const input = document.getElementById('search-chat-input');
    if (input) {
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                if (!input.disabled) sendSearchMessage();
            }
        });
    }

    window.addEventListener('beforeunload', clearSearchSession);
}

function clearSearchSession() {
    searchState = {
        documentText: '',
        analysisText: '',
        title: '',
        filename: '',
        source: '',
        analysisFilename: '',
        analysisSource: '',
        analysisAutoMatched: false,
        messages: [],
    };
}

function isSearchSetupLocked() {
    return document.getElementById('search-setup-panel')?.classList.contains('search-setup-locked') === true;
}

function setSearchSetupLocked(locked) {
    const panel = document.getElementById('search-setup-panel');
    const hint = document.getElementById('search-setup-reselect-hint');
    if (panel) panel.classList.toggle('search-setup-locked', locked);
    if (hint) hint.hidden = !locked;

    [
        'search-file-input',
        'search-analysis-input',
        'btn-search-upload',
        'search-db-select',
        'search-analysis-select',
        'btn-search-from-db',
    ].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.disabled = locked;
    });
}

function onSearchBack() {
    clearSearchSession();
    window.location.href = '/';
}

async function loadVndDatabaseList() {
    const select = document.getElementById('search-db-select');
    const status = document.getElementById('search-db-status');
    if (!select) return;

    try {
        const response = await fetch(`${API_BASE}/api/bases/vnd/documents`);
        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось загрузить список документов'));
        }
        const data = await response.json();
        const documents = data.documents || [];

        select.innerHTML = '';
        if (!documents.length) {
            select.innerHTML = '<option value="">— База ВНД пуста —</option>';
            if (status) {
                status.textContent = 'Загрузите документы через «Анализ ВНД» или кнопку загрузки слева.';
                status.className = 'upload-status';
            }
            return;
        }

        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = '— Выберите документ —';
        select.appendChild(placeholder);

        documents.forEach((doc) => {
            const opt = document.createElement('option');
            opt.value = doc.filename;
            const chunks = doc.chunks ? ` (${doc.chunks} фрагм.)` : '';
            opt.textContent = `${doc.filename}${chunks}`;
            select.appendChild(opt);
        });
    } catch (error) {
        select.innerHTML = '<option value="">— Ошибка загрузки —</option>';
        if (status) {
            status.textContent = formatCaughtError(error, 'Ошибка загрузки списка');
            status.className = 'upload-status error';
        }
    }
}

async function refreshAnalysisCandidates(vndFilename) {
    const select = document.getElementById('search-analysis-select');
    if (!select) return;

    select.innerHTML = '<option value="">— Автоподбор —</option>';
    if (!vndFilename) return;

    try {
        const response = await fetch(
            `${API_BASE}/api/search/analysis-candidates?vnd_filename=${encodeURIComponent(vndFilename)}`
        );
        if (!response.ok) return;
        const data = await response.json();
        (data.candidates || []).forEach((item) => {
            const opt = document.createElement('option');
            opt.value = `${item.source}::${item.filename}`;
            opt.textContent = `${item.filename} (${item.source})`;
            select.appendChild(opt);
        });
    } catch (error) {
        console.warn('Не удалось загрузить отчёты анализа:', error);
    }
}

function parseAnalysisSelectValue(value) {
    if (!value) return { analysis_filename: null, analysis_source: null, auto_match: true };
    const [source, ...rest] = value.split('::');
    return {
        analysis_filename: rest.join('::'),
        analysis_source: source,
        auto_match: false,
    };
}

async function uploadSearchAnalysisFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE}/api/search/upload-analysis`, {
        method: 'POST',
        body: formData,
    });
    if (!response.ok) {
        throw new Error(await readApiError(response, 'Не удалось загрузить отчёт анализа'));
    }
    return response.json();
}

async function loadSearchSessionPayload(source, filename, analysisOptions = {}) {
    const response = await fetch(`${API_BASE}/api/search/load-document`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            source,
            filename,
            analysis_filename: analysisOptions.analysis_filename || '',
            analysis_source: analysisOptions.analysis_source || '',
            auto_match_analysis: analysisOptions.auto_match !== false,
        }),
    });
    if (!response.ok) {
        throw new Error(await readApiError(response, 'Не удалось загрузить документ'));
    }
    return response.json();
}

async function uploadSearchDocument() {
    if (searchUploadInProgress || isSearchSetupLocked()) return;

    const input = document.getElementById('search-file-input');
    const analysisInput = document.getElementById('search-analysis-input');
    const status = document.getElementById('search-upload-status');
    const file = input?.files?.[0];

    if (!file) {
        alert('Выберите файл ВНД');
        return;
    }

    searchUploadInProgress = true;
    if (status) {
        status.textContent = '⏳ Загрузка...';
        status.className = 'upload-status';
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const uploadResponse = await fetch(`${API_BASE}/api/upload/vnd`, {
            method: 'POST',
            body: formData,
        });
        if (!uploadResponse.ok) {
            throw new Error(await readApiError(uploadResponse, 'Не удалось загрузить файл'));
        }
        const uploadData = await uploadResponse.json();
        const filename = uploadData.filename || file.name;

        let analysisOptions = { auto_match: true };
        const analysisFile = analysisInput?.files?.[0];
        if (analysisFile) {
            const analysisUpload = await uploadSearchAnalysisFile(analysisFile);
            analysisOptions = {
                analysis_filename: analysisUpload.filename,
                analysis_source: analysisUpload.source || 'search',
                auto_match: false,
            };
        }

        const loadData = await loadSearchSessionPayload('upload', filename, analysisOptions);

        if (status) {
            let message = `✓ Загружен: ${filename}`;
            if (loadData.analysis_filename) {
                message += loadData.analysis_auto_matched
                    ? ` · отчёт подключён автоматически: ${loadData.analysis_filename}`
                    : ` · отчёт: ${loadData.analysis_filename}`;
            }
            status.textContent = message;
            status.className = 'upload-status success';
        }

        startSearchChat(loadData);
        loadVndDatabaseList();
    } catch (error) {
        if (status) {
            status.textContent = '✗ ' + formatCaughtError(error, 'Ошибка загрузки');
            status.className = 'upload-status error';
        }
    } finally {
        searchUploadInProgress = false;
    }
}

async function loadSearchFromDatabase() {
    const select = document.getElementById('search-db-select');
    const analysisSelect = document.getElementById('search-analysis-select');
    const status = document.getElementById('search-db-status');
    const filename = select?.value || '';

    if (!filename) {
        alert('Выберите документ из базы ВНД');
        return;
    }

    if (status) {
        status.textContent = '⏳ Загрузка документа...';
        status.className = 'upload-status';
    }

    try {
        const analysisOptions = parseAnalysisSelectValue(analysisSelect?.value || '');
        const data = await loadSearchSessionPayload('database', filename, analysisOptions);

        if (status) {
            let message = `✓ Выбран: ${filename}`;
            if (data.analysis_filename) {
                message += data.analysis_auto_matched
                    ? ` · отчёт подключён автоматически: ${data.analysis_filename}`
                    : ` · отчёт: ${data.analysis_filename}`;
            } else {
                message += ' · отчёт анализа не найден';
            }
            status.textContent = message;
            status.className = 'upload-status success';
        }

        startSearchChat(data);
    } catch (error) {
        if (status) {
            status.textContent = '✗ ' + formatCaughtError(error, 'Ошибка выбора');
            status.className = 'upload-status error';
        }
    }
}

function startSearchChat(data) {
    clearSearchSession();
    const hasAnalysis = Boolean((data.analysis_text || '').trim());

    searchState = {
        documentText: data.text || '',
        analysisText: data.analysis_text || '',
        title: data.title || data.filename || 'ВНД',
        filename: data.filename || '',
        source: data.source || '',
        analysisFilename: data.analysis_filename || '',
        analysisSource: data.analysis_source || '',
        analysisAutoMatched: Boolean(data.analysis_auto_matched),
        messages: [{
            role: 'assistant',
            content: hasAnalysis ? SEARCH_QA_WELCOME_WITH_ANALYSIS : SEARCH_QA_WELCOME,
        }],
    };

    const titleEl = document.getElementById('search-doc-title');
    if (titleEl) {
        titleEl.textContent = `Документ: ${searchState.title}`;
    }

    const analysisEl = document.getElementById('search-analysis-title');
    if (analysisEl) {
        if (searchState.analysisFilename) {
            const prefix = searchState.analysisAutoMatched ? 'Отчёт анализа (авто): ' : 'Отчёт анализа: ';
            analysisEl.textContent = prefix + searchState.analysisFilename;
            analysisEl.style.display = 'block';
        } else {
            analysisEl.textContent = '';
            analysisEl.style.display = 'none';
        }
    }

    document.getElementById('search-setup-panel')?.removeAttribute('hidden');

    setSearchSetupLocked(true);
    document.body.classList.add('search-dialog-active');
    updateSearchChatControls();
    renderSearchMessages();
    document.getElementById('search-chat-input')?.focus();
}

function showSearchSetup() {
    document.body.classList.remove('search-dialog-active');
    const setup = document.getElementById('search-setup-panel');
    if (setup) {
        setup.hidden = false;
        setup.classList.remove('search-setup-locked');
    }
    setSearchSetupLocked(false);

    const hint = document.getElementById('search-setup-reselect-hint');
    if (hint) hint.hidden = true;

    const uploadStatus = document.getElementById('search-upload-status');
    const dbStatus = document.getElementById('search-db-status');
    if (uploadStatus) {
        uploadStatus.textContent = '';
        uploadStatus.className = 'upload-status';
    }
    if (dbStatus) {
        dbStatus.textContent = '';
        dbStatus.className = 'upload-status';
    }

    const fileInput = document.getElementById('search-file-input');
    if (fileInput) fileInput.value = '';
    const analysisInput = document.getElementById('search-analysis-input');
    if (analysisInput) analysisInput.value = '';
    const dbSelect = document.getElementById('search-db-select');
    if (dbSelect) dbSelect.value = '';
    const analysisSelect = document.getElementById('search-analysis-select');
    if (analysisSelect) {
        analysisSelect.innerHTML = '<option value="">— Автоподбор —</option>';
    }

    loadVndDatabaseList();
    initSearchPageLayout();
}

function finishSearchDialog() {
    clearSearchSession();
    window.location.href = '/';
}

function startNewSearchDialog() {
    clearSearchSession();
    showSearchSetup();
}

function renderSearchMessages() {
    const container = document.getElementById('search-chat-messages');
    if (!container) return;

    container.innerHTML = '';
    searchState.messages.forEach((msg) => {
        const div = document.createElement('div');
        div.className = `message ${msg.role === 'user' ? 'user' : 'assistant'}`;
        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = msg.content;
        div.appendChild(content);
        container.appendChild(div);
    });
    container.scrollTop = container.scrollHeight;
}

async function sendSearchMessage() {
    if (searchSending || !hasSearchDocument()) return;

    const input = document.getElementById('search-chat-input');
    const text = input?.value?.trim();
    if (!text) return;

    const sendBtn = document.getElementById('btn-search-send');
    searchSending = true;
    updateSearchChatControls();

    try {
        const response = await fetch(`${API_BASE}/api/search/qa/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                document: searchState.documentText,
                analysis_text: searchState.analysisText,
                title: searchState.title,
                messages: searchState.messages,
                user_message: text,
            }),
        });

        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось отправить вопрос'));
        }

        const data = await response.json();
        searchState.messages = data.messages || searchState.messages;
        if (input) input.value = '';
        renderSearchMessages();
    } catch (error) {
        alert('❌ ' + formatCaughtError(error, 'Ошибка диалога'));
    } finally {
        searchSending = false;
        updateSearchChatControls();
    }
}

async function saveSearchDialog() {
    const hasUserMessages = searchState.messages.some((msg) => msg.role === 'user');
    if (!hasUserMessages) {
        alert('В диалоге пока нет вопросов для сохранения');
        return;
    }

    try {
        const result = await saveDocumentToWorkFolder(
            `${API_BASE}/api/search/qa/save`,
            {
                title: searchState.title,
                messages: searchState.messages,
            },
            'Не удалось сохранить диалог',
        );
        alert(`✅ Диалог сохранён в рабочую папку\n\n📁 ${result.filepath || result.filename}`);
    } catch (error) {
        alert('❌ ' + formatCaughtError(error, 'Ошибка сохранения'));
    }
}
