// Страница анализа ВНД

// API_BASE можно изменить, если backend на другом порту/хосте
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://localhost:8011' 
    : '';

let uploadedDocumentText = null;
let uploadedDocumentName = null;
let uploadedFilename = null;
let detectedFederalRefs = [];
let allDetectedFederalRefs = [];
let stage1Data = null;
let currentVndName = '';
let lastStage1Answers = null;
let lastAnalysisReport = '';
let analysisInProgress = false;
let stage1ProgressInterval = null;
let stage2ProgressInterval = null;

const FEDERAL_REFS_SESSION_KEY = 'wnd_federal_refs_session';

function clearFederalRefsSession() {
    detectedFederalRefs = [];
    allDetectedFederalRefs = [];
    sessionStorage.removeItem(FEDERAL_REFS_SESSION_KEY);
    fetch(`${API_BASE}/api/vnd/federal-references-session`, { method: 'DELETE' }).catch(() => {});
}

function saveFederalRefsSession(data) {
    if (!data) return;
    sessionStorage.setItem(FEDERAL_REFS_SESSION_KEY, JSON.stringify({
        ...data,
        saved_at: new Date().toISOString()
    }));
}

function getFederalRefsSession() {
    try {
        const raw = sessionStorage.getItem(FEDERAL_REFS_SESSION_KEY);
        return raw ? JSON.parse(raw) : null;
    } catch (error) {
        console.warn('Не удалось прочитать сохранённый результат поиска ссылок:', error);
        return null;
    }
}

window.getFederalRefsSession = getFederalRefsSession;
window.clearFederalRefsSession = clearFederalRefsSession;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    bindAnalizModalHandlers();
    updateVndNameDisplay();
    updateStartAnalysisButton();
    document.getElementById('file-input')?.addEventListener('change', (event) => {
        if (event.target.files && event.target.files[0]) {
            uploadDocument();
        }
    });
    await checkBasesStatus();
});

function updateVndNameDisplay(name) {
    const textEl = document.getElementById('vnd-name-text');
    if (!textEl) return;
    const resolved = (name || uploadedDocumentName || '').trim();
    if (resolved) {
        textEl.textContent = resolved;
        textEl.classList.remove('is-empty');
    } else {
        textEl.textContent = 'Документ ещё не загружен';
        textEl.classList.add('is-empty');
    }
}

function updateStartAnalysisButton() {
    const btn = document.getElementById('btn-start-analysis');
    if (btn) btn.disabled = !uploadedFilename;
}

function bindAnalizModalHandlers() {
    const modal = document.getElementById('analiz-files-modal');
    if (!modal || modal.dataset.bound) return;
    modal.dataset.bound = '1';

    modal.querySelectorAll('[data-close-analiz-modal]').forEach((el) => {
        el.addEventListener('click', closeAnalizFilesModal);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal && !modal.hidden) {
            closeAnalizFilesModal();
        }
    });
}

function openAnalizFilesModal() {
    const modal = document.getElementById('analiz-files-modal');
    if (!modal) return;
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
}

function closeAnalizFilesModal() {
    const modal = document.getElementById('analiz-files-modal');
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
}

window.openAnalizFilesModal = openAnalizFilesModal;
window.closeAnalizFilesModal = closeAnalizFilesModal;

