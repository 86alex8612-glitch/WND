/**
 * Настройки: рабочая папка и подпапки.
 * Загрузка ГОСТ/ФЗ — в карточке «Статистика» (app.js).
 */

const APP_UI_VERSION = '12.07';

const CONFIG_API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8011'
    : '';

let appConfigCache = null;

function getConfigApiBase() {
    return typeof API_BASE !== 'undefined' ? API_BASE : CONFIG_API_BASE;
}

async function fetchAppConfig(force = false) {
    if (appConfigCache && !force) {
        return appConfigCache;
    }
    const response = await fetch(`${getConfigApiBase()}/api/config`);
    if (!response.ok) {
        throw new Error(await readApiError(response, 'Не удалось загрузить настройки'));
    }
    appConfigCache = await response.json();
    return appConfigCache;
}

function escapeConfigHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function renderSettingsForm(config) {
    const inputEl = document.getElementById('settings-work-folder');
    const labelEl = document.getElementById('settings-data-root-label');
    const hintEl = document.getElementById('settings-main-hint');
    const browseBtn = document.getElementById('btn-settings-browse');
    const saveBtn = document.getElementById('btn-settings-save');
    const defaultBtn = document.getElementById('btn-settings-default');
    const foldersEl = document.getElementById('settings-folder-list');
    const versionEl = document.getElementById('settings-ui-version');
    const dataRoot = config?.data_root || config?.work_folder || '';
    const editable = Boolean(config?.paths_editable);

    if (versionEl) {
        versionEl.textContent = APP_UI_VERSION;
    }

    if (labelEl) {
        labelEl.textContent = config?.data_root_label || 'Рабочая папка';
    }
    if (hintEl) {
        hintEl.textContent = config?.settings_hint
            || 'Укажите рабочую папку. При сохранении будут созданы необходимые подпапки.';
    }
    if (inputEl) {
        inputEl.value = dataRoot;
        inputEl.readOnly = !editable;
        inputEl.disabled = !editable;
    }
    if (browseBtn) {
        browseBtn.hidden = !config?.folder_browse_available;
        browseBtn.disabled = !editable;
    }
    if (saveBtn) saveBtn.disabled = !editable;
    if (defaultBtn) defaultBtn.disabled = !editable;

    if (foldersEl) {
        const folders = config?.display_folders || [];
        foldersEl.innerHTML = folders.map((item) => (
            `<div class="config-folder-row">`
            + `<span class="config-folder-name">${escapeConfigHtml(item.name)}</span>`
            + `<div class="config-folder-details">`
            + `<span class="config-folder-desc">${escapeConfigHtml(item.description || '')}</span>`
            + `<span class="config-folder-path">${escapeConfigHtml(item.path)}</span>`
            + `</div>`
            + `</div>`
        )).join('');
    }
}

function setSettingsStatus(message, type = 'info') {
    const status = document.getElementById('settings-save-status');
    if (!status) return;
    status.hidden = !message;
    status.textContent = message || '';
    status.className = `settings-save-status settings-save-status-${type}`;
}

async function persistJsonPost(url, body, errorLabel) {
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        throw new Error(await readApiError(response, errorLabel));
    }
    return response.json();
}

async function saveDocumentToWorkFolder(url, body, errorLabel) {
    return persistJsonPost(url, { ...body, persist_only: true }, errorLabel);
}

async function uploadFilesToFolder(target, fileList, options = {}) {
    const files = Array.from(fileList || []);
    if (!files.length) {
        return null;
    }

    const preserveRelativePath = Boolean(options.preserveRelativePath);
    const formData = new FormData();
    for (const file of files) {
        const uploadName = preserveRelativePath && file.webkitRelativePath
            ? file.webkitRelativePath
            : file.name;
        formData.append('files', file, uploadName);
    }

    const response = await fetch(
        `${getConfigApiBase()}/api/config/upload-files?target_folder=${encodeURIComponent(target)}`,
        {
            method: 'POST',
            body: formData,
        },
    );
    if (!response.ok) {
        throw new Error(await readApiError(response, 'Не удалось загрузить файлы'));
    }
    return response.json();
}

