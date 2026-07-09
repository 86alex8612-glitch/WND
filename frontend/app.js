// Главная страница - навигация по меню

// API_BASE можно изменить, если backend на другом порту/хосте
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
    ? 'http://localhost:8011' 
    : '';

function openAnalizPage() {
    window.location.href = '/analiz';
}

function openCreatePage() {
    window.location.href = '/create';
}

function openSearchPage() {
    window.location.href = '/search';
}

const BASE_LABELS = {
    gost: 'ГОСТ',
    fz: 'ФЗ',
    vnd: 'ВНД',
};

const BASE_SOURCE_HINTS = {
    gost: 'FZYur',
    fz: 'FZ',
    vnd: 'IN',
};

const BASE_UPLOAD_TARGETS = {
    gost: 'FZYur',
    fz: 'FZ',
};

let statsEditMode = false;
let pendingStatsUploadTarget = '';

function escapeHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function getStatsModal() {
    return document.getElementById('stats-docs-modal');
}

function closeBaseDocumentsModal() {
    const modal = getStatsModal();
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
}

function renderBaseDocumentsModal(data) {
    const modal = getStatsModal();
    const titleEl = document.getElementById('stats-modal-title');
    const bodyEl = document.getElementById('stats-modal-body');
    if (!modal || !titleEl || !bodyEl) return;

    titleEl.textContent = `Документы: ${data.label || BASE_LABELS[data.base] || data.base}`;
    const documents = data.documents || [];

    if (documents.length === 0) {
        bodyEl.innerHTML = '<p class="stats-modal-empty">В базе пока нет документов.</p>';
    } else {
        const summary = `<p class="stats-modal-summary">Всего: ${data.total_documents || documents.length} док., ${data.total_chunks || 0} чанков</p>`;
        const listItems = documents.map((doc) => {
            const filename = escapeHtml(doc.filename || 'Без названия');
            const chunks = doc.chunks || 0;
            return `<li><span class="stats-doc-name">${filename}</span><span class="stats-doc-chunks">${chunks} чанк.</span></li>`;
        }).join('');
        bodyEl.innerHTML = `${summary}<ul class="stats-doc-list">${listItems}</ul>`;
    }

    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
}

async function openBaseDocuments(baseName, event) {
    if (event) {
        event.stopPropagation();
    }

    const modal = getStatsModal();
    const titleEl = document.getElementById('stats-modal-title');
    const bodyEl = document.getElementById('stats-modal-body');
    if (!modal || !titleEl || !bodyEl) return;

    titleEl.textContent = `Документы: ${BASE_LABELS[baseName] || baseName}`;
    bodyEl.innerHTML = '<p class="stats-modal-loading">Загрузка списка...</p>';
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');

    try {
        const baseQuery = encodeURIComponent(baseName);
        let response = await fetch(`${API_BASE || ''}/api/bases/status?documents=${baseQuery}`);
        if (response.status === 404) {
            response = await fetch(`${API_BASE || ''}/api/bases/${baseQuery}/documents`);
        }
        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось загрузить список документов'));
        }
        const data = await response.json();
        renderBaseDocumentsModal(data);
    } catch (error) {
        bodyEl.innerHTML = `<p class="stats-modal-error">${escapeHtml(formatCaughtError(error, 'Не удалось загрузить список документов'))}</p>`;
    }
}

function bindStatsModalHandlers() {
    const modal = getStatsModal();
    if (!modal || modal.dataset.bound === '1') return;
    modal.dataset.bound = '1';

    modal.querySelectorAll('[data-close-modal]').forEach((el) => {
        el.addEventListener('click', (event) => {
            event.stopPropagation();
            closeBaseDocumentsModal();
        });
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal && !modal.hidden) {
            closeBaseDocumentsModal();
        }
    });
}

async function openStatsPage() {
    // Статистика уже отображается в квадрате, просто обновляем её
    await updateStatsInCard();
}