// Загрузка незавершенных диалогов
async function loadUnfinishedDialogs() {
    try {
        const response = await fetch(`${API_BASE}/api/dialogs/unfinished`);
        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось загрузить список диалогов'));
        }
        const data = await response.json();
        
        if (data.dialogs && data.dialogs.length > 0) {
            const dialogsDiv = document.getElementById('unfinished-dialogs');
            const dialogsList = document.getElementById('dialogs-list');
            
            dialogsDiv.style.display = 'block';
            dialogsList.innerHTML = '';
            
            data.dialogs.forEach(dialog => {
                const dialogItem = document.createElement('div');
                dialogItem.className = 'dialog-item';
                
                const dialogInfo = document.createElement('div');
                dialogInfo.className = 'dialog-item-info';
                
                const dialogName = document.createElement('div');
                dialogName.className = 'dialog-item-name';
                dialogName.textContent = dialog.vnd_name || 'Без названия';
                
                const dialogDate = document.createElement('div');
                dialogDate.className = 'dialog-item-date';
                dialogDate.textContent = `Создан: ${new Date(dialog.created_at).toLocaleString('ru-RU')}`;
                
                dialogInfo.appendChild(dialogName);
                dialogInfo.appendChild(dialogDate);

                const actions = document.createElement('div');
                actions.className = 'dialog-item-actions';

                const continueBtn = document.createElement('button');
                continueBtn.className = 'btn-primary';
                continueBtn.textContent = 'Продолжить';
                continueBtn.addEventListener('click', (event) => {
                    event.stopPropagation();
                    continueDialog(dialog.id);
                });

                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn-danger dialog-delete-btn';
                deleteBtn.textContent = 'Удалить';
                deleteBtn.addEventListener('click', (event) => {
                    event.stopPropagation();
                    deleteUnfinishedDialog(dialog.id, dialog.vnd_name);
                });

                actions.appendChild(continueBtn);
                actions.appendChild(deleteBtn);

                dialogItem.appendChild(dialogInfo);
                dialogItem.appendChild(actions);

                dialogsList.appendChild(dialogItem);
            });
        } else {
            const dialogsDiv = document.getElementById('unfinished-dialogs');
            if (dialogsDiv) {
                dialogsDiv.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Ошибка загрузки диалогов:', error);
        // Не показываем ошибку пользователю, просто не отображаем незавершенные диалоги
    }
}

// Удалить незавершенный диалог из списка
async function deleteUnfinishedDialog(dialogId, dialogName) {
    const title = dialogName || 'Без названия';
    if (!confirm(`Удалить диалог «${title}»? Это действие нельзя отменить.`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/dialogs/${dialogId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось выполнить операцию'));
        }

        resetAnalysisState();

        await loadUnfinishedDialogs();
    } catch (error) {
        console.error('Ошибка удаления диалога:', error);
        alert('Ошибка при удалении диалога: ' + formatCaughtError(error, 'Не удалось удалить диалог'));
    }
}

// Продолжить диалог (legacy, не используется в новом анализе)
window.continueDialog = async function continueDialog(dialogId) {
    alert('Продолжение старых диалогов недоступно. Начните новый анализ.');
    await loadUnfinishedDialogs();
};

// Функция для обновления прогресса
function updateProgress(progressBar, progressText, percent, message) {
    if (progressBar) progressBar.style.width = percent + '%';
    if (progressText) progressText.textContent = message;
    const progressPercent = document.getElementById('progress-percent');
    if (progressPercent) progressPercent.textContent = Math.round(percent) + '%';
}

// Загрузка документа
function buildCompactUploadResultHtml(data, file, result) {
    const filename = data?.filename || result?.filename || file?.name || '—';
    const status = result?.status || 'success';
    const chunks = result?.total_chunks;
    const filesProcessed = result?.files_processed;

    if (status === 'error') {
        return `
            <div class="upload-error upload-success-compact">
                <p class="upload-success-title" style="color:#dc3545;">✗ Ошибка обработки</p>
                <p><strong>Файл:</strong> ${filename}</p>
                <p>${humanizeErrorMessage(result?.message || 'Не удалось обработать файл')}</p>
            </div>
        `;
    }

    if (status === 'warning') {
        return `
            <div class="upload-success upload-success-compact">
                <p class="upload-success-title" style="color:#856404;">⚠ Загружено с предупреждением</p>
                <p><strong>Файл:</strong> ${filename}</p>
                <p>${result?.message || 'Проверьте результат индексации'}</p>
                ${chunks !== undefined ? `<p><strong>Чанков:</strong> ${chunks}</p>` : ''}
            </div>
        `;
    }

    return `
        <div class="upload-success upload-success-compact">
            <p class="upload-success-title" style="color:#28a745;">✓ Файл загружен и проиндексирован</p>
            <p><strong>Файл:</strong> ${filename}</p>
            ${filesProcessed !== undefined ? `<p><strong>Обработано:</strong> ${filesProcessed}</p>` : ''}
            ${chunks !== undefined ? `<p><strong>Чанков в базе:</strong> ${chunks}</p>` : ''}
        </div>
    `;
}

async function pickAnalizFile() {
    try {
        const config = await fetchAppConfig();
        if (config?.file_browse_available) {
            await browseVndDocument();
            return;
        }
    } catch (error) {
        console.warn('Не удалось определить режим выбора файла:', error);
    }
    document.getElementById('file-input')?.click();
}

async function browseVndDocument() {
    clearFederalRefsSession();
    hideFederalRefsPanel();
    const resultContent = document.getElementById('upload-result-content');
    const pickBtn = document.getElementById('btn-pick-analiz-file');

    if (pickBtn) pickBtn.disabled = true;
    resultContent.innerHTML = '<p class="analiz-upload-placeholder">Откройте окно выбора файла (начальная папка IN)...</p>';

    try {
        const response = await fetch(`${API_BASE}/api/files/browse-vnd`, { method: 'POST' });
        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось выбрать файл'));
        }
        const data = await response.json();
        if (data.cancelled) {
            resultContent.innerHTML = '<div class="analiz-upload-placeholder">Выбор файла отменён</div>';
            return;
        }
        await applyVndUploadResult(data, { name: data.filename || 'документ' });
    } catch (error) {
        resultContent.innerHTML = `
            <div class="upload-error">
                <p style="color: #dc3545; font-weight: bold;">✗ Ошибка выбора файла</p>
                <p style="color: #dc3545;">${formatCaughtError(error, 'Не удалось выбрать файл')}</p>
            </div>
        `;
    } finally {
        if (pickBtn) pickBtn.disabled = false;
    }
}

async function applyVndUploadResult(data, fileMeta) {
    const resultContent = document.getElementById('upload-result-content');
    const result = data.result || { status: 'success' };
    resultContent.innerHTML = buildCompactUploadResultHtml(data, fileMeta, result);

    const sourceName = fileMeta?.name || data.filename || '';
    const fileNameWithoutExt = sourceName.replace(/\.[^/.]+$/, '');
    uploadedDocumentName = fileNameWithoutExt;
    uploadedFilename = data.filename || sourceName;
    updateVndNameDisplay(fileNameWithoutExt);
    updateStartAnalysisButton();

    if (fileMeta instanceof File && fileMeta.type === 'text/plain') {
        uploadedDocumentText = await fileMeta.text();
    }

    await checkBasesStatus();
}

window.pickAnalizFile = pickAnalizFile;

async function uploadDocument() {
    clearFederalRefsSession();
    hideFederalRefsPanel();
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];
    const resultDiv = document.getElementById('upload-result');
    const resultContent = document.getElementById('upload-result-content');
    
    if (!file) {
        alert('Пожалуйста, выберите файл');
        return;
    }
    
    // Показываем прогресс-бар
    resultContent.innerHTML = `
        <div class="progress-container analiz-upload-progress">
            <div class="progress-info">
                <p class="progress-message" id="progress-message">Подготовка к загрузке...</p>
                <p class="progress-file-name">${file.name}</p>
            </div>
            <div class="progress-bar-wrapper">
                <div class="progress-bar" id="progress-bar">
                    <div class="progress-bar-fill" id="progress-bar-fill"></div>
                </div>
                <span class="progress-percent" id="progress-percent">0%</span>
            </div>
        </div>
    `;
    
    const progressBarFill = document.getElementById('progress-bar-fill');
    const progressPercent = document.getElementById('progress-percent');
    const progressMessage = document.getElementById('progress-message');
    
    // Анимация прогресса
    let currentProgress = 0;
    const progressInterval = setInterval(() => {
        if (currentProgress < 90) {
            currentProgress += 2;
            progressBarFill.style.width = currentProgress + '%';
            progressPercent.textContent = Math.round(currentProgress) + '%';
        }
    }, 200);
    
        // Этап 1: Загрузка файла
        updateProgress(progressBarFill, progressMessage, 10, 'Загрузка файла на сервер...');
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
        // Этап 2: Отправка на сервер
        updateProgress(progressBarFill, progressMessage, 30, 'Отправка файла...');
        
        const response = await fetch(`${API_BASE}/api/upload/vnd`, {
            method: 'POST',
            body: formData
        });
        
        // Этап 3: Обработка
        updateProgress(progressBarFill, progressMessage, 60, 'Обработка файла...');
        
        clearInterval(progressInterval);
        currentProgress = 60;
        progressBarFill.style.width = '60%';
        progressPercent.textContent = '60%';
        
        // Этап 4: Индексация
        updateProgress(progressBarFill, progressMessage, 80, 'Индексация в векторной базе...');
        
        if (!response.ok) {
            clearInterval(progressInterval);
            const errorMessage = await readApiError(response, 'Не удалось загрузить файл');
            resultContent.innerHTML = `
                <div class="upload-error">
                    <p style="color: #dc3545; font-weight: bold; font-size: 1.1rem;">✗ Ошибка загрузки</p>
                    <p style="color: #dc3545;">${errorMessage}</p>
                </div>
            `;
            return;
        }

        const data = await response.json();
        
        console.log('Ответ сервера:', data); // Логируем ответ для отладки
        
        if (response.ok) {
            updateProgress(progressBarFill, progressMessage, 100, 'Завершено!');
            await new Promise(resolve => setTimeout(resolve, 300));
            await applyVndUploadResult(data, file);
        }
    } catch (error) {
        console.error('Ошибка загрузки:', error);
        clearInterval(progressInterval);
        resultContent.innerHTML = `
            <div class="upload-error">
                <p style="color: #dc3545; font-weight: bold; font-size: 1.1rem;">✗ Ошибка загрузки файла</p>
                <p style="color: #dc3545;">${formatCaughtError(error, 'Не удалось загрузить файл')}</p>
                <p style="color: #666; font-size: 0.9rem;">${WND_SERVER_HINT}</p>
            </div>
        `;
    }
}

