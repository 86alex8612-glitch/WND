// Помощник в создании ВНД

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8011'
    : '';

let createOptions = null;
let mainFilename = null;
let analysisFilename = null;
let analysisText = null;
let analysisAutoMatched = false;
let reworkAnalysisSkipped = false;
let lastReworkDocument = '';
let lastReworkChangesReport = '';
let lastNewDocument = '';
let newFlowState = { form: null, followup_answers: {}, analysis: '', laws: [], download_result: null };
let reworkFormReady = false;
let reworkFormState = null;
let progressInterval = null;
let createQaMode = null;
let createQaSending = false;
const createQaState = {
    rework: { messages: [] },
    new: { messages: [] },
};
const CREATE_QA_WELCOME =
    'Здравствуйте! Задайте вопрос по подготовленному документу — ' +
    'поясню статьи, структуру, правовые основания и места для самостоятельного заполнения.';

let createInstructionCache = '';
let createInstructionLoading = false;

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function formatDocumentWithRedMarkers(text) {
    const escaped = escapeHtml(text || '');
    return escaped.replace(
        /&lt;&lt;RED&gt;&gt;([\s\S]*?)&lt;&lt;ENDRED&gt;&gt;/g,
        '<strong class="vnd-self-fill">$1</strong>'
    );
}

function renderReworkDocument(text) {
    lastReworkDocument = text || '';
}

function openCreateDocumentModal(mode, options = {}) {
    const text = mode === 'rework' ? lastReworkDocument : lastNewDocument;
    if (!text) {
        alert('Документ ещё не сформирован');
        return;
    }

    createQaMode = mode;
    const state = createQaState[mode];
    if (!state.messages.length) {
        state.messages.push({ role: 'assistant', content: CREATE_QA_WELCOME });
    }

    const body = document.getElementById('create-document-body');
    if (body) {
        body.innerHTML = formatDocumentWithRedMarkers(text);
        body.scrollTop = 0;
    }
    const title = document.getElementById('create-document-title');
    if (title) {
        title.textContent = mode === 'rework' ? 'Переработанный документ' : 'Сформированный документ';
    }
    const subtitle = document.getElementById('create-document-subtitle');
    if (subtitle) {
        subtitle.textContent = `Документ: ${getCreateQaTitle(mode)}. Слева — текст, справа — диалог с вопросами.`;
    }

    renderCreateQaMessages();

    const modal = document.getElementById('create-document-modal');
    if (!modal) return;
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');

    if (options.focusChat) {
        document.getElementById('create-qa-input')?.focus();
    }
}

function closeCreateDocumentModal() {
    const modal = document.getElementById('create-document-modal');
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
}

function downloadCreateDocumentFromModal() {
    if (!createQaMode) return;
    downloadCreateDocument(createQaMode, 'docx');
}

document.addEventListener('DOMContentLoaded', () => {
    loadCreateOptions();
    updateReworkPrefillButton();
    setupReworkFormValidationRefresh();
    setReworkAnalysisControlsEnabled(true);
    const qaInput = document.getElementById('create-qa-input');
    if (qaInput) {
        qaInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendCreateQaMessage();
            }
        });
    }
});

async function loadCreateOptions() {
    try {
        const response = await fetch(`${API_BASE}/api/create/options?t=${Date.now()}`);
        if (!response.ok) return;
        createOptions = await response.json();
        populateNewFormOptions(createOptions.new_document);
        populateReworkFormOptions(createOptions.new_document);
    } catch (error) {
        console.warn('Не удалось загрузить справочники:', error);
    }
}

async function refreshFollowupQuestionOptions() {
    try {
        const response = await fetch(`${API_BASE}/api/create/options?t=${Date.now()}`);
        if (!response.ok) return;
        const data = await response.json();
        if (!createOptions) createOptions = {};
        createOptions.new_document = data.new_document;
    } catch (error) {
        console.warn('Не удалось обновить уточняющие вопросы:', error);
    }
}

function populateNewFormOptions(options) {
    if (!options) return;

    const legalSelect = document.getElementById('new-legal-area');
    if (legalSelect) {
        legalSelect.innerHTML = '<option value="">— Выберите область —</option>';
        (options.legal_areas || []).forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.label;
            opt.dataset.examples = item.examples || '';
            legalSelect.appendChild(opt);
        });
    }

    const activitySelect = document.getElementById('new-activity');
    if (activitySelect) {
        activitySelect.innerHTML = '<option value="">— Выберите сферу —</option>';
        (options.activity_spheres || []).forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.label;
            opt.dataset.description = item.description || '';
            activitySelect.appendChild(opt);
        });
    }

    const ownershipSelect = document.getElementById('new-ownership');
    if (ownershipSelect) {
        ownershipSelect.innerHTML = '<option value="">— Выберите форму —</option>';
        (options.ownership_forms || []).forEach((group) => {
            const optgroup = document.createElement('optgroup');
            optgroup.label = group.group || '';
            (group.options || []).forEach((value) => {
                const opt = document.createElement('option');
                opt.value = value;
                opt.textContent = value;
                optgroup.appendChild(opt);
            });
            ownershipSelect.appendChild(optgroup);
        });
    }

    const secretSelect = document.getElementById('new-state-secret');
    if (secretSelect) {
        secretSelect.innerHTML = '<option value="">— Выберите —</option>';
        (options.state_secret_options || []).forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.label;
            secretSelect.appendChild(opt);
        });
    }

    const audienceSelect = document.getElementById('new-audience');
    if (audienceSelect) {
        audienceSelect.innerHTML = '<option value="">— Выберите аудиторию —</option>';
        (options.target_audiences || []).forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.label;
            audienceSelect.appendChild(opt);
        });
    }

    updateLegalAreaHint();
    updateActivityHint();
}

function populateSelectOptions(selectId, options, selected) {
    const select = document.getElementById(selectId);
    if (!select) return;
    select.innerHTML = '';
    (options || []).forEach((value) => {
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = value;
        if (selected && selected === value) opt.selected = true;
        select.appendChild(opt);
    });
}

function updateReworkPrefillButton() {
    const btn = document.getElementById('btn-rework-prefill');
    if (btn) btn.disabled = !mainFilename;
}

function populateReworkFormOptions(options) {
    if (!options) return;

    const legalSelect = document.getElementById('rework-legal-area');
    if (legalSelect) {
        legalSelect.innerHTML = '<option value="">— Выберите область —</option>';
        (options.legal_areas || []).forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.label;
            opt.dataset.examples = item.examples || '';
            legalSelect.appendChild(opt);
        });
    }

    const activitySelect = document.getElementById('rework-activity');
    if (activitySelect) {
        activitySelect.innerHTML = '<option value="">— Выберите сферу —</option>';
        (options.activity_spheres || []).forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.label;
            opt.dataset.description = item.description || '';
            activitySelect.appendChild(opt);
        });
    }

    const ownershipSelect = document.getElementById('rework-ownership');
    if (ownershipSelect) {
        ownershipSelect.innerHTML = '<option value="">— Выберите форму —</option>';
        (options.ownership_forms || []).forEach((group) => {
            const optgroup = document.createElement('optgroup');
            optgroup.label = group.group || '';
            (group.options || []).forEach((value) => {
                const opt = document.createElement('option');
                opt.value = value;
                opt.textContent = value;
                optgroup.appendChild(opt);
            });
            ownershipSelect.appendChild(optgroup);
        });
    }

    const secretSelect = document.getElementById('rework-state-secret');
    if (secretSelect) {
        secretSelect.innerHTML = '<option value="">— Выберите —</option>';
        (options.state_secret_options || []).forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.label;
            secretSelect.appendChild(opt);
        });
    }

    const audienceSelect = document.getElementById('rework-audience');
    if (audienceSelect) {
        audienceSelect.innerHTML = '<option value="">— Выберите аудиторию —</option>';
        (options.target_audiences || []).forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.label;
            audienceSelect.appendChild(opt);
        });
    }

    updateReworkLegalAreaHint();
    updateReworkActivityHint();
}

function setFieldValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value || '';
}

function setSelectValue(id, value) {
    const el = document.getElementById(id);
    if (!el || !value) return;
    el.value = value;
    if (el.value !== value) {
        const option = Array.from(el.options).find((opt) => opt.value === value);
        if (option) option.selected = true;
    }
}

async function loadCreateInstructionContent(forceReload = false) {
    if (!forceReload && createInstructionCache) {
        return createInstructionCache;
    }
    if (createInstructionLoading) {
        return createInstructionCache;
    }

    createInstructionLoading = true;
    try {
        const response = await fetch(`${API_BASE}/api/create-instruction?t=${Date.now()}`);
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.detail || 'Не удалось загрузить инструкцию');
        }
        const data = await response.json();
        createInstructionCache = renderInstructionMarkdown(data.content || '');
        const titleEl = document.getElementById('create-instruction-title');
        if (titleEl && data.title) {
            titleEl.textContent = data.title;
        }
        return createInstructionCache;
    } finally {
        createInstructionLoading = false;
    }
}

function setCreateInstructionBody(html, isError = false) {
    const body = document.getElementById('create-instruction-body');
    if (!body) {
        return;
    }
    body.innerHTML = html;
    body.classList.toggle('user-instruction-body-error', isError);
}

async function openCreateInstructionModal() {
    const modal = document.getElementById('create-instruction-modal');
    if (!modal) return;

    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    setCreateInstructionBody('<p class="user-instruction-loading">Загрузка инструкции…</p>');

    try {
        const html = await loadCreateInstructionContent();
        setCreateInstructionBody(html);
    } catch (error) {
        const message = formatCaughtError(error, 'Не удалось загрузить инструкцию');
        setCreateInstructionBody(
            `<p class="user-instruction-error">${escapeInstructionHtml(message)}</p>`,
            true,
        );
    }
}

function closeCreateInstructionModal() {
    const modal = document.getElementById('create-instruction-modal');
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
}

function setReworkAnalysisControlsEnabled(enabled) {
    const analysisInput = document.getElementById('rework-analysis-input');
    const uploadBtn = document.getElementById('btn-rework-analysis-upload');
    if (analysisInput) analysisInput.disabled = !enabled;
    if (uploadBtn) uploadBtn.disabled = !enabled;
}

function isReworkAnalysisNoneChecked() {
    return Boolean(document.getElementById('rework-analysis-none')?.checked);
}

function toggleReworkAnalysisNone() {
    reworkAnalysisSkipped = isReworkAnalysisNoneChecked();
    if (reworkAnalysisSkipped) {
        analysisFilename = null;
        analysisText = null;
        analysisAutoMatched = false;
        const analysisInput = document.getElementById('rework-analysis-input');
        if (analysisInput) analysisInput.value = '';
        setReworkAnalysisControlsEnabled(false);
        const status = document.getElementById('rework-analysis-status');
        if (status) {
            status.textContent =
                'Отчёт анализа не используется — при переработке будет выполнен автоматический анализ.';
            status.className = 'upload-status';
        }
        return;
    }

    setReworkAnalysisControlsEnabled(true);
    if (mainFilename) {
        const originalName = document.getElementById('rework-vnd-name')?.value?.trim()
            || mainFilename.replace(/^main_\d{8}_\d{6}_/i, '');
        autoLoadReworkAnalysis(originalName || mainFilename);
    } else {
        resetReworkAnalysisState();
    }
}

function resetReworkUploadFields() {
    const mainInput = document.getElementById('rework-main-input');
    const analysisInput = document.getElementById('rework-analysis-input');
    const analysisNone = document.getElementById('rework-analysis-none');
    const vndName = document.getElementById('rework-vnd-name');
    const mainStatus = document.getElementById('rework-main-status');
    reworkAnalysisSkipped = false;
    if (mainInput) mainInput.value = '';
    if (analysisInput) analysisInput.value = '';
    if (analysisNone) analysisNone.checked = false;
    setReworkAnalysisControlsEnabled(true);
    if (vndName) vndName.value = '';
    if (mainStatus) {
        mainStatus.textContent = '';
        mainStatus.className = 'upload-status';
    }
    const stage1Panel = document.getElementById('rework-step-form');
    if (stage1Panel) stage1Panel.style.display = 'none';
    const progress = document.getElementById('rework-progress');
    if (progress) {
        progress.style.display = 'none';
        progress.textContent = '';
    }
}

async function refreshReworkFormPrefill() {
    if (!mainFilename) return null;

    const vndName = document.getElementById('rework-vnd-name')?.value || '';
    const response = await fetch(`${API_BASE}/api/create/rework/stage1`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            main_filename: mainFilename,
            vnd_name: vndName,
            analysis_text: analysisText || '',
            analysis_filename: analysisFilename || '',
        }),
    });
    if (!response.ok) {
        throw new Error(await readApiError(response, 'Не удалось определить параметры документа'));
    }
    return response.json();
}

function resetReworkAnalysisState(message) {
    analysisFilename = null;
    analysisText = null;
    analysisAutoMatched = false;
    const status = document.getElementById('rework-analysis-status');
    if (status) {
        status.textContent = message || 'Отчёт будет подобран после загрузки основного документа.';
        status.className = 'upload-status';
    }
}

async function autoLoadReworkAnalysis(originalFilename) {
    const status = document.getElementById('rework-analysis-status');
    if (!originalFilename) {
        resetReworkAnalysisState();
        return;
    }
    if (isReworkAnalysisNoneChecked()) {
        toggleReworkAnalysisNone();
        return;
    }

    if (status) {
        status.textContent = '⏳ Поиск отчёта анализа...';
        status.className = 'upload-status';
    }

    try {
        const candidatesResponse = await fetch(
            `${API_BASE}/api/search/analysis-candidates?vnd_filename=${encodeURIComponent(originalFilename)}`
        );
        if (!candidatesResponse.ok) {
            throw new Error(await readApiError(candidatesResponse, 'Не удалось найти отчёт анализа'));
        }

        const candidatesData = await candidatesResponse.json();
        const best = candidatesData.auto_match || null;
        if (!best) {
            analysisFilename = null;
            analysisText = null;
            analysisAutoMatched = false;
            if (status) {
                status.textContent =
                    'Файл анализа не найден. Отметьте «Нет отчёта анализа» или загрузите отчёт вручную.';
                status.className = 'upload-status warning';
            }
            return;
        }

        const resolveResponse = await fetch(`${API_BASE}/api/search/resolve-analysis`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: best.filename,
                source: best.source || '',
            }),
        });
        if (!resolveResponse.ok) {
            throw new Error(await readApiError(resolveResponse, 'Не удалось прочитать отчёт анализа'));
        }

        const resolved = await resolveResponse.json();
        analysisFilename = null;
        analysisText = resolved.text || '';
        analysisAutoMatched = true;

        if (status) {
            status.textContent = `✓ Подобран автоматически: ${resolved.filename} (${resolved.source})`;
            status.className = 'upload-status success';
        }
    } catch (error) {
        console.warn('Автоподбор отчёта анализа:', error);
        analysisFilename = null;
        analysisText = null;
        analysisAutoMatched = false;
        if (status) {
            status.textContent =
                'Файл анализа не найден. Отметьте «Нет отчёта анализа» или загрузите отчёт вручную.';
            status.className = 'upload-status warning';
        }
    }
}

