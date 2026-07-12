/**
 * Инструкция пользователя на главной странице (из ИНСТРУКЦИЯ_ПОЛЬЗОВАТЕЛЯ.md).
 */

const USER_INSTRUCTION_API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8011'
    : '';

let userInstructionCache = '';
let userInstructionLoading = false;

function getUserInstructionModal() {
    return document.getElementById('user-instruction-modal');
}

function getUserInstructionBody() {
    return document.getElementById('user-instruction-body');
}

function setUserInstructionBody(html, isError = false) {
    const body = getUserInstructionBody();
    if (!body) {
        return;
    }
    body.innerHTML = html;
    body.classList.toggle('user-instruction-body-error', isError);
}

async function loadUserInstructionContent(forceReload = false) {
    if (!forceReload && userInstructionCache) {
        return userInstructionCache;
    }
    if (userInstructionLoading) {
        return userInstructionCache;
    }

    userInstructionLoading = true;
    try {
        const response = await fetch(`${USER_INSTRUCTION_API_BASE}/api/user-instruction?t=${Date.now()}`);
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.detail || 'Не удалось загрузить инструкцию');
        }
        const data = await response.json();
        userInstructionCache = renderInstructionMarkdown(data.content || '');
        const titleEl = document.getElementById('user-instruction-title');
        if (titleEl && data.title) {
            titleEl.textContent = data.title;
        }
        return userInstructionCache;
    } finally {
        userInstructionLoading = false;
    }
}

async function openUserInstructionModal() {
    const modal = getUserInstructionModal();
    if (!modal) {
        return;
    }

    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    setUserInstructionBody('<p class="user-instruction-loading">Загрузка инструкции…</p>');

    try {
        const html = await loadUserInstructionContent();
        setUserInstructionBody(html);
    } catch (error) {
        const message = typeof formatCaughtError === 'function'
            ? formatCaughtError(error, 'Не удалось загрузить инструкцию')
            : (error?.message || 'Не удалось загрузить инструкцию');
        setUserInstructionBody(`<p class="user-instruction-error">${escapeInstructionHtml(message)}</p>`, true);
    }
}

function closeUserInstructionModal() {
    const modal = getUserInstructionModal();
    if (!modal) {
        return;
    }
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
}

function bindUserInstructionHandlers() {
    document.getElementById('btn-user-instruction')?.addEventListener('click', () => {
        openUserInstructionModal();
    });

    const modal = getUserInstructionModal();
    if (!modal) {
        return;
    }

    modal.querySelectorAll('[data-close-user-instruction]').forEach((element) => {
        element.addEventListener('click', closeUserInstructionModal);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.hidden) {
            closeUserInstructionModal();
        }
    });
}

document.addEventListener('DOMContentLoaded', bindUserInstructionHandlers);

window.openUserInstructionModal = openUserInstructionModal;
window.closeUserInstructionModal = closeUserInstructionModal;
