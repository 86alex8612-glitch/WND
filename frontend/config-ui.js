/**
 * Настройки рабочей папки (config.cfg) и сохранение в рабочие каталоги.
 */

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

function formatFolderList(config) {
    const folders = config?.display_folders || [];
    if (!folders.length) {
        return '';
    }
    return folders.map((item) => `${item.name}: ${item.path}`).join('\n');
}

function buildPreviewFolders(config, workFolderOverride) {
    const root = String(workFolderOverride || config?.work_folder || '').trim().replace(/[\\/]+$/, '');
    const template = config?.display_folders || [];
    if (!root) {
        return template;
    }
    return template.map((item) => ({
        ...item,
        path: `${root}\\${item.name}`,
    }));
}

function renderConfigFolderList(container, config, workFolderOverride) {
    if (!container) return;
    const folders = buildPreviewFolders(config, workFolderOverride);
    if (!folders.length) {
        container.innerHTML = '<p class="config-folders-empty">Папки не заданы</p>';
        return;
    }
    container.innerHTML = folders.map((item) => (
        `<div class="config-folder-row">`
        + `<span class="config-folder-name">${escapeConfigHtml(item.name)}</span>`
        + `<div class="config-folder-details">`
        + `<span class="config-folder-desc">${escapeConfigHtml(item.description || '')}</span>`
        + `<span class="config-folder-path">${escapeConfigHtml(item.path)}</span>`
        + `</div>`
        + `</div>`
    )).join('');
}

function refreshSettingsFolderPreview() {
    const input = document.getElementById('settings-work-folder');
    const container = document.getElementById('settings-folder-list');
    if (!appConfigCache || !container) return;
    renderConfigFolderList(container, appConfigCache, input?.value?.trim() || '');
}

function escapeConfigHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
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

    document.getElementById('btn-settings-save')?.addEventListener('click', saveSettingsFromModal);
    document.getElementById('btn-settings-default')?.addEventListener('click', resetSettingsToDefault);
    document.getElementById('btn-settings-browse')?.addEventListener('click', browseWorkFolderFromModal);
    document.getElementById('settings-work-folder')?.addEventListener('input', refreshSettingsFolderPreview);

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && modal && !modal.hidden) {
            closeSettingsModal();
        }
    });
}

function openSettingsModal() {
    const modal = document.getElementById('app-settings-modal');
    if (!modal) return;

    fetchAppConfig(true)
        .then((config) => {
            const input = document.getElementById('settings-work-folder');
            if (input) {
                input.value = config.work_folder || config.default_work_folder || 'C:\\WND';
            }
            renderConfigFolderList(document.getElementById('settings-folder-list'), config);
            modal.hidden = false;
            modal.setAttribute('aria-hidden', 'false');
        })
        .catch((error) => {
            alert('❌ ' + formatCaughtError(error, 'Не удалось открыть настройки'));
        });
}

function closeSettingsModal() {
    const modal = document.getElementById('app-settings-modal');
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
}

async function browseWorkFolderFromModal() {
    const input = document.getElementById('settings-work-folder');
    const browseBtn = document.getElementById('btn-settings-browse');
    const initialPath = input?.value?.trim() || appConfigCache?.work_folder || '';

    if (browseBtn) {
        browseBtn.disabled = true;
        browseBtn.textContent = '…';
    }

    try {
        const result = await persistJsonPost(
            `${getConfigApiBase()}/api/config/browse-folder`,
            { initial_path: initialPath },
            'Не удалось открыть выбор папки',
        );
        if (result.status === 'cancelled' || !result.path) {
            return;
        }
        if (input) {
            input.value = result.path;
        }
        refreshSettingsFolderPreview();
    } catch (error) {
        alert('❌ ' + formatCaughtError(error, 'Не удалось открыть выбор папки'));
    } finally {
        if (browseBtn) {
            browseBtn.disabled = false;
            browseBtn.textContent = 'Обзор…';
        }
    }
}

async function saveSettingsFromModal() {
    const input = document.getElementById('settings-work-folder');
    const workFolder = input?.value?.trim();
    if (!workFolder) {
        alert('Укажите рабочую папку');
        return;
    }

    try {
        const result = await persistJsonPost(
            `${getConfigApiBase()}/api/config/save`,
            { work_folder: workFolder },
            'Не удалось сохранить настройки',
        );
        appConfigCache = result;
        renderConfigFolderList(document.getElementById('settings-folder-list'), result);
        alert('✅ ' + (result.message || 'Настройки сохранены'));
    } catch (error) {
        alert('❌ ' + formatCaughtError(error, 'Не удалось сохранить настройки'));
    }
}

async function resetSettingsToDefault() {
    try {
        const result = await persistJsonPost(
            `${getConfigApiBase()}/api/config/default`,
            {},
            'Не удалось восстановить настройки',
        );
        appConfigCache = result;
        const input = document.getElementById('settings-work-folder');
        if (input) {
            input.value = result.work_folder || result.default_work_folder || 'C:\\WND';
        }
        renderConfigFolderList(document.getElementById('settings-folder-list'), result);
        alert('✅ ' + (result.message || 'Установлены настройки по умолчанию'));
    } catch (error) {
        alert('❌ ' + formatCaughtError(error, 'Не удалось восстановить настройки'));
    }
}

function initSettingsGear() {
    bindSettingsModalHandlers();
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
window.openSettingsModal = openSettingsModal;