function fillLegalMultiSelect(selectId, options, selectedAreas) {
    const select = document.getElementById(selectId);
    if (!select) return;
    const selected = new Set(selectedAreas || []);
    select.innerHTML = '';
    (options || []).forEach((value) => {
        const opt = document.createElement('option');
        opt.value = value;
        opt.textContent = value;
        opt.selected = selected.has(value);
        select.appendChild(opt);
    });
}

function backToCreateMenu() {
    stopProgress();
    reworkFormReady = false;
    reworkFormState = null;
    mainFilename = null;
    analysisFilename = null;
    analysisText = null;
    analysisAutoMatched = false;
    reworkAnalysisSkipped = false;
    createQaMode = null;
    createQaState.rework.messages = [];
    createQaState.new.messages = [];
    closeCreateQaModal();
    closeCreateDocumentModal();
    leaveCreateResultView();
    document.body.classList.remove('create-new-active');
    document.body.classList.remove('create-rework-active');
    resetReworkUploadFields();
    resetReworkAnalysisState();
    const landing = document.getElementById('create-landing');
    const sharedPrep = document.getElementById('create-shared-prep');
    if (landing) landing.style.display = 'flex';
    if (sharedPrep) sharedPrep.style.display = 'none';
    document.getElementById('rework-panel').style.display = 'none';
    document.getElementById('new-panel').style.display = 'none';
    const formStep = document.getElementById('rework-step-form');
    if (formStep) formStep.style.display = 'none';
    const resultPanel = document.getElementById('rework-result-panel');
    if (resultPanel) resultPanel.style.display = 'none';
    document.body.classList.remove('analysis-active');
    updateReworkPrefillButton();
}

function enterCreateResultView(mode) {
    document.body.classList.add('analysis-active');
    document.body.classList.add('create-result-view');
    document.body.classList.remove('create-new-active');
    document.body.classList.remove('create-rework-active');
    document.getElementById('create-shared-prep').style.display = 'none';
    document.getElementById('new-panel').style.display = 'none';
    const reworkForm = document.getElementById('rework-step-form');
    if (reworkForm) reworkForm.style.display = 'none';

    if (mode === 'rework') {
        document.getElementById('rework-panel')?.classList.add('create-result-visible');
        document.getElementById('rework-panel').style.display = 'block';
        const resultPanel = document.getElementById('rework-result-panel');
        if (resultPanel) resultPanel.style.setProperty('display', 'flex', 'important');
    } else {
        document.getElementById('new-panel')?.classList.add('create-result-visible');
        document.getElementById('new-panel').style.display = 'block';
        showNewStep('document');
    }
}

function leaveCreateResultView() {
    document.body.classList.remove('create-result-view');
    document.getElementById('rework-panel')?.classList.remove('create-result-visible');
    document.getElementById('new-panel')?.classList.remove('create-result-visible');
}

function showExitWithoutSaveModal() {
    const modal = document.getElementById('exit-without-save-modal');
    if (!modal) return;
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
}

function closeExitWithoutSaveModal() {
    const modal = document.getElementById('exit-without-save-modal');
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
}

function confirmExitWithoutSave() {
    closeExitWithoutSaveModal();
    window.location.href = '/';
}

function showReworkMode() {
    document.body.classList.remove('create-new-active');
    document.body.classList.remove('create-rework-active');
    const landing = document.getElementById('create-landing');
    if (landing) landing.style.display = 'none';
    document.getElementById('new-panel').style.display = 'none';
    document.getElementById('rework-panel').style.display = 'block';
    const resultPanel = document.getElementById('rework-result-panel');
    if (resultPanel) resultPanel.style.display = 'none';
    const formStep = document.getElementById('rework-step-form');
    if (formStep) formStep.style.display = 'none';
    showReworkStep('prep');
    autoImportFromInIfAvailable();
}

async function autoImportFromInIfAvailable() {
    if (mainFilename) return;

    try {
        const latestResponse = await fetch(`${API_BASE}/api/vnd/latest-file`);
        if (!latestResponse.ok) return;

        const latest = await latestResponse.json();
        const sourceName = (latest.filename || '').trim();
        if (!sourceName) return;

        await useDocumentFromIn(sourceName);
    } catch (error) {
        console.warn('Автоподготовка документа из IN:', error);
    }
}

function showReworkStep(step) {
    const prep = document.getElementById('create-shared-prep');
    const form = document.getElementById('rework-step-form');
    const result = document.getElementById('rework-result-panel');
    const panel = document.getElementById('rework-panel');

    if (step === 'prep') {
        leaveCreateResultView();
        if (prep) prep.style.display = 'block';
        if (form) form.style.display = 'none';
        if (result) result.style.display = 'none';
        if (panel) panel.style.display = 'block';
        document.getElementById('new-panel').style.display = 'none';
        document.body.classList.remove('create-rework-active');
        updateReworkPrefillButton();
        return;
    }

    if (step === 'form') {
        leaveCreateResultView();
        if (prep) prep.style.display = 'none';
        if (form) form.style.setProperty('display', 'flex', 'important');
        if (result) result.style.display = 'none';
        if (panel) panel.style.display = 'block';
        document.getElementById('new-panel').style.display = 'none';
        document.body.classList.add('create-rework-active');
        applyReworkFormValidationHighlight();
    }
}

function showNewMode() {
    leaveCreateResultView();
    document.body.classList.remove('analysis-active');
    const landing = document.getElementById('create-landing');
    const sharedPrep = document.getElementById('create-shared-prep');
    if (landing) landing.style.display = 'none';
    if (sharedPrep) sharedPrep.style.display = 'none';
    document.getElementById('new-panel').style.display = 'block';
    document.getElementById('rework-panel').style.display = 'none';
    newFlowState = { form: null, followup_answers: {}, analysis: '', laws: [], download_result: null };
    highlightNewFormErrors([]);
    showNewStep('form');
}

function setCreateNewLayoutActive(active) {
    document.body.classList.toggle('create-new-active', Boolean(active));
}

function showNewStep(step) {
    const steps = {
        form: 'new-step-form',
        followup: 'new-step-followup',
        analysis: 'new-step-analysis',
        document: 'new-step-document',
    };
    const flexSteps = new Set(['form', 'followup', 'document']);
    Object.entries(steps).forEach(([key, id]) => {
        const el = document.getElementById(id);
        if (!el) return;
        const active = key === step;
        if (active) {
            el.style.setProperty('display', flexSteps.has(key) ? 'flex' : 'block', 'important');
        } else {
            el.style.setProperty('display', 'none', 'important');
        }
    });
    setCreateNewLayoutActive(step === 'form' || step === 'followup');
    if (step === 'document') {
        document.body.classList.add('analysis-active');
    } else if (step === 'form' || step === 'followup') {
        document.body.classList.remove('analysis-active');
    }
    if (step === 'form') {
        leaveCreateResultView();
    }
}