function renderStatItem(baseKey, baseData) {
    const label = BASE_LABELS[baseKey] || baseKey;
    const disabledAttr = statsEditMode ? '' : ' disabled';
    const recreateBtn = baseKey !== 'vnd'
        ? `<button type="button" class="stat-base-recreate" data-base="${baseKey}"${disabledAttr}>Пересоздать</button>`
        : '';
    const uploadFilesBtn = BASE_UPLOAD_TARGETS[baseKey]
        ? `<button type="button" class="stat-base-upload stat-base-upload-files" data-base="${baseKey}" data-target="${BASE_UPLOAD_TARGETS[baseKey]}" data-mode="files" title="Выбрать файлы на вашем компьютере">Файлы с ПК</button>`
        : '';
    const uploadFolderBtn = BASE_UPLOAD_TARGETS[baseKey]
        ? `<button type="button" class="stat-base-upload stat-base-upload-folder" data-base="${baseKey}" data-target="${BASE_UPLOAD_TARGETS[baseKey]}" data-mode="folder" title="Выбрать папку на компьютере (например FZYur) — загрузка на сервер">Папка с ПК</button>`
        : '';

    return `
        <div class="stat-item">
            <div class="stat-item-content">
                <div class="stat-item-row">
                    <button type="button" class="stat-base-link" data-base="${baseKey}" title="Показать список документов">${label}</button>
                    <div class="stat-item-right">
                        ${uploadFilesBtn}
                        ${uploadFolderBtn}
                        <button type="button" class="stat-base-reset" data-base="${baseKey}"${disabledAttr}>Сбросить</button>
                        ${recreateBtn}
                        <span class="stat-status ${baseData?.ready ? 'ready' : 'not-ready'}">
                            ${baseData?.count || 0} чанков
                        </span>
                    </div>
                </div>
                <div class="stat-docs">Документов: ${baseData?.files_count || 0} · папка ${BASE_SOURCE_HINTS[baseKey] || ''}</div>
            </div>
        </div>
    `;
}

function syncStatsEditControls(statsCard) {
    const editInput = statsCard.querySelector('.stats-edit-input');
    if (editInput) {
        editInput.checked = statsEditMode;
    }
    statsCard.querySelectorAll('.stat-base-reset, .stat-base-recreate, .recreate-btn').forEach((btn) => {
        btn.disabled = !statsEditMode;
    });
}

function setStatsUploadStatus(message, type = 'info') {
    const status = document.getElementById('stats-upload-status');
    if (!status) return;
    status.hidden = !message;
    status.textContent = message || '';
    status.className = `stats-upload-status stats-upload-status-${type}`;
}

function bindStatsUploadHandlers() {
    if (document.body.dataset.statsUploadBound === '1') return;
    document.body.dataset.statsUploadBound = '1';

    document.getElementById('stats-upload-files-input')?.addEventListener('change', (event) => {
        uploadStatsFiles(event.target.files, false).finally(() => {
            event.target.value = '';
        });
    });
    document.getElementById('stats-upload-folder-input')?.addEventListener('change', (event) => {
        uploadStatsFiles(event.target.files, true).finally(() => {
            event.target.value = '';
        });
    });
}

async function uploadStatsFiles(fileList, preserveRelativePath) {
    const files = Array.from(fileList || []);
    if (!files.length || !pendingStatsUploadTarget) return;

    const target = pendingStatsUploadTarget;
    const label = Object.entries(BASE_UPLOAD_TARGETS).find(([, folder]) => folder === target)?.[0];
    const baseLabel = BASE_LABELS[label] || target;

    const buttons = document.querySelectorAll('.stat-base-upload');
    buttons.forEach((button) => { button.disabled = true; });
    setStatsUploadStatus(`Загрузка в ${target}: ${files.length} файл(ов)...`, 'info');

    try {
        const result = await uploadFilesToFolder(target, files, { preserveRelativePath });
        let message = result?.message || `Загружено в ${target}: ${result?.saved_count || files.length} файл(ов)`;
        if (result?.reindex_message) {
            message += `. ${result.reindex_message}`;
        }
        setStatsUploadStatus(message, 'success');
        await updateStatsInCard();
    } catch (error) {
        setStatsUploadStatus(formatCaughtError(error, `Не удалось загрузить файлы в ${baseLabel}`), 'error');
    } finally {
        buttons.forEach((button) => { button.disabled = false; });
        pendingStatsUploadTarget = '';
    }
}