async function saveWorkFolderSettings() {
    const inputEl = document.getElementById('settings-work-folder');
    const workFolder = (inputEl?.value || '').trim();
    if (!workFolder) {
        setSettingsStatus('Укажите путь к рабочей папке', 'error');
        return;
    }

    setSettingsStatus('Сохранение...', 'info');
    try {
        const result = await persistJsonPost(
            `${getConfigApiBase()}/api/config/save`,
            { work_folder: workFolder },
            'Не удалось сохранить рабочую папку',
        );
        appConfigCache = result;
        renderSettingsForm(result);
        setSettingsStatus(result.message || 'Рабочая папка сохранена', 'success');
        if (typeof updateStatsInCard === 'function') {
            await updateStatsInCard();
        }
    } catch (error) {
        setSettingsStatus(formatCaughtError(error, 'Не удалось сохранить рабочую папку'), 'error');
    }
}

async function resetWorkFolderSettings() {
    if (!confirm('Установить рабочую папку по умолчанию?')) {
        return;
    }

    setSettingsStatus('Сброс...', 'info');
    try {
        const result = await persistJsonPost(
            `${getConfigApiBase()}/api/config/default`,
            {},
            'Не удалось сбросить рабочую папку',
        );
        appConfigCache = result;
        renderSettingsForm(result);
        setSettingsStatus(result.message || 'Установлена папка по умолчанию', 'success');
        if (typeof updateStatsInCard === 'function') {
            await updateStatsInCard();
        }
    } catch (error) {
        setSettingsStatus(formatCaughtError(error, 'Не удалось сбросить рабочую папку'), 'error');
    }
}

async function browseWorkFolder() {
    const inputEl = document.getElementById('settings-work-folder');
    const initialDir = (inputEl?.value || '').trim();

    setSettingsStatus('Откройте окно выбора папки...', 'info');
    try {
        const result = await persistJsonPost(
            `${getConfigApiBase()}/api/config/browse-folder`,
            { initial_dir: initialDir },
            'Не удалось открыть диалог выбора папки',
        );
        if (result.cancelled) {
            setSettingsStatus('', 'info');
            return;
        }
        if (inputEl && result.work_folder) {
            inputEl.value = result.work_folder;
        }
        setSettingsStatus('Папка выбрана. Нажмите «Сохранить».', 'success');
    } catch (error) {
        setSettingsStatus(formatCaughtError(error, 'Не удалось выбрать папку'), 'error');
    }
}

function bindSettingsModalHandlers() {
    const modal = document.getElementById('app-settings-modal');
    if (!modal || modal.dataset.bound === '1') return;
    modal.dataset.bound = '1';

    modal.querySelectorAll('[data-close-settings]').forEach((el) => {
        el.addEventListener('click', (event) => {
            event.stopPropagation();
            closeSettingsModal();
        });
    });

    document.getElementById('btn-settings-save')?.addEventListener('click', saveWorkFolderSettings);
    document.getElementById('btn-settings-default')?.addEventListener('click', resetWorkFolderSettings);
    document.getElementById('btn-settings-browse')?.addEventListener('click', browseWorkFolder);

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal && !modal.hidden) {
            closeSettingsModal();
        }
    });
}

function openSettingsModal() {
    const modal = document.getElementById('app-settings-modal');
    if (!modal) return;

    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');

    fetchAppConfig(true)
        .then((config) => {
            renderSettingsForm(config);
            setSettingsStatus('', 'info');
        })
        .catch((error) => {
            renderSettingsForm({
                data_root: '—',
                work_folder: '—',
                paths_editable: false,
                settings_hint: formatCaughtError(error, 'Не удалось загрузить настройки с сервера'),
            });
            setSettingsStatus(formatCaughtError(error, 'Ошибка загрузки настроек'), 'error');
        });
}

function closeSettingsModal() {
    const modal = document.getElementById('app-settings-modal');
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
}

function initSettingsGear() {
    bindSettingsModalHandlers();
    const versionEl = document.getElementById('settings-ui-version');
    if (versionEl) {
        versionEl.textContent = APP_UI_VERSION;
    }
    document.getElementById('btn-app-settings')?.addEventListener('click', (event) => {
        event.stopPropagation();
        openSettingsModal();
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initSettingsGear();
    fetchAppConfig().catch(() => {
        /* настройки подгрузятся при открытии модального окна */
    });
});

window.fetchAppConfig = fetchAppConfig;
window.saveDocumentToWorkFolder = saveDocumentToWorkFolder;
window.uploadFilesToFolder = uploadFilesToFolder;
window.openSettingsModal = openSettingsModal;