// Начать новый диалог
async function startNewDialog() {
    clearFederalRefsSession();
    hideFederalRefsPanel();
    const inputValue = uploadedDocumentName || '';
    const vndName = inputValue || 'ВНД анализ';

    const startBtn = document.getElementById('btn-start-analysis');
    const originalBtnText = startBtn ? startBtn.textContent : '';
    if (startBtn) {
        startBtn.textContent = '⏳ Подготовка...';
        startBtn.disabled = true;
    }

    try {
        const resolvedFilename = await resolveUploadedFilename();
        if (!resolvedFilename) {
            alert('Сначала загрузите документ ВНД для анализа');
            return;
        }

        uploadedFilename = resolvedFilename;
        currentVndName = vndName;

        const refsStepShown = await checkFederalReferences(uploadedFilename);
        if (refsStepShown) {
            return;
        }

        await proceedWithStage1(vndName);
    } catch (error) {
        console.error('Ошибка запуска анализа:', error);
        alert('Ошибка запуска анализа: ' + formatCaughtError(error, 'Не удалось начать анализ') + '\n\n' + WND_SERVER_HINT);
    } finally {
        if (startBtn) {
            startBtn.textContent = originalBtnText || 'Начать анализ';
            updateStartAnalysisButton();
        }
    }
}

