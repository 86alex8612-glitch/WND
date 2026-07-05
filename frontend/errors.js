/**
 * Понятные сообщения об ошибках на русском языке для интерфейса.
 */
const WND_SERVER_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8011'
    : window.location.origin;

const WND_SERVER_HINT = `Убедитесь, что сервер запущен (start_server.bat) и доступен по адресу ${WND_SERVER_URL}.`;

function humanizeErrorMessage(raw) {
    if (raw === null || raw === undefined) {
        return 'Произошла неизвестная ошибка. Попробуйте ещё раз.';
    }

    const text = String(raw).trim().replace(/\s+/g, ' ');
    if (!text) {
        return 'Произошла неизвестная ошибка. Попробуйте ещё раз.';
    }

    const lower = text.toLowerCase();

    const rules = [
        [['failed to fetch', 'networkerror', 'load failed', 'network request failed'],
            `Не удалось связаться с сервером. ${WND_SERVER_HINT}`],
        [['permission denied', 'errno 13', 'being used by another process'],
            'Не удалось сохранить файл: он открыт в другой программе (часто Adobe Acrobat). Закройте документ и повторите загрузку.'],
        [['winerror 32', 'cannot access the file'],
            'Файл используется другой программой. Закройте его и повторите операцию.'],
        [['openai', 'api key', 'authentication', 'incorrect api key'],
            'Ошибка доступа к OpenAI API. Проверьте ключ OPENAI_API_KEY в файле .env.'],
        [['rate limit', 'ratelimit'],
            'Превышен лимит запросов к OpenAI API. Подождите и повторите попытку.'],
        [['insufficient_quota', 'quota', 'billing'],
            'Исчерпана квота OpenAI API. Проверьте баланс аккаунта.'],
        [['timeout', 'timed out'],
            'Превышено время ожидания ответа сервера. Попробуйте ещё раз.'],
        [['unsupported format', 'неподдерживаемый формат'],
            'Неподдерживаемый формат файла. Загрузите PDF, DOCX или TXT.'],
        [['не содержит текста'],
            'Из документа не удалось извлечь текст. Возможно, это скан без текстового слоя.'],
        [['диалог не найден'],
            'Диалог не найден. Возможно, он уже удалён — начните анализ заново.'],
        [['http error! status: 404', 'status: 404', 'not found'],
            'Запрашиваемые данные не найдены.'],
        [['http error! status: 409', 'status: 409'],
            'Файл открыт в другой программе. Закройте его и повторите загрузку.'],
        [['http error! status: 400', 'status: 400'],
            'Некорректный запрос. Проверьте введённые данные и выбранный файл.'],
        [['http error! status: 500', 'status: 500', 'internal server error'],
            'Внутренняя ошибка сервера. Попробуйте ещё раз или перезапустите сервер.'],
    ];

    for (const [patterns, message] of rules) {
        if (patterns.some((pattern) => lower.includes(pattern))) {
            return message;
        }
    }

    if (/^ошибка/i.test(text) || /^не удалось/i.test(text) || text.includes('❌')) {
        return text;
    }

    if (/errno|traceback|exception|winerror|\.py\b|\[Errno/i.test(text)) {
        return 'Произошла внутренняя ошибка. Попробуйте ещё раз или перезапустите сервер.';
    }

    return text;
}

async function readApiError(response, fallbackMessage) {
    let payload = null;

    try {
        payload = await response.clone().json();
    } catch (_) {
        payload = null;
    }

    if (payload) {
        if (typeof payload.detail === 'string') {
            return humanizeErrorMessage(payload.detail);
        }
        if (Array.isArray(payload.detail)) {
            const parts = payload.detail
                .map((item) => item?.msg || item?.message || (typeof item === 'string' ? item : ''))
                .filter(Boolean);
            if (parts.length) {
                return humanizeErrorMessage(parts.join('; '));
            }
        }
        if (payload.message) {
            return humanizeErrorMessage(payload.message);
        }
    }

    if (response.status === 404) {
        return 'Запрашиваемые данные не найдены.';
    }
    if (response.status === 409) {
        return 'Файл открыт в другой программе. Закройте его и повторите операцию.';
    }
    if (response.status === 400) {
        return 'Некорректный запрос. Проверьте введённые данные.';
    }
    if (response.status >= 500) {
        return 'Внутренняя ошибка сервера. Попробуйте ещё раз или перезапустите сервер.';
    }
    if (response.status === 0) {
        return `Не удалось связаться с сервером. ${WND_SERVER_HINT}`;
    }

    return humanizeErrorMessage(fallbackMessage || `Ошибка сервера (код ${response.status}).`);
}

function formatCaughtError(error, fallbackMessage) {
    if (!error) {
        return humanizeErrorMessage(fallbackMessage);
    }
    if (error.message) {
        return humanizeErrorMessage(error.message);
    }
    return humanizeErrorMessage(fallbackMessage || String(error));
}

window.humanizeErrorMessage = humanizeErrorMessage;
window.readApiError = readApiError;
window.formatCaughtError = formatCaughtError;
window.WND_SERVER_HINT = WND_SERVER_HINT;