function initStatsCardHandlers() {
    const statsCard = document.getElementById('card-stats');
    if (!statsCard || statsCard.dataset.statsHandlersBound) return;
    statsCard.dataset.statsHandlersBound = '1';

    statsCard.addEventListener('change', (e) => {
        if (!e.target.classList.contains('stats-edit-input')) return;
        e.stopPropagation();
        statsEditMode = e.target.checked;
        syncStatsEditControls(statsCard);
    });

    statsCard.addEventListener('click', (e) => {
        const interactive = e.target.closest(
            '.stats-edit-switch, .stat-base-link, .stat-base-reset, .stat-base-recreate, .recreate-btn, .stat-base-upload'
        );
        if (interactive) {
            e.stopPropagation();
        }

        const uploadBtn = e.target.closest('.stat-base-upload');
        if (uploadBtn) {
            pendingStatsUploadTarget = uploadBtn.dataset.target || '';
            if (!pendingStatsUploadTarget) return;
            const mode = uploadBtn.dataset.mode || 'files';
            if (mode === 'folder') {
                document.getElementById('stats-upload-folder-input')?.click();
            } else {
                document.getElementById('stats-upload-files-input')?.click();
            }
            return;
        }

        const baseLink = e.target.closest('.stat-base-link');
        if (baseLink) {
            openBaseDocuments(baseLink.dataset.base, e);
            return;
        }

        const resetBtn = e.target.closest('.stat-base-reset');
        if (resetBtn) {
            resetBase(resetBtn.dataset.base);
            return;
        }

        const recreateOneBtn = e.target.closest('.stat-base-recreate');
        if (recreateOneBtn) {
            recreateBase(recreateOneBtn.dataset.base);
            return;
        }

        const recreateAllBtn = e.target.closest('.recreate-btn');
        if (recreateAllBtn) {
            recreateBases();
        }
    });
}

async function resetBase(baseName) {
    if (!statsEditMode) {
        alert('⚠️ Включите переключатель «Редактировать», чтобы сбросить базу.');
        return;
    }

    const label = BASE_LABELS[baseName] || baseName;
    if (!confirm(
        `⚠️ Сброс базы «${label}»\n\n` +
        `Будут удалены все чанки и записи из базы «${label}».\n` +
        'Действие необратимо.\n\n' +
        'Продолжить?'
    )) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE || ''}/api/bases/${baseName}/reset`, {
            method: 'POST',
        });

        if (!response.ok) {
            throw new Error(await readApiError(response, `Не удалось сбросить базу ${label}`));
        }

        const result = await response.json();
        await updateStatsInCard();
        alert('✅ ' + (result.message || `База «${label}» сброшена.`));
    } catch (error) {
        console.error('Ошибка сброса базы:', error);
        alert('❌ ' + formatCaughtError(error, `Не удалось сбросить базу ${label}`));
    }
}

async function recreateBase(baseName) {
    if (!statsEditMode) {
        alert('⚠️ Включите переключатель «Редактировать», чтобы пересоздать базу.');
        return;
    }

    const label = BASE_LABELS[baseName] || baseName;
    const folder = BASE_SOURCE_HINTS[baseName] || '';
    if (!confirm(
        `⚠️ Пересоздание базы «${label}»\n\n` +
        `База будет очищена и заново загружена из папки ${folder}.\n` +
        'Существующие чанки и записи будут удалены.\n\n' +
        'Продолжить?'
    )) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE || ''}/api/bases/${baseName}/recreate`, {
            method: 'POST',
        });

        if (!response.ok) {
            throw new Error(await readApiError(response, `Не удалось пересоздать базу ${label}`));
        }

        const result = await response.json();
        await updateStatsInCard();
        alert('✅ ' + (result.message || `База «${label}» пересоздана.`));
    } catch (error) {
        console.error('Ошибка пересоздания базы:', error);
        alert('❌ ' + formatCaughtError(error, `Не удалось пересоздать базу ${label}`));
    }
}