async function resolveUploadedFilename() {
    if (uploadedFilename) {
        return uploadedFilename;
    }

    const fileInput = document.getElementById('file-input');
    if (fileInput && fileInput.files && fileInput.files[0]) {
        await uploadDocument();
        return uploadedFilename;
    }

    try {
        const response = await fetch(`${API_BASE}/api/vnd/latest-file`);
        if (response.ok) {
            const data = await response.json();
            if (data.filename) {
                uploadedFilename = data.filename;
                if (!uploadedDocumentName) {
                    uploadedDocumentName = data.filename.replace(/\.[^/.]+$/, '');
                }
                updateVndNameDisplay(uploadedDocumentName);
                updateStartAnalysisButton();
                return uploadedFilename;
            }
        }
    } catch (error) {
        console.warn('Не удалось получить последний загруженный файл:', error);
    }

    return null;
}

// Проверка ссылок на федеральные документы в ВНД
async function checkFederalReferences(filename) {
    try {
        const response = await fetch(`${API_BASE}/api/vnd/detect-references`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename || '' })
        });

        if (!response.ok) {
            console.warn('Не удалось проверить ссылки:', await readApiError(response, 'Не удалось проверить федеральные ссылки'));
            return false;
        }

        const data = await response.json();
        allDetectedFederalRefs = data.unique_references || data.references || [];
        detectedFederalRefs = data.missing_references || [];
        saveFederalRefsSession(data);

        if (allDetectedFederalRefs.length === 0) {
            return false;
        }

        showFederalRefsPanel(allDetectedFederalRefs, detectedFederalRefs);
        return true;
    } catch (error) {
        console.error('Ошибка проверки федеральных ссылок:', error);
        return false;
    }
}

function setFederalRefsButtons(mode) {
    const buttons = {
        download: document.getElementById('btn-download-federal'),
        skip: document.getElementById('btn-skip-refs'),
        continueAllFound: document.getElementById('btn-continue-all-found'),
        continueSuccess: document.getElementById('btn-continue-analysis'),
        continueFailure: document.getElementById('btn-continue-after-failure'),
        cancel: document.getElementById('btn-cancel-refs'),
    };

    const show = (el) => { if (el) el.style.display = 'inline-block'; };
    const hide = (el) => { if (el) el.style.display = 'none'; };

    Object.values(buttons).forEach(hide);

    if (mode === 'initial') {
        show(buttons.download);
        show(buttons.skip);
    } else if (mode === 'all_found') {
        show(buttons.continueAllFound);
    } else if (mode === 'success') {
        show(buttons.continueSuccess);
    } else if (mode === 'failure') {
        show(buttons.continueFailure);
        show(buttons.cancel);
    }

    const actions = document.getElementById('federal-refs-actions');
    if (actions) {
        actions.style.display = 'flex';
    }
}

// Показать панель с найденными федеральными документами
function showFederalRefsPanel(allReferences, missingReferences) {
    const panel = document.getElementById('federal-refs-panel');
    const list = document.getElementById('federal-refs-list');
    const statusDiv = document.getElementById('federal-refs-status');
    const subtitle = document.getElementById('federal-refs-subtitle');

    if (!panel || !list) return;

    list.innerHTML = '';
    let missingCount = 0;
    allReferences.forEach((ref, index) => {
        const li = document.createElement('li');
        const isMissing = ref.in_local_base === false;
        if (isMissing) {
            missingCount += 1;
        }
        const statusText = isMissing ? 'отсутствует в базе' : 'есть в базе';
        const statusClass = isMissing ? 'missing' : 'found';
        const variantsNote = ref.variants_count > 1
            ? `<span class="federal-ref-variants"> (${ref.variants_count} упомин.)</span>`
            : '';

        li.innerHTML = `
            <span class="federal-ref-title">${index + 1}. ${ref.title}${ref.number ? ' (' + ref.number + ')' : ''}${variantsNote}</span>
            <span class="federal-ref-status ${statusClass}">${statusText}</span>
        `;
        list.appendChild(li);
    });

    if (subtitle) {
        const totalMentions = allReferences.reduce(
            (sum, ref) => sum + (ref.variants_count || 1),
            0
        );
        const uniqueCount = allReferences.length;
        if (missingCount > 0) {
            subtitle.textContent =
                `Найдено ${uniqueCount} уникальных документов (${totalMentions} упоминаний в тексте). Отсутствуют в локальной базе:`;
        } else {
            subtitle.textContent =
                `Найдено ${uniqueCount} уникальных документов (${totalMentions} упоминаний). Все они уже есть в локальной базе:`;
        }
    }

    if (statusDiv) {
        statusDiv.style.display = 'none';
        statusDiv.textContent = '';
        statusDiv.className = 'federal-refs-status';
    }

    if (missingCount > 0) {
        detectedFederalRefs = (missingReferences && missingReferences.length > 0)
            ? [...missingReferences]
            : allReferences.filter(ref => ref.in_local_base === false);
        setFederalRefsButtons('initial');
    } else {
        detectedFederalRefs = [];
        setFederalRefsButtons('all_found');
    }

    const unfinished = document.getElementById('unfinished-dialogs');
    const landing = document.getElementById('analiz-landing');
    const h2 = document.querySelector('.analiz-container > h2');
    const stage1Panel = document.getElementById('stage1-panel');
    const stage2Panel = document.getElementById('stage2-panel');

    if (unfinished) unfinished.style.display = 'none';
    if (landing) landing.style.display = 'none';
    if (h2) h2.style.display = 'none';
    if (stage1Panel) stage1Panel.style.display = 'none';
    if (stage2Panel) stage2Panel.style.display = 'none';

    panel.style.display = 'block';
    document.body.classList.remove('dialog-active');
    document.body.classList.add('federal-refs-active');
}