function getFollowupQuestionsForArea(legalArea) {
    const area = legalArea || 'custom';
    const map = createOptions?.new_document?.followup_questions || {};
    return map[area] || map.custom || [];
}

function readFollowupAnswersFromDom() {
    const legalArea = document.getElementById('new-legal-area')?.value || 'custom';
    const questions = getFollowupQuestionsForArea(legalArea);
    const raw = {};

    questions.forEach((q) => {
        if (q.type === 'multiselect') {
            raw[q.id] = Array.from(
                document.querySelectorAll(
                    `#new-followup-fields input[type="checkbox"][data-question-id="${q.id}"]:checked`
                )
            ).map((el) => el.value);
        } else {
            const el = document.getElementById(`followup-${q.id}`);
            raw[q.id] = el ? el.value : undefined;
        }
    });

    return { questions, raw };
}

function filterVisibleFollowupAnswers(questions, raw) {
    const answers = {};
    questions.forEach((q) => {
        if (!isFollowupQuestionVisible(q, raw)) return;
        if (raw[q.id] !== undefined) {
            answers[q.id] = raw[q.id];
        }
    });
    return answers;
}

function getFollowupQuestionLabel(questionId) {
    const legalArea = document.getElementById('new-legal-area')?.value || 'custom';
    const questions = getFollowupQuestionsForArea(legalArea);
    const q = questions.find((item) => item.id === questionId);
    return q?.label || questionId;
}

function isFollowupQuestionVisible(question, answers) {
    const cond = question.show_if;
    if (!cond) return true;
    const value = answers[cond.field];
    if (cond.values) {
        return cond.values.includes(value);
    }
    if (cond.contains) {
        if (Array.isArray(value)) return value.includes(cond.contains);
        return String(value || '').split(',').map((s) => s.trim()).includes(cond.contains);
    }
    return true;
}

function renderFollowupQuestions() {
    const container = document.getElementById('new-followup-fields');
    if (!container) return;

    const legalArea = document.getElementById('new-legal-area')?.value || 'custom';
    const questions = getFollowupQuestionsForArea(legalArea);
    const { raw } = readFollowupAnswersFromDom();
    const answers = { ...(newFlowState.followup_answers || {}), ...raw };
    const visibilityCtx = { ...answers, ...raw };
    container.innerHTML = '';

    questions.forEach((q) => {
        if (!isFollowupQuestionVisible(q, visibilityCtx)) return;

        const wrap = document.createElement('div');
        wrap.className = 'stage1-field';
        if (q.show_if) wrap.classList.add('followup-nested-field');
        wrap.dataset.field = q.id;

        const label = document.createElement('label');
        label.textContent = q.label + (q.required ? ' *' : '');
        label.setAttribute('for', `followup-${q.id}`);
        wrap.appendChild(label);

        const qType = q.type || 'text';
        if (qType === 'select') {
            const select = document.createElement('select');
            select.id = `followup-${q.id}`;
            select.className = 'create-text-input';
            select.innerHTML = '<option value="">— Выберите —</option>';
            (q.options || []).forEach((opt) => {
                const option = document.createElement('option');
                option.value = opt.id;
                option.textContent = opt.label;
                if (answers[q.id] === opt.id) option.selected = true;
                select.appendChild(option);
            });
            select.addEventListener('change', onFollowupFieldChange);
            wrap.appendChild(select);
        } else if (qType === 'multiselect') {
            const box = document.createElement('div');
            box.className = 'new-followup-multiselect';
            const selected = Array.isArray(answers[q.id]) ? answers[q.id] : [];
            (q.options || []).forEach((opt) => {
                const row = document.createElement('label');
                row.className = 'new-followup-option';
                const cb = document.createElement('input');
                cb.type = 'checkbox';
                cb.value = opt.id;
                cb.dataset.questionId = q.id;
                cb.checked = selected.includes(opt.id);
                cb.addEventListener('change', onFollowupFieldChange);
                row.appendChild(cb);
                row.appendChild(document.createTextNode(opt.label));
                box.appendChild(row);
            });
            wrap.appendChild(box);
        } else if (qType === 'textarea') {
            const ta = document.createElement('textarea');
            ta.id = `followup-${q.id}`;
            ta.rows = 3;
            ta.className = 'create-text-input';
            ta.placeholder = q.placeholder || '';
            ta.value = answers[q.id] || '';
            ta.addEventListener('input', onFollowupFieldChange);
            wrap.appendChild(ta);
        } else {
            const input = document.createElement('input');
            input.type = 'text';
            input.id = `followup-${q.id}`;
            input.className = 'create-text-input';
            input.placeholder = q.placeholder || '';
            input.value = answers[q.id] || '';
            input.addEventListener('input', onFollowupFieldChange);
            wrap.appendChild(input);
        }

        container.appendChild(wrap);
    });
}

function onFollowupFieldChange() {
    const prev = { ...(newFlowState.followup_answers || {}) };
    const { questions, raw } = readFollowupAnswersFromDom();
    newFlowState.followup_answers = filterVisibleFollowupAnswers(questions, raw);

    let needRerender = false;
    let revealedId = null;
    questions.forEach((q) => {
        if (!q.show_if) return;
        const wasVisible = isFollowupQuestionVisible(q, prev);
        const nowVisible = isFollowupQuestionVisible(q, raw);
        if (wasVisible !== nowVisible) {
            needRerender = true;
            if (nowVisible) revealedId = q.id;
        }
    });

    if (needRerender) {
        renderFollowupQuestions();
        if (revealedId) {
            requestAnimationFrame(() => {
                const el = document.querySelector(`#new-followup-fields .stage1-field[data-field="${revealedId}"]`);
                el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            });
        }
    }
}

function collectFollowupAnswers() {
    const { questions, raw } = readFollowupAnswersFromDom();
    return filterVisibleFollowupAnswers(questions, raw);
}

function validateFollowupClient() {
    const { questions, raw } = readFollowupAnswersFromDom();
    const missing = [];

    questions.forEach((q) => {
        if (!isFollowupQuestionVisible(q, raw)) return;
        if (!q.required) return;
        const val = raw[q.id];
        if (q.type === 'multiselect') {
            if (!val || !val.length) missing.push(q.id);
        } else if (!String(val || '').trim()) {
            missing.push(q.id);
        }
    });
    return missing;
}