async function updateStatsInCard() {
    const statsCard = document.getElementById('card-stats');
    if (!statsCard) return;
    
    try {
        const response = await fetch(`${API_BASE || ''}/api/bases/status`);
        if (!response.ok) {
            throw new Error(await readApiError(response, 'Не удалось загрузить статистику баз'));
        }
        const data = await response.json();
        
        // Обновляем содержимое квадрата статистики
        const globalRecreateDisabled = statsEditMode ? '' : ' disabled';
        const statsHTML = `
            <label class="stats-edit-switch" title="Включить редактирование баз">
                <span class="stats-edit-label">Редактировать</span>
                <input type="checkbox" class="stats-edit-input"${statsEditMode ? ' checked' : ''}>
                <span class="stats-edit-slider" aria-hidden="true"></span>
            </label>
            <div class="card-icon">📊</div>
            <h2>Статистика</h2>
            <p class="stats-card-subtitle">ГОСТ и ФЗ загружаются с вашего компьютера через браузер</p>
            <div class="stats-in-card">
                ${renderStatItem('gost', data.gost)}
                ${renderStatItem('fz', data.fz)}
                ${renderStatItem('vnd', data.vnd)}
            </div>
            <button type="button" class="recreate-btn"${globalRecreateDisabled}>
                🔄 Пересоздать
            </button>
        `;
        
        statsCard.innerHTML = statsHTML;
        syncStatsEditControls(statsCard);

        statsCard.onclick = (e) => {
            if (
                e.target.closest('.stats-edit-switch') ||
                e.target.closest('.stat-base-link') ||
                e.target.closest('.stat-item-right') ||
                e.target.closest('.recreate-btn') ||
                e.target.closest('.stats-modal') ||
                e.target.closest('.stat-base-upload')
            ) {
                return;
            }
            openStatsPage();
        };
    } catch (error) {
        console.error('Ошибка загрузки статистики:', error);
        const statsCard = document.getElementById('card-stats');
        if (statsCard) {
            statsCard.innerHTML = `
                <div class="card-icon">📊</div>
                <h2>Статистика</h2>
                <p class="stats-card-subtitle">ГОСТ и ФЗ загружаются с вашего компьютера через браузер</p>
                <p style="color: #dc3545;">${formatCaughtError(error, 'Не удалось загрузить статистику')}</p>
                <p style="color: #666; font-size: 0.9rem;">${WND_SERVER_HINT}</p>
            `;
        }
    }
}

async function recreateBases() {
    if (!statsEditMode) {
        alert('⚠️ Включите переключатель «Редактировать», чтобы пересоздать все базы.');
        return;
    }

    if (!confirm(
        '⚠️ Пересоздание всех баз знаний\n\n' +
        'Будут очищены и заново загружены базы из рабочей папки: ГОСТ (FZYur), ФЗ (FZ) и ВНД (IN).\n' +
        'Все существующие чанки и записи будут удалены.\n\n' +
        'Продолжить?'
    )) {
        return;
    }
    
    const statsCard = document.getElementById('card-stats');
    if (statsCard) {
        const oldHTML = statsCard.innerHTML;
        statsCard.innerHTML = `
            <div class="card-icon">📊</div>
            <h2>Статистика</h2>
            <p style="color: #007bff;">⏳ Пересоздание баз...</p>
        `;
        
        try {
            const response = await fetch(`${API_BASE || ''}/api/bases/recreate`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(await readApiError(response, 'Не удалось пересоздать базы знаний'));
            }
            
            const result = await response.json();
            
            // Обновляем статистику после пересоздания
            await updateStatsInCard();
            
            if (result.status === "warning") {
                alert('⚠️ ' + result.message + '\n\n' + (result.note || ''));
            } else {
                alert('✅ Базы знаний успешно пересозданы!\n\n' + 
                      `ФЗ: ${result.results?.fz?.files_processed || 0} файлов\n` +
                      `ГОСТ: ${result.results?.gost?.files_processed || 0} файлов\n` +
                      `ВНД: ${result.results?.vnd?.files_processed || 0} файлов`);
            }
        } catch (error) {
            console.error('Ошибка пересоздания баз:', error);
            alert('❌ ' + formatCaughtError(error, 'Не удалось пересоздать базы знаний'));
            statsCard.innerHTML = oldHTML; // Восстанавливаем старое содержимое
        }
    }
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', async () => {
    bindStatsModalHandlers();
    bindStatsUploadHandlers();
    initStatsCardHandlers();
    // Загружаем статистику в квадрат при загрузке страницы
    await updateStatsInCard();
    
    // Обновляем статистику каждые 5 секунд
    setInterval(updateStatsInCard, 5000);
});