// Скрыть панель федеральных ссылок
function hideFederalRefsPanel() {
    const panel = document.getElementById('federal-refs-panel');
    if (panel) panel.style.display = 'none';
    document.body.classList.remove('federal-refs-active');
}

// Скачать федеральные документы с pravo.gov.ru
async function downloadFederalDocs() {
    if (!detectedFederalRefs.length) {
        alert('Нет документов для загрузки');
        return;
    }

    const btn = document.getElementById('btn-download-federal');
    const skipBtn = document.getElementById('btn-skip-refs');
    const statusDiv = document.getElementById('federal-refs-status');
    const originalText = btn.textContent;

    btn.textContent = '⏳ Скачивание...';
    btn.disabled = true;
    if (skipBtn) skipBtn.disabled = true;

    statusDiv.style.display = 'block';
    statusDiv.className = 'federal-refs-status info';
    statusDiv.textContent = 'Идёт скачивание документов с pravo.gov.ru...';

    try {
        const response = await fetch(`${API_BASE}/api/vnd/download-federal`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ references: detectedFederalRefs })
        });

        const data = await response.json();

        if (data.status === 'success') {
            statusDiv.className = 'federal-refs-status success';
            let successText = data.message || 'Документы успешно скачаны и добавлены в базу федеральных документов.';
            if (data.fz_chunks_after !== undefined) {
                successText += `\nБаза ФЗ: ${data.fz_chunks_after} чанков`;
                if (data.fz_chunks_added > 0) {
                    successText += ` (+${data.fz_chunks_added})`;
                }
            }
            if (data.downloaded && data.downloaded.length > 0) {
                const indexed = data.downloaded.filter(item => item.chunks > 0);
                if (indexed.length > 0) {
                    successText += '\n' + indexed.map(item =>
                        `• ${item.title}: ${item.chunks} чанков`
                    ).join('\n');
                }
            }
            statusDiv.textContent = successText;
            setFederalRefsButtons('success');
            await checkBasesStatus();
        } else if (data.status === 'partial') {
            statusDiv.className = 'federal-refs-status partial';
            let partialText = data.message || 'Часть документов скачана и добавлена в базу.';
            if (data.fz_chunks_after !== undefined) {
                partialText += `\nБаза ФЗ: ${data.fz_chunks_after} чанков`;
                if (data.fz_chunks_added > 0) {
                    partialText += ` (+${data.fz_chunks_added})`;
                }
            }
            if (data.downloaded && data.downloaded.length > 0) {
                partialText += '\n' + data.downloaded.map(item => {
                    const chunkInfo = item.chunks > 0 ? `, ${item.chunks} чанков` : '';
                    return `• ${item.title}: ${item.message || item.status}${chunkInfo}`;
                }).join('\n');
            }
            if (data.failed && data.failed.length > 0) {
                partialText += '\n' + data.failed.map(item => `• ${item.title}: ${item.message}`).join('\n');
            }
            statusDiv.textContent = partialText;
            setFederalRefsButtons('success');
            await checkBasesStatus();
        } else {
            statusDiv.className = 'federal-refs-status error';
            let errorText = 'Актуальные документы скачать не удалось. Добавьте их в ручную';
            if (data.failed && data.failed.length > 0) {
                errorText += ':\n' + data.failed.map(item => `• ${item.title}: ${item.message}`).join('\n');
            }
            if (data.log_file) {
                errorText += `\n\nПодробности в логе:\n${data.log_file}`;
            }
            statusDiv.textContent = errorText;
            setFederalRefsButtons('failure');
        }
    } catch (error) {
        console.error('Ошибка загрузки федеральных документов:', error);
        statusDiv.style.display = 'block';
        statusDiv.className = 'federal-refs-status error';
        statusDiv.textContent = formatCaughtError(error, 'Не удалось скачать федеральные документы. Добавьте их вручную.');
        setFederalRefsButtons('failure');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
        if (skipBtn) skipBtn.disabled = false;
    }
}

// Продолжить анализ после проверки ссылок
async function continueAnalysisAfterRefs() {
    hideFederalRefsPanel();
    detectedFederalRefs = [];
    allDetectedFederalRefs = [];
    const vndName = uploadedDocumentName || 'ВНД анализ';
    await proceedWithStage1(vndName);
}

// Игнорировать отсутствующие документы и продолжить анализ
async function skipFederalRefs() {
    await continueAnalysisAfterRefs();
}

// Отмена — вернуться на главный экран
async function cancelAnalysis() {
    resetAnalysisState();
    detectedFederalRefs = [];
    allDetectedFederalRefs = [];
    clearFederalRefsSession();
    hideFederalRefsPanel();
    window.location.href = '/';
}

