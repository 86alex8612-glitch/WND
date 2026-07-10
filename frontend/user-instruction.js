/**
 * Инструкция пользователя на главной странице (из ИНСТРУКЦИЯ_ПОЛЬЗОВАТЕЛЯ.md).
 */

const USER_INSTRUCTION_API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8011'
    : '';

let userInstructionCache = '';
let userInstructionLoading = false;

function escapeInstructionHtml(text) {
    return String(text ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function renderInstructionInline(text) {
    let html = escapeInstructionHtml(text);
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    return html;
}

function isInstructionTableSeparator(line) {
    const trimmed = line.trim();
    if (!trimmed.includes('|')) {
        return false;
    }
    return trimmed.replace(/[|\s:]/g, '').replace(/-/g, '') === '';
}

function parseInstructionTableRow(line) {
    const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '');
    return trimmed.split('|').map((cell) => cell.trim());
}

function renderInstructionMarkdown(markdown) {
    const lines = String(markdown || '').replace(/\r\n/g, '\n').split('\n');
    const blocks = [];
    let index = 0;

    while (index < lines.length) {
        const line = lines[index];
        const trimmed = line.trim();

        if (!trimmed) {
            index += 1;
            continue;
        }

        if (/^---+$/.test(trimmed)) {
            blocks.push('<hr>');
            index += 1;
            continue;
        }

        const headingMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
        if (headingMatch) {
            const level = headingMatch[1].length;
            blocks.push(`<h${level}>${renderInstructionInline(headingMatch[2])}</h${level}>`);
            index += 1;
            continue;
        }

        if (trimmed.startsWith('> ')) {
            const quoteLines = [];
            while (index < lines.length && lines[index].trim().startsWith('> ')) {
                quoteLines.push(lines[index].trim().slice(2));
                index += 1;
            }
            blocks.push(`<blockquote><p>${renderInstructionInline(quoteLines.join(' '))}</p></blockquote>`);
            continue;
        }

        if (trimmed.includes('|') && index + 1 < lines.length && isInstructionTableSeparator(lines[index + 1])) {
            const headerCells = parseInstructionTableRow(lines[index]);
            index += 2;
            const bodyRows = [];
            while (index < lines.length) {
                const rowLine = lines[index].trim();
                if (!rowLine || !rowLine.includes('|')) {
                    break;
                }
                bodyRows.push(parseInstructionTableRow(lines[index]));
                index += 1;
            }
            const thead = `<thead><tr>${headerCells.map((cell) => `<th>${renderInstructionInline(cell)}</th>`).join('')}</tr></thead>`;
            const tbody = bodyRows.length
                ? `<tbody>${bodyRows.map((row) => `<tr>${row.map((cell) => `<td>${renderInstructionInline(cell)}</td>`).join('')}</tr>`).join('')}</tbody>`
                : '';
            blocks.push(`<div class="user-instruction-table-wrap"><table class="user-instruction-table">${thead}${tbody}</table></div>`);
            continue;
        }

        if (/^[-*]\s+/.test(trimmed)) {
            const items = [];
            while (index < lines.length && /^[-*]\s+/.test(lines[index].trim())) {
                items.push(lines[index].trim().replace(/^[-*]\s+/, ''));
                index += 1;
            }
            blocks.push(`<ul>${items.map((item) => `<li>${renderInstructionInline(item)}</li>`).join('')}</ul>`);
            continue;
        }

        if (/^\d+\.\s+/.test(trimmed)) {
            const items = [];
            while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
                items.push(lines[index].trim().replace(/^\d+\.\s+/, ''));
                index += 1;
            }
            blocks.push(`<ol>${items.map((item) => `<li>${renderInstructionInline(item)}</li>`).join('')}</ol>`);
            continue;
        }

        const paragraphLines = [];
        while (index < lines.length) {
            const paragraphLine = lines[index];
            const paragraphTrimmed = paragraphLine.trim();
            if (!paragraphTrimmed) {
                break;
            }
            if (
                /^---+$/.test(paragraphTrimmed)
                || /^(#{1,4})\s+/.test(paragraphTrimmed)
                || paragraphTrimmed.startsWith('> ')
                || /^[-*]\s+/.test(paragraphTrimmed)
                || /^\d+\.\s+/.test(paragraphTrimmed)
                || (paragraphTrimmed.includes('|') && index + 1 < lines.length && isInstructionTableSeparator(lines[index + 1]))
            ) {
                break;
            }
            paragraphLines.push(paragraphTrimmed);
            index += 1;
        }
        blocks.push(`<p>${renderInstructionInline(paragraphLines.join(' '))}</p>`);
    }

    return blocks.join('\n');
}

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