function highlightFollowupErrors(missing) {
    if (missing?.length) {
        newFlowState.followup_answers = collectFollowupAnswers();
        renderFollowupQuestions();
    }

    document.querySelectorAll('#new-followup-fields .stage1-field').forEach((el) => {
        el.classList.remove('field-error');
    });

    const notFound = [];
    (missing || []).forEach((id) => {
        const el = document.querySelector(`#new-followup-fields .stage1-field[data-field="${id}"]`);
        if (el) {
            el.classList.add('field-error');
        } else {
            notFound.push(getFollowupQuestionLabel(id));
        }
    });

    const errorBox = document.getElementById('new-followup-error');
    if (errorBox) {
        if (missing?.length) {
            errorBox.style.display = 'block';
            if (notFound.length) {
                errorBox.textContent = `Заполните обязательные поля: ${notFound.join('; ')}.`;
            } else {
                errorBox.textContent = 'Ответьте на все обязательные вопросы (подсвечены).';
                const firstError = document.querySelector('#new-followup-fields .stage1-field.field-error');
                firstError?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        } else {
            errorBox.style.display = 'none';
            errorBox.textContent = '';
        }
    }
}

function runNewGoToFollowup() {
    const form = collectNewFormData();
    const missing = validateNewFormClient(form);
    highlightNewFormErrors(missing);
    if (missing.length) return;

    newFlowState.followup_answers = newFlowState.followup_answers || {};
    refreshFollowupQuestionOptions().then(() => {
        renderFollowupQuestions();
        showNewStep('followup');
    });
}

function updateLegalAreaHint() {
    const select = document.getElementById('new-legal-area');
    const hint = document.getElementById('new-legal-area-hint');
    if (!select || !hint) return;
    const option = select.selectedOptions[0];
    const examples = option?.dataset?.examples || '';
    hint.textContent = examples ? `Примеры: ${examples.replace(/;/g, ' · ')}` : '';
}

function updateActivityHint() {
    const select = document.getElementById('new-activity');
    const hint = document.getElementById('new-activity-hint');
    if (!select || !hint) return;
    const option = select.selectedOptions[0];
    hint.textContent = option?.dataset?.description || '';
}

function toggleNewCustomField(kind) {
    if (kind === 'legal') {
        const isCustom = document.getElementById('new-legal-area')?.value === 'custom';
        const wrap = document.getElementById('new-legal-custom-wrap');
        if (wrap) wrap.style.display = isCustom ? 'block' : 'none';
        newFlowState.followup_answers = {};
        updateLegalAreaHint();
    }
    if (kind === 'audience') {
        const isCustom = document.getElementById('new-audience')?.value === 'custom';
        const wrap = document.getElementById('new-audience-custom-wrap');
        if (wrap) wrap.style.display = isCustom ? 'block' : 'none';
    }
}

function collectNewFormData() {
    return {
        document_name: document.getElementById('new-doc-name')?.value?.trim() || '',
        document_topic: document.getElementById('new-doc-topic')?.value?.trim() || '',
        legal_area: document.getElementById('new-legal-area')?.value || '',
        legal_area_custom: document.getElementById('new-legal-custom')?.value?.trim() || '',
        activity_sphere: document.getElementById('new-activity')?.value || '',
        ownership_form: document.getElementById('new-ownership')?.value || '',
        state_secret: document.getElementById('new-state-secret')?.value || '',
        employees_count: document.getElementById('new-employees')?.value?.trim() || '',
        branches: document.getElementById('new-branches')?.value?.trim() || '',
        target_audience: document.getElementById('new-audience')?.value || '',
        target_audience_custom: document.getElementById('new-audience-custom')?.value?.trim() || '',
    };
}

function validateNewFormClient(form) {
    const missing = [];
    const checks = [
        ['document_name', form.document_name],
        ['document_topic', form.document_topic],
        ['legal_area', form.legal_area],
        ['activity_sphere', form.activity_sphere],
        ['ownership_form', form.ownership_form],
        ['state_secret', form.state_secret],
        ['employees_count', form.employees_count],
        ['branches', form.branches],
        ['target_audience', form.target_audience],
    ];
    checks.forEach(([field, value]) => {
        if (!value) missing.push(field);
    });
    if (form.legal_area === 'custom' && !form.legal_area_custom) {
        missing.push('legal_area_custom');
    }
    if (form.target_audience === 'custom' && !form.target_audience_custom) {
        missing.push('target_audience_custom');
    }
    return missing;
}

function highlightNewFormErrors(missing) {
    document.querySelectorAll('#new-step-form .stage1-field').forEach((el) => {
        el.classList.remove('field-error');
    });
    (missing || []).forEach((field) => {
        const el = document.querySelector(`#new-step-form .stage1-field[data-field="${field}"]`);
        if (el) el.classList.add('field-error');
    });
    const errorBox = document.getElementById('new-form-error');
    if (errorBox) {
        if (missing?.length) {
            errorBox.style.display = 'block';
            errorBox.textContent = 'Заполните все обязательные поля (подсвечены).';
        } else {
            errorBox.style.display = 'none';
            errorBox.textContent = '';
        }
    }
}

async function runNewAnalyze() {
    const form = collectNewFormData();
    const missing = validateNewFormClient(form);
    highlightNewFormErrors(missing);
    if (missing.length) {
        showNewStep('form');
        return;
    }

    const followup = collectFollowupAnswers();
    const followupMissing = validateFollowupClient();
    highlightFollowupErrors(followupMissing);
    if (followupMissing.length) return;

    const payload = { ...form, followup_answers: followup };

    const btn = document.getElementById('btn-new-analyze');
    if (btn) btn.disabled = true;
    showProgressBlock('new-analyze-progress-followup', 'Выполняется правовой анализ...');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 600000);

    try {
        const response = await fetch(`${API_BASE}/api/create/new/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            const detail = errData.detail || {};
            if (detail.missing_fields?.length) {
                showNewStep('form');
                highlightNewFormErrors(detail.missing_fields);
                return;
            }
            if (detail.missing_followup?.length) {
                highlightFollowupErrors(detail.missing_followup);
                return;
            }
            throw new Error(await readApiError(response, 'Не удалось выполнить анализ'));
        }

        const data = await response.json();
        newFlowState.form = data.form || payload;
        newFlowState.followup_answers = followup;
        newFlowState.analysis = data.analysis || '';
        newFlowState.laws = data.laws || [];

        completeProgress('new-analyze-progress-followup');
        const progress = document.getElementById('new-analyze-progress-followup');
        if (progress) progress.style.display = 'none';

        document.getElementById('new-analysis-result').textContent = newFlowState.analysis;
        showNewStep('analysis');
    } catch (error) {
        stopProgress();
        const progress = document.getElementById('new-analyze-progress-followup');
        if (progress) {
            progress.style.display = 'block';
            progress.className = 'stage1-note warning';
            progress.textContent = '❌ ' + formatCaughtError(error, 'Ошибка анализа');
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function runNewContinue() {
    if (!newFlowState.analysis || !newFlowState.form) {
        alert('Сначала выполните анализ');
        return;
    }

    showNewStep('document');
    showProgressBlock(
        'new-generate-progress',
        'Формирую план и генерирую документ по разделам (может занять несколько минут)...'
    );

    const btn = document.getElementById('btn-new-continue');
    if (btn) btn.disabled = true;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 600000);

    try {
        const response = await fetch(`${API_BASE}/api/create/new/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                form: newFlowState.form,
                analysis: newFlowState.analysis,
                laws: newFlowState.laws,
            }),
            signal: controller.signal,
        });
        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось сформировать документ'));
        }

        const data = await response.json();
        newFlowState.download_result = data.download_result;
        newFlowState.laws = data.laws || newFlowState.laws;

        completeProgress('new-generate-progress');
        const progress = document.getElementById('new-generate-progress');
        if (progress) progress.style.display = 'none';

        createQaState.new.messages = [];
        lastNewDocument = data.document || '';
        enterCreateResultView('new');
    } catch (error) {
        stopProgress();
        const progress = document.getElementById('new-generate-progress');
        if (progress) {
            progress.className = 'stage1-note warning';
            progress.textContent = '❌ ' + formatCaughtError(error, 'Ошибка формирования');
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

function stopProgress() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

function showProgressBlock(containerId, message) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.style.display = 'block';
    container.className = 'stage1-note stage1-note-progress';
    container.innerHTML = `
        <div class="stage1-progress">
            <p class="progress-message">${message}</p>
            <div class="progress-bar-wrapper">
                <div class="progress-bar">
                    <div class="progress-bar-fill" id="${containerId}-fill" style="width: 0%"></div>
                </div>
                <span class="progress-percent" id="${containerId}-percent">0%</span>
            </div>
        </div>
    `;
    stopProgress();
    let current = 0;
    progressInterval = setInterval(() => {
        if (current >= 92) return;
        current += current < 50 ? 2 : 1;
        const fill = document.getElementById(`${containerId}-fill`);
        const percent = document.getElementById(`${containerId}-percent`);
        if (fill) fill.style.width = `${current}%`;
        if (percent) percent.textContent = `${current}%`;
    }, 180);
}

function completeProgress(containerId) {
    stopProgress();
    const fill = document.getElementById(`${containerId}-fill`);
    const percent = document.getElementById(`${containerId}-percent`);
    if (fill) fill.style.width = '100%';
    if (percent) percent.textContent = '100%';
}

async function uploadCreateFile(kind) {
    const inputId = kind === 'main' ? 'rework-main-input' : 'rework-analysis-input';
    const statusId = kind === 'main' ? 'rework-main-status' : 'rework-analysis-status';
    const input = document.getElementById(inputId);
    const status = document.getElementById(statusId);
    const file = input?.files?.[0];

    if (!file) {
        alert('Выберите файл');
        return;
    }

    if (kind === 'analysis' && !mainFilename) {
        alert('Сначала загрузите основной (перерабатываемый) документ.');
        if (input) input.value = '';
        return;
    }

    status.textContent = '⏳ Загрузка...';
    status.className = 'upload-status';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('kind', kind);

    const uploadUrl = kind === 'analysis'
        ? `${API_BASE}/api/create/upload?kind=${kind}&main_filename=${encodeURIComponent(mainFilename)}`
        : `${API_BASE}/api/create/upload?kind=${kind}`;

    try {
        const response = await fetch(uploadUrl, {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось загрузить файл'));
        }
        const data = await response.json();
        if (kind === 'main') {
            mainFilename = data.filename;
            reworkFormReady = false;
            if (!document.getElementById('rework-vnd-name').value) {
                document.getElementById('rework-vnd-name').value = file.name.replace(/\.[^/.]+$/, '');
            }
            updateReworkPrefillButton();
            status.textContent = `✓ ВНД загружен в IN/: ${data.filename}`;
            status.className = 'upload-status success';
            await autoLoadReworkAnalysis(file.name);
            return;
        } else {
            analysisFilename = data.filename;
            analysisText = null;
            analysisAutoMatched = false;
            status.textContent = `✓ Отчёт загружен в OUT/: ${data.filename}`;
            status.className = 'upload-status success';
        }
    } catch (error) {
        if (kind === 'analysis') {
            analysisFilename = null;
            analysisText = null;
            analysisAutoMatched = false;
            if (input) input.value = '';
        }
        const message = formatCaughtError(error, 'Ошибка загрузки');
        status.textContent = '✗ ' + message;
        status.className = 'upload-status error';
        if (kind === 'analysis') {
            alert('❌ ' + message);
        }
    }
}

function collectReworkFormData() {
    return {
        document_name: document.getElementById('rework-doc-name')?.value?.trim() || '',
        document_topic: document.getElementById('rework-doc-topic')?.value?.trim() || '',
        legal_area: document.getElementById('rework-legal-area')?.value || '',
        legal_area_custom: document.getElementById('rework-legal-custom')?.value?.trim() || '',
        activity_sphere: document.getElementById('rework-activity')?.value || '',
        ownership_form: document.getElementById('rework-ownership')?.value || '',
        state_secret: document.getElementById('rework-state-secret')?.value || '',
        employees_count: document.getElementById('rework-employees')?.value?.trim() || '',
        branches: document.getElementById('rework-branches')?.value?.trim() || '',
        target_audience: document.getElementById('rework-audience')?.value || '',
        target_audience_custom: document.getElementById('rework-audience-custom')?.value?.trim() || '',
    };
}

function highlightReworkFormErrors(missing) {
    document.querySelectorAll('#rework-step-form .stage1-field').forEach((el) => {
        el.classList.remove('field-error');
    });
    (missing || []).forEach((field) => {
        const el = document.querySelector(`#rework-step-form .stage1-field[data-field="${field}"]`);
        if (el) el.classList.add('field-error');
    });
    const errorBox = document.getElementById('rework-form-error');
    if (errorBox) {
        if (missing?.length) {
            errorBox.style.display = 'block';
            errorBox.textContent = missing.length === 1
                ? 'Не все обязательные поля заполнены автоматически — укажите недостающее значение (подсвечено).'
                : 'Не все обязательные поля заполнены автоматически — укажите недостающие значения (подсвечены).';
        } else {
            errorBox.style.display = 'none';
            errorBox.textContent = '';
        }
    }
}

function applyReworkFormValidationHighlight() {
    const missing = validateNewFormClient(collectReworkFormData());
    highlightReworkFormErrors(missing);
}

function refreshReworkFormValidation() {
    applyReworkFormValidationHighlight();
}

function setupReworkFormValidationRefresh() {
    const form = document.getElementById('rework-step-form');
    if (!form || form.dataset.validationBound) return;
    form.dataset.validationBound = '1';
    form.addEventListener('input', refreshReworkFormValidation);
    form.addEventListener('change', refreshReworkFormValidation);
}

function updateReworkLegalAreaHint() {
    const select = document.getElementById('rework-legal-area');
    const hint = document.getElementById('rework-legal-area-hint');
    if (!select || !hint) return;
    const option = select.selectedOptions[0];
    const examples = option?.dataset?.examples || '';
    hint.textContent = examples ? `Примеры: ${examples.replace(/;/g, ' · ')}` : '';
}

function updateReworkActivityHint() {
    const select = document.getElementById('rework-activity');
    const hint = document.getElementById('rework-activity-hint');
    if (!select || !hint) return;
    const option = select.selectedOptions[0];
    hint.textContent = option?.dataset?.description || '';
}

function toggleReworkCustomField(kind) {
    if (kind === 'legal') {
        const isCustom = document.getElementById('rework-legal-area')?.value === 'custom';
        const wrap = document.getElementById('rework-legal-custom-wrap');
        if (wrap) wrap.style.display = isCustom ? 'block' : 'none';
        updateReworkLegalAreaHint();
    }
    if (kind === 'audience') {
        const isCustom = document.getElementById('rework-audience')?.value === 'custom';
        const wrap = document.getElementById('rework-audience-custom-wrap');
        if (wrap) wrap.style.display = isCustom ? 'block' : 'none';
    }
}

function populateReworkForm(data) {
    reworkFormState = data;
    const form = data.form || {};
    if (data.options) {
        populateReworkFormOptions(data.options);
    }

    setFieldValue('rework-doc-name', form.document_name);
    setFieldValue('rework-doc-topic', form.document_topic);
    setSelectValue('rework-legal-area', form.legal_area);
    setFieldValue('rework-legal-custom', form.legal_area_custom);
    toggleReworkCustomField('legal');
    setSelectValue('rework-activity', form.activity_sphere);
    setSelectValue('rework-ownership', form.ownership_form);
    setSelectValue('rework-state-secret', form.state_secret);
    setFieldValue('rework-employees', form.employees_count);
    setFieldValue('rework-branches', form.branches);
    setSelectValue('rework-audience', form.target_audience);
    setFieldValue('rework-audience-custom', form.target_audience_custom);
    toggleReworkCustomField('audience');
    applyReworkFormValidationHighlight();
}

function reworkFormToStage1(form) {
    const legalMap = {
        corporate: 'Другое',
        personal_data: 'Персональные данные',
        confidentiality_ib: 'Информационная безопасность',
        labor: 'Трудовое законодательство',
        contracts_procurement: 'Закупки и контрактная система',
        finance_risks: 'Безопасность финансовых (банковских) операций',
        compliance_ethics: 'Противодействие коррупции',
        custom: 'Другое',
    };
    const activityMap = {
        finance: 'Финансы',
        it_telecom: 'Информационные технологии (IT)',
        trade_services: 'Услуги',
        manufacturing: 'Производство',
        construction_realestate: 'Строительство',
        social: 'Образовательные услуги',
    };

    let legalLabel = legalMap[form.legal_area] || 'Другое';
    if (form.legal_area === 'custom' && form.legal_area_custom) {
        legalLabel = form.legal_area_custom;
    }

    const ownership = form.ownership_form || '';
    let ownershipOld = 'Частные компании';
    if (
        /^Федеральные/.test(ownership)
        || /^Органы государственной власти субъектов/.test(ownership)
        || /^Органы местного самоуправления/.test(ownership)
        || /государствен/i.test(ownership)
        || /муниципаль/i.test(ownership)
    ) {
        ownershipOld = 'Государственные предприятия';
    }

    return {
        activity_sphere: activityMap[form.activity_sphere] || 'Другое',
        ownership_form: ownershipOld,
        legal_areas: [legalLabel],
    };
}

async function goToReworkForm() {
    if (!mainFilename) {
        alert('Загрузите основной (перерабатываемый) документ');
        return;
    }

    const btn = document.getElementById('btn-rework-prefill');
    if (btn) btn.disabled = true;

    try {
        const data = await refreshReworkFormPrefill();
        populateReworkForm(data);
        reworkFormReady = true;
        showReworkStep('form');
    } catch (error) {
        alert('❌ ' + formatCaughtError(error, 'Не удалось подготовить параметры'));
    } finally {
        updateReworkPrefillButton();
    }
}

async function useDocumentFromIn(filename) {
    const status = document.getElementById('rework-main-status');
    if (status) {
        status.textContent = '⏳ Подготовка документа из папки IN...';
        status.className = 'upload-status';
    }

    try {
        let sourceName = (filename || '').trim();
        if (!sourceName) {
            const latestResponse = await fetch(`${API_BASE}/api/vnd/latest-file`);
            if (!latestResponse.ok) {
                throw new Error(await readApiError(
                    latestResponse,
                    'В папке IN нет документа. Сначала выполните «Анализ ВНД» или загрузите файл вручную.',
                ));
            }
            const latest = await latestResponse.json();
            sourceName = latest.filename || '';
        }

        const importResponse = await fetch(`${API_BASE}/api/create/rework/import-from-in`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: sourceName }),
        });
        if (!importResponse.ok) {
            throw new Error(await readApiError(importResponse, 'Не удалось подготовить документ из IN'));
        }

        const data = await importResponse.json();
        mainFilename = data.filename;
        reworkFormReady = false;

        const vndNameInput = document.getElementById('rework-vnd-name');
        if (vndNameInput && !vndNameInput.value) {
            vndNameInput.value = sourceName.replace(/\.[^/.]+$/, '');
        }

        if (status) {
            status.textContent = `✓ ВНД из IN/: ${data.filename}`;
            status.className = 'upload-status success';
        }

        updateReworkPrefillButton();
        await autoLoadReworkAnalysis(sourceName);
    } catch (error) {
        if (status) {
            status.textContent = '✗ ' + formatCaughtError(error, 'Не удалось взять документ из IN');
            status.className = 'upload-status error';
        }
    }
}