function resetAnalysisState() {
    stopStage1Progress();
    stopStage2Progress();
    stage1Data = null;
    lastStage1Answers = null;
    lastAnalysisReport = '';
    analysisInProgress = false;
    uploadedDocumentText = null;
    uploadedDocumentName = null;
    uploadedFilename = null;
    hideAnalysisPanels();
    document.body.classList.remove('analysis-active');
    const landing = document.getElementById('analiz-landing');
    if (landing) landing.style.display = '';
    updateVndNameDisplay();
    updateStartAnalysisButton();
}

function hideAnalysisPanels() {
    const stage1 = document.getElementById('stage1-panel');
    const stage2 = document.getElementById('stage2-panel');
    if (stage1) stage1.style.display = 'none';
    if (stage2) stage2.style.display = 'none';
}

function showAnalysisMode() {
    document.body.classList.add('analysis-active');
    const unfinished = document.getElementById('unfinished-dialogs');
    const landing = document.getElementById('analiz-landing');
    const h2 = document.querySelector('.analiz-container > h2');
    if (unfinished) unfinished.style.display = 'none';
    if (landing) landing.style.display = 'none';
    if (h2) h2.style.display = 'none';
}

function fillSelectOptions(selectEl, options, selectedValue) {
    if (!selectEl) return;
    selectEl.innerHTML = '';
    (options || []).forEach((option) => {
        const opt = document.createElement('option');
        opt.value = option;
        opt.textContent = option;
        if (selectedValue && option === selectedValue) {
            opt.selected = true;
        }
        selectEl.appendChild(opt);
    });
}

function fillLegalAreasSelect(selectEl, options, selectedAreas) {
    if (!selectEl) return;
    selectEl.innerHTML = '';
    const selected = new Set(selectedAreas || []);
    (options || []).forEach((option) => {
        const opt = document.createElement('option');
        opt.value = option;
        opt.textContent = option;
        opt.selected = selected.has(option);
        selectEl.appendChild(opt);
    });
}

function stopStage1Progress(finalPercent = null) {
    if (stage1ProgressInterval) {
        clearInterval(stage1ProgressInterval);
        stage1ProgressInterval = null;
    }
    const fill = document.getElementById('stage1-progress-fill');
    const percent = document.getElementById('stage1-progress-percent');
    if (finalPercent !== null && fill && percent) {
        fill.style.width = `${finalPercent}%`;
        percent.textContent = `${Math.round(finalPercent)}%`;
    }
}

function showStage1ProgressMessage(message = 'Анализирую документ...') {
    const note = document.getElementById('stage1-detected-note');
    if (!note) return;

    stopStage1Progress();
    note.className = 'stage1-note stage1-note-progress';
    note.innerHTML = `
        <div class="stage1-progress">
            <p class="progress-message" id="stage1-progress-message">${message}</p>
            <div class="progress-bar-wrapper">
                <div class="progress-bar">
                    <div class="progress-bar-fill" id="stage1-progress-fill" style="width: 0%"></div>
                </div>
                <span class="progress-percent" id="stage1-progress-percent">0%</span>
            </div>
        </div>
    `;

    let currentProgress = 0;
    stage1ProgressInterval = setInterval(() => {
        if (currentProgress >= 92) return;
        currentProgress += currentProgress < 40 ? 3 : currentProgress < 70 ? 2 : 1;
        const fill = document.getElementById('stage1-progress-fill');
        const percentEl = document.getElementById('stage1-progress-percent');
        if (fill) fill.style.width = `${currentProgress}%`;
        if (percentEl) percentEl.textContent = `${Math.round(currentProgress)}%`;
    }, 180);
}

function stopStage2Progress(finalPercent = null) {
    if (stage2ProgressInterval) {
        clearInterval(stage2ProgressInterval);
        stage2ProgressInterval = null;
    }
    const fill = document.getElementById('stage2-progress-fill');
    const percent = document.getElementById('stage2-progress-percent');
    if (finalPercent !== null && fill && percent) {
        fill.style.width = `${finalPercent}%`;
        percent.textContent = `${Math.round(finalPercent)}%`;
    }
}

function showStage2ProgressMessage(message = 'Выполняется правовой анализ документа...') {
    const resultDiv = document.getElementById('analysis-result');
    if (!resultDiv) return;

    stopStage2Progress();
    resultDiv.className = 'analysis-result analysis-progress';
    resultDiv.innerHTML = `
        <div class="stage1-progress">
            <p class="progress-message" id="stage2-progress-message">${message}</p>
            <div class="progress-bar-wrapper">
                <div class="progress-bar">
                    <div class="progress-bar-fill" id="stage2-progress-fill" style="width: 0%"></div>
                </div>
                <span class="progress-percent" id="stage2-progress-percent">0%</span>
            </div>
        </div>
    `;

    let currentProgress = 0;
    stage2ProgressInterval = setInterval(() => {
        if (currentProgress >= 92) return;
        currentProgress += currentProgress < 40 ? 3 : currentProgress < 70 ? 2 : 1;
        const fill = document.getElementById('stage2-progress-fill');
        const percentEl = document.getElementById('stage2-progress-percent');
        if (fill) fill.style.width = `${currentProgress}%`;
        if (percentEl) percentEl.textContent = `${Math.round(currentProgress)}%`;
    }, 180);
}

