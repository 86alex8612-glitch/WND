/**
 * Скачивание файлов, сформированных на сервере.
 */

function parseFilenameFromDisposition(header, fallback) {
    if (!header) {
        return fallback;
    }
    const utf8Match = header.match(/filename\*=UTF-8''([^;\n]+)/i);
    if (utf8Match) {
        try {
            return decodeURIComponent(utf8Match[1]);
        } catch (_) {
            /* ignore */
        }
    }
    const plainMatch = header.match(/filename="([^"]+)"/i);
    if (plainMatch) {
        return plainMatch[1];
    }
    return fallback;
}

async function triggerBrowserDownload(response, fallbackFilename) {
    const blob = await response.blob();
    const filename = parseFilenameFromDisposition(
        response.headers.get('Content-Disposition'),
        fallbackFilename,
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    return filename;
}

async function downloadFromPost(url, body, fallbackFilename, errorLabel) {
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        let detail = errorLabel || 'Не удалось скачать файл';
        try {
            const data = await response.json();
            detail = data.detail || data.message || detail;
        } catch (_) {
            try {
                const text = await response.text();
                if (text) {
                    detail = text.substring(0, 200);
                }
            } catch (_) {
                /* ignore */
            }
        }
        throw new Error(typeof detail === 'string' ? detail : errorLabel);
    }

    return triggerBrowserDownload(response, fallbackFilename);
}

window.parseFilenameFromDisposition = parseFilenameFromDisposition;
window.triggerBrowserDownload = triggerBrowserDownload;
window.downloadFromPost = downloadFromPost;