function isReworkNotFoundError(error) {
    const message = formatCaughtError(error, '').toLowerCase();
    return (
        message.includes('не найден')
        || message.includes('запрашиваемые данные не найдены')
        || message.includes('status: 404')
        || message.includes('404')
    );
}

async function runReworkPipeline(mainFilename, vndName, stage1, hasAnalysis) {
    if (hasAnalysis) {
        try {
            return await runReworkWithUploadedAnalysis(mainFilename, vndName, stage1);
        } catch (error) {
            if (!isReworkNotFoundError(error)) {
                throw error;
            }
            analysisFilename = null;
            analysisText = null;
            analysisAutoMatched = false;
            showProgressBlock(
                'rework-progress',
                'Отчёт не найден на сервере. Выполняется правовой анализ...',
            );
        }
    }

    return runReworkAnalyzeAndGenerate(mainFilename, vndName, stage1);
}

async function runReworkAnalyzeAndGenerate(mainFilename, vndName, stage1) {
    showProgressBlock('rework-progress', 'Выполняется правовой анализ документа...');

    const analyzeController = new AbortController();
    const analyzeTimeout = setTimeout(() => analyzeController.abort(), 600000);

    const analyzeResponse = await fetch(`${API_BASE}/api/create/rework/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            main_filename: mainFilename,
            vnd_name: vndName,
            stage1,
        }),
        signal: analyzeController.signal,
    });
    clearTimeout(analyzeTimeout);

    if (!analyzeResponse.ok) {
        throw new Error(await readApiError(analyzeResponse, 'Не удалось выполнить правовой анализ'));
    }

    const analyzeData = await analyzeResponse.json();
    showProgressBlock('rework-progress', 'Перерабатываю документ...');

    const generateController = new AbortController();
    const generateTimeout = setTimeout(() => generateController.abort(), 600000);

    const generateResponse = await fetch(`${API_BASE}/api/create/rework/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            main_filename: mainFilename,
            vnd_name: vndName,
            stage1: analyzeData.stage1 || stage1,
            analysis_text: analyzeData.analysis_text || '',
            analysis_meta: analyzeData.analysis_meta || null,
        }),
        signal: generateController.signal,
    });
    clearTimeout(generateTimeout);

    if (!generateResponse.ok) {
        throw new Error(await readApiError(generateResponse, 'Не удалось выполнить переработку'));
    }

    return generateResponse.json();
}