function populateStage1Form(data) {
    stage1Data = data;
    const options = data.options || {};
    fillSelectOptions(
        document.getElementById('stage1-activity'),
        options.activity_spheres,
        data.activity_sphere || ''
    );
    fillSelectOptions(
        document.getElementById('stage1-ownership'),
        options.ownership_forms,
        data.ownership_form || ''
    );
    fillLegalAreasSelect(
        document.getElementById('stage1-legal'),
        options.legal_areas,
        data.legal_areas || []
    );

    document.querySelectorAll('#stage1-lower-level-docs input[type="checkbox"]').forEach((cb) => {
        cb.checked = false;
    });

    const note = document.getElementById('stage1-detected-note');
    if (!note) return;

    const needs = data.needs_user_input || [];
    if (needs.length === 0 && data.detected_from_document) {
        note.className = 'stage1-note';
        note.textContent = 'Параметры определены из названия и содержания документа. Проверьте и при необходимости измените значения.';
    } else if (needs.length > 0) {
        note.className = 'stage1-note warning';
        const labels = {
            activity_sphere: 'сферу деятельности',
            ownership_form: 'форму собственности',
            legal_areas: 'области законодательства',
        };
        const missing = needs.map((key) => labels[key] || key).join(', ');
        note.textContent = `Не удалось однозначно определить: ${missing}. Выберите значения в списках ниже.`;
    } else {
        note.className = 'stage1-note';
        note.textContent = 'Уточните параметры перед правовым анализом.';
    }
}

function collectStage1LowerLevelDocs() {
    return Array.from(
        document.querySelectorAll('#stage1-lower-level-docs input[type="checkbox"]:checked')
    ).map((el) => el.value);
}

const STAGE1_LOWER_LEVEL_LABELS = {
    provisions: 'Положения',
    regulations: 'Регламенты',
    appointment_orders: 'Приказы о назначении ответственных лиц',
    instructions: 'Инструкции',
};

function formatStage1LowerLevelDocs(ids) {
    return (ids || [])
        .map((id) => STAGE1_LOWER_LEVEL_LABELS[id] || id)
        .join(', ');
}

function collectStage1Answers() {
    const activity = document.getElementById('stage1-activity')?.value || '';
    const ownership = document.getElementById('stage1-ownership')?.value || '';
    const legalSelect = document.getElementById('stage1-legal');
    const legalAreas = legalSelect
        ? Array.from(legalSelect.selectedOptions).map((opt) => opt.value)
        : [];

    if (!activity) {
        alert('Выберите сферу деятельности предприятия');
        return null;
    }
    if (!ownership) {
        alert('Выберите форму собственности');
        return null;
    }
    if (legalAreas.length === 0) {
        alert('Выберите хотя бы одну область законодательства');
        return null;
    }

    return {
        activity_sphere: activity,
        ownership_form: ownership,
        legal_areas: legalAreas,
        lower_level_documents: collectStage1LowerLevelDocs(),
    };
}

function renderStage1Summary(stage1) {
    const summary = document.getElementById('stage1-summary');
    if (!summary || !stage1) return;
    const areas = (stage1.legal_areas || []).join(', ');
    const lowerLevel = formatStage1LowerLevelDocs(stage1.lower_level_documents);
    summary.innerHTML = `
        <strong>Параметры этапа 1:</strong><br>
        Сфера деятельности: ${stage1.activity_sphere || '—'}<br>
        Форма собственности: ${stage1.ownership_form || '—'}<br>
        Области законодательства: ${areas || '—'}<br>
        Документы нижнего уровня: ${lowerLevel || 'не указаны'}
    `;
}

