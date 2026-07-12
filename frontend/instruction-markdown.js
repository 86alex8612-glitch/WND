/**
 * Общий рендер Markdown → HTML для инструкций (главная и помощник ВНД).
 */

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

window.escapeInstructionHtml = escapeInstructionHtml;
window.renderInstructionMarkdown = renderInstructionMarkdown;