async function runReworkWithUploadedAnalysis(mainFilename, vndName, stage1) {
    showProgressBlock('rework-progress', 'Перерабатываю документ...');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 600000);

    const response = await fetch(`${API_BASE}/api/create/rework/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            main_filename: mainFilename,
            analysis_filename: analysisFilename || undefined,
            analysis_text: analysisText || undefined,
            vnd_name: vndName,
            stage1: stage1,
        }),
        signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!response.ok) {
        throw new Error(await readApiError(response, 'Не удалось выполнить переработку'));
    }

    return response.json();
}

function showReworkResult(data, resultPanel) {
    createQaState.rework.messages = [];
    lastReworkDocument = data.document || '';
    lastReworkChangesReport = data.changes_report || '';
    document.getElementById('rework-changes-report').textContent =
        lastReworkChangesReport || 'Отчёт о переработке формируется…';
    renderReworkDocument(lastReworkDocument);
    resultPanel.style.display = 'flex';
    enterCreateResultView('rework');
}

async function runReworkFromForm() {
    if (!mainFilename) {
        alert('Загрузите основной (перерабатываемый) документ');
        return;
    }

    const form = collectReworkFormData();
    const missing = validateNewFormClient(form);
    highlightReworkFormErrors(missing);
    if (missing.length) return;

    const btn = document.getElementById('btn-rework-start');
    const vndName = form.document_name || document.getElementById('rework-vnd-name')?.value || '';
    const progress = document.getElementById('rework-progress');
    const resultPanel = document.getElementById('rework-result-panel');
    const hasAnalysis = Boolean(
        analysisFilename || (analysisText && analysisText.trim())
    );
    const stage1 = reworkFormToStage1(form);

    if (btn) btn.disabled = true;
    if (resultPanel) resultPanel.style.display = 'none';
    showProgressBlock('rework-progress', hasAnalysis
        ? 'Перерабатываю документ...'
        : 'Выполняется правовой анализ документа...');

    try {
        const data = await runReworkPipeline(mainFilename, vndName, stage1, hasAnalysis);

        completeProgress('rework-progress');
        if (progress) progress.style.display = 'none';
        showReworkResult(data, resultPanel);
    } catch (error) {
        stopProgress();
        if (progress) {
            progress.style.display = 'block';
            progress.className = 'stage1-note warning';
            progress.textContent = '❌ ' + formatCaughtError(error, 'Ошибка переработки');
        }
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function runNewStep2() {
    await runNewAnalyze();
}

async function runNewGenerate() {
    await runNewContinue();
}

async function downloadCreateDocument(mode, format = 'docx') {
    const documentText = mode === 'rework' ? lastReworkDocument : lastNewDocument;
    if (!documentText) {
        alert('Нет документа для скачивания');
        return;
    }

    const title = mode === 'rework'
        ? (document.getElementById('rework-vnd-name')?.value || 'Переработка')
        : (newFlowState.form?.document_name || 'Новый ВНД');

    try {
        const filename = await downloadFromPost(
            `${API_BASE}/api/create/save`,
            {
                document: documentText,
                title,
                format,
                mode,
            },
            `ВНД_${title}.docx`,
            'Не удалось скачать документ',
        );
        alert(`✅ Документ скачан\n\n📄 ${filename}`);
    } catch (error) {
        alert('❌ ' + formatCaughtError(error, 'Ошибка скачивания'));
    }
}

function getCreateQaDocument(mode) {
    return mode === 'rework' ? lastReworkDocument : lastNewDocument;
}

function getCreateQaTitle(mode) {
    if (mode === 'rework') {
        return document.getElementById('rework-vnd-name')?.value?.trim() || 'Переработка';
    }
    return newFlowState.form?.document_name || 'Новый ВНД';
}

function renderCreateQaMessages() {
    const container = document.getElementById('create-qa-messages');
    if (!container || !createQaMode) return;

    const messages = createQaState[createQaMode].messages;
    container.innerHTML = '';
    messages.forEach((msg) => {
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

function openCreateQaModal(mode) {
    openCreateDocumentModal(mode, { focusChat: true });
}

function closeCreateQaModal() {
    closeCreateDocumentModal();
}

async function sendCreateQaMessage() {
    if (!createQaMode || createQaSending) return;

    const input = document.getElementById('create-qa-input');
    const text = input?.value?.trim();
    if (!text) return;

    const documentText = getCreateQaDocument(createQaMode);
    const state = createQaState[createQaMode];
    const sendBtn = document.getElementById('btn-create-qa-send');

    createQaSending = true;
    if (sendBtn) sendBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/api/create/qa/message`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: createQaMode,
                document: documentText,
                title: getCreateQaTitle(createQaMode),
                messages: state.messages,
                user_message: text,
            }),
        });

        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось отправить вопрос'));
        }

        const data = await response.json();
        state.messages = data.messages || state.messages;
        if (input) input.value = '';
        renderCreateQaMessages();
    } catch (error) {
        alert('❌ ' + formatCaughtError(error, 'Ошибка диалога'));
    } finally {
        createQaSending = false;
        if (sendBtn) sendBtn.disabled = false;
    }
}