async function proceedWithStage1(vndName) {
    currentVndName = vndName;
    showAnalysisMode();
    hideAnalysisPanels();

    const stage1Panel = document.getElementById('stage1-panel');
    const note = document.getElementById('stage1-detected-note');
    const submitBtn = document.getElementById('btn-stage1-submit');

    if (stage1Panel) stage1Panel.style.display = 'flex';
    showStage1ProgressMessage('Анализирую документ...');
    if (submitBtn) submitBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/api/vnd/stage1`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                vnd_filename: uploadedFilename || '',
                vnd_name: vndName,
            }),
        });

        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось выполнить предварительный анализ'));
        }

        const data = await response.json();
        stopStage1Progress(100);
        populateStage1Form(data);
    } catch (error) {
        console.error('Ошибка этапа 1:', error);
        stopStage1Progress();
        if (note) {
            note.className = 'stage1-note warning';
            note.textContent = '❌ ' + formatCaughtError(error, 'Не удалось выполнить предварительный анализ');
        }
    } finally {
        stopStage1Progress();
        if (submitBtn) submitBtn.disabled = false;
    }
}

async function submitStage1() {
    if (analysisInProgress) return;

    const answers = collectStage1Answers();
    if (!answers) return;

    lastStage1Answers = answers;
    analysisInProgress = true;

    const stage1Panel = document.getElementById('stage1-panel');
    const stage2Panel = document.getElementById('stage2-panel');
    const resultDiv = document.getElementById('analysis-result');
    const stage2Title = document.getElementById('stage2-title');
    const submitBtn = document.getElementById('btn-stage1-submit');

    if (stage1Panel) stage1Panel.style.display = 'none';
    if (stage2Panel) stage2Panel.style.display = 'flex';
    if (stage2Title) stage2Title.textContent = `Правовой анализ: ${currentVndName}`;
    renderStage1Summary(answers);
    showStage2ProgressMessage('Выполняется правовой анализ документа...');

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300000);

    try {
        const response = await fetch(`${API_BASE}/api/vnd/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                vnd_filename: uploadedFilename || '',
                vnd_name: currentVndName,
                stage1: answers,
            }),
            signal: controller.signal,
        });

        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось выполнить анализ'));
        }

        const data = await response.json();
        lastAnalysisReport = data.response || '';
        stopStage2Progress(100);
        if (resultDiv) {
            resultDiv.className = 'analysis-result';
            resultDiv.textContent = lastAnalysisReport;
            resultDiv.dataset.reportText = lastAnalysisReport;
        }
        if (data.stage1) {
            lastStage1Answers = data.stage1;
            renderStage1Summary(data.stage1);
        }
    } catch (error) {
        console.error('Ошибка этапа 2:', error);
        const message = error && error.name === 'AbortError'
            ? 'Превышено время ожидания ответа сервера. Попробуйте ещё раз.'
            : formatCaughtError(error, 'Не удалось выполнить анализ');
        if (resultDiv) {
            stopStage2Progress();
            resultDiv.className = 'analysis-result';
            resultDiv.textContent = '❌ ' + message;
        }
        if (stage1Panel) stage1Panel.style.display = 'flex';
        if (stage2Panel) stage2Panel.style.display = 'none';
    } finally {
        clearTimeout(timeoutId);
        stopStage2Progress();
        analysisInProgress = false;
        if (submitBtn) submitBtn.disabled = false;
    }
}

window.submitStage1 = submitStage1;

async function finishAnalysis() {
    if (!confirm('Завершить анализ и вернуться к загрузке документа?')) {
        return;
    }

    resetAnalysisState();
    clearFederalRefsSession();

    const upload = document.querySelector('.upload-section');
    const newDialog = document.querySelector('.new-dialog-section');
    const h2 = document.querySelector('.analiz-container > h2');
    if (upload) upload.style.display = 'block';
    if (newDialog) newDialog.style.display = 'block';
    if (h2) h2.style.display = 'block';
}

window.finishAnalysis = finishAnalysis;

// Проверка статуса баз
async function checkBasesStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/bases/status`);
        const data = await response.json();
        
        // Можно показать предупреждение, если базы не готовы
        if (!data.gost?.ready || !data.fz?.ready) {
            console.warn('Некоторые базы не готовы');
        }
    } catch (error) {
        console.error('Ошибка проверки статуса баз:', error);
    }
}

// Скачать отчёт (PDF) — текст как на экране
function getAnalysisReportText() {
    if (lastAnalysisReport && lastAnalysisReport.trim()) {
        return lastAnalysisReport.trim();
    }

    const resultDiv = document.getElementById('analysis-result');
    if (!resultDiv) return '';

    const stored = (resultDiv.dataset.reportText || '').trim();
    if (stored) return stored;

    const text = (resultDiv.textContent || '').trim();
    if (!text || text.startsWith('❌') || resultDiv.classList.contains('analysis-progress')) {
        return '';
    }
    return text;
}

function getAnalysisReportPayload() {
    const summaryEl = document.getElementById('stage1-summary');
    const titleEl = document.getElementById('stage2-title');
    return {
        report_name: currentVndName || uploadedDocumentName || 'Отчёт',
        content: getAnalysisReportText(),
        title: titleEl?.textContent?.trim() || '',
        summary_html: summaryEl?.innerHTML?.trim() || '',
    };
}

async function downloadReport() {
    const payload = getAnalysisReportPayload();
    if (!payload.content) {
        alert('Нет результата анализа для скачивания. Дождитесь завершения правового анализа.');
        return;
    }

    const reportName = payload.report_name;

    const downloadBtn = document.getElementById('btn-download-report');
    const originalText = downloadBtn ? downloadBtn.textContent : '⬇ Скачать отчёт (PDF)';
    if (downloadBtn) {
        downloadBtn.textContent = '⏳ Подготовка...';
        downloadBtn.disabled = true;
    }

    try {
        const filename = await downloadFromPost(
            `${API_BASE}/api/report/save`,
            payload,
            `Отчёт_${reportName}.pdf`,
            'Не удалось скачать отчёт',
        );
        alert(`✅ Отчёт скачан и сохранён в подпапку OUT рабочей папки\n\n📄 ${filename}`);
    } catch (error) {
        console.error('Ошибка скачивания отчёта:', error);
        alert(`❌ ${formatCaughtError(error, 'Не удалось скачать отчёт')}`);
    } finally {
        if (downloadBtn) {
            downloadBtn.textContent = originalText;
            downloadBtn.disabled = false;
        }
    }
}