async function downloadCreateQaDialog() {
    if (!createQaMode) return;

    const state = createQaState[createQaMode];
    const hasUserMessages = state.messages.some((msg) => msg.role === 'user');
    if (!hasUserMessages) {
        alert('В диалоге пока нет вопросов для скачивания');
        return;
    }

    try {
        const title = getCreateQaTitle(createQaMode);
        const filename = await downloadFromPost(
            `${API_BASE}/api/create/qa/save`,
            {
                mode: createQaMode,
                title,
                messages: state.messages,
            },
            `Диалог_${title}.txt`,
            'Не удалось скачать диалог',
        );
        alert(`✅ Диалог скачан\n\n📄 ${filename}`);
    } catch (error) {
        alert('❌ ' + formatCaughtError(error, 'Ошибка скачивания диалога'));
    }
}

window.toggleReworkAnalysisNone = toggleReworkAnalysisNone;
window.goToReworkForm = goToReworkForm;
window.showReworkStep = showReworkStep;
window.runReworkFromForm = runReworkFromForm;
window.toggleReworkCustomField = toggleReworkCustomField;
window.updateReworkActivityHint = updateReworkActivityHint;
window.openCreateInstructionModal = openCreateInstructionModal;
window.closeCreateInstructionModal = closeCreateInstructionModal;
window.showReworkMode = showReworkMode;
window.showNewMode = showNewMode;
window.backToCreateMenu = backToCreateMenu;
window.uploadCreateFile = uploadCreateFile;
window.useDocumentFromIn = useDocumentFromIn;
window.startRework = runReworkFromForm;
window.runNewGoToFollowup = runNewGoToFollowup;
window.runNewAnalyze = runNewAnalyze;
window.runNewContinue = runNewContinue;
window.toggleNewCustomField = toggleNewCustomField;
window.updateActivityHint = updateActivityHint;
window.runNewStep2 = runNewStep2;
window.runNewGenerate = runNewGenerate;
window.downloadCreateDocument = downloadCreateDocument;
window.showNewStep = showNewStep;
window.showExitWithoutSaveModal = showExitWithoutSaveModal;
window.closeExitWithoutSaveModal = closeExitWithoutSaveModal;
window.confirmExitWithoutSave = confirmExitWithoutSave;
window.downloadCreateDocumentFromModal = downloadCreateDocumentFromModal;
window.openCreateDocumentModal = openCreateDocumentModal;
window.closeCreateDocumentModal = closeCreateDocumentModal;
window.openCreateQaModal = openCreateQaModal;
window.closeCreateQaModal = closeCreateQaModal;
window.sendCreateQaMessage = sendCreateQaMessage;
window.downloadCreateQaDialog = downloadCreateQaDialog;
