// Вкладка "Записи разговоров": выбор номеров для записи и архив с фильтрами и плеером.
const RecordingsModule = (() => {
    const TEXT = {
        selectExtensions: 'Выберите номера',
        enabledFor: 'Запись включена для:',
        createExtensionsFirst: 'Сначала создайте номера.',
        saved: 'Сохранено. Нажмите «Применить конфигурацию», чтобы запись началась.',
        saveFailed: 'Не удалось сохранить настройки.',
        loadFailed: 'Не удалось загрузить записи.',
        found: 'Найдено записей:',
        none: 'Записи не найдены.',
        showMore: 'Показать ещё',
        confirmDelete: 'Удалить эту запись?',
        connectionError: 'Ошибка соединения с сервером'
    };
    const PAGE = 50;

    let shown = 0;
    let total = 0;
    const el = (id) => document.getElementById(id);

    function fmtDuration(sec) {
        const m = Math.floor(sec / 60), s = sec % 60;
        return m + ':' + String(s).padStart(2, '0');
    }

    function fmtDate(iso) {
        const lang = document.documentElement.lang || undefined;
        return new Date(iso).toLocaleString(lang, { dateStyle: 'short', timeStyle: 'medium' });
    }

    // ---------- настройки записи ----------
    function updateSummary() {
        const numbers = Array.from(document.querySelectorAll('input[name="recExt"]:checked')).map(cb => cb.dataset.number);
        el('recSummary').textContent = numbers.length ? TEXT.enabledFor + ' ' + numbers.join(', ') : TEXT.selectExtensions;
    }

    async function loadSettings() {
        const list = el('recExtList');
        try {
            const [exts, settings] = await Promise.all([
                fetch('/api/extensions').then(r => r.json()),
                fetch('/api/recordings/settings').then(r => r.json())
            ]);
            if (!Array.isArray(exts) || !settings.extensions) return;
            if (exts.length === 0) {
                list.innerHTML = `<p style="color: red;">${TEXT.createExtensionsFirst}</p>`;
                updateSummary();
                return;
            }
            const chosen = new Set(settings.extensions);
            list.innerHTML = exts.map(e => `<label style="display: block; margin-bottom: 5px; cursor: pointer;">
                    <input type="checkbox" name="recExt" data-number="${e.extension}" ${chosen.has(e.extension) ? 'checked' : ''}>
                    <b>${e.extension}</b> (${e.callerid})
                </label>`).join('');
            list.querySelectorAll('input').forEach(cb => cb.addEventListener('change', updateSummary));
            updateSummary();
        } catch (err) { /* список останется как есть */ }
    }

    async function saveSettings() {
        const result = el('recSettingsResult');
        const numbers = Array.from(document.querySelectorAll('input[name="recExt"]:checked')).map(cb => parseInt(cb.dataset.number));
        try {
            const res = await fetch('/api/recordings/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ extensions: numbers })
            });
            if (res.ok) {
                result.style.color = 'green';
                result.textContent = TEXT.saved;
            } else if (res.status !== 401) {
                result.style.color = 'red';
                result.textContent = TEXT.saveFailed;
            }
        } catch (err) {
            result.style.color = 'red';
            result.textContent = TEXT.connectionError;
        }
    }

    // ---------- архив ----------
    function filterQuery(offset) {
        const params = new URLSearchParams({ limit: PAGE, offset });
        const number = el('recFilterNumber').value.trim();
        if (number) params.set('number', number);
        if (el('recFilterFrom').value) params.set('date_from', el('recFilterFrom').value);
        if (el('recFilterTo').value) params.set('date_to', el('recFilterTo').value);
        if (el('recFilterMin').value) params.set('min_duration', el('recFilterMin').value);
        return params.toString();
    }

    function rowHtml(r) {
        const cell = 'padding: 8px; border: 1px solid #ddd;';
        return `<tr>
            <td style="${cell}">${fmtDate(r.date)}</td>
            <td style="${cell} font-weight: bold;">${r.caller}</td>
            <td style="${cell} font-weight: bold;">${r.callee}</td>
            <td style="${cell}">${fmtDuration(r.duration)}</td>
            <td style="${cell}"><audio controls preload="none" src="/api/recordings/${r.id}/audio" style="height: 32px; width: 220px;"></audio></td>
            <td style="${cell} text-align: center; white-space: nowrap;">
                <a href="/api/recordings/${r.id}/audio?download=1" style="background-color: #17a2b8; color: white; padding: 4px 8px; font-size: 12px; border-radius: 3px; text-decoration: none; margin-right: 5px;">Скачать</a>
                <button onclick="RecordingsModule.remove(${r.id})" style="background-color: #dc3545; color: white; padding: 4px 8px; font-size: 12px;">Удалить</button>
            </td>
        </tr>`;
    }

    async function load(append) {
        const container = el('recordsContainer');
        const offset = append ? shown : 0;
        try {
            const res = await fetch('/api/recordings?' + filterQuery(offset));
            if (!res.ok) {
                if (res.status !== 401) container.innerHTML = `<p style="color: red;">${TEXT.loadFailed}</p>`;
                return;
            }
            const data = await res.json();
            total = data.total;
            if (!append) {
                shown = 0;
                container.innerHTML = '';
            }
            el('recSummaryLine').textContent = TEXT.found + ' ' + total;

            if (total === 0) {
                container.innerHTML = `<p style="color: #666; font-style: italic;">${TEXT.none}</p>`;
                el('recMoreBtn').style.display = 'none';
                return;
            }
            let table = container.querySelector('table');
            if (!table) {
                container.innerHTML = '<table style="width:100%; border-collapse: collapse;"><tr style="background: #f1f1f1; text-align: left;">' +
                    '<th style="padding: 8px; border: 1px solid #ddd;">Дата</th>' +
                    '<th style="padding: 8px; border: 1px solid #ddd;">Звонящий</th>' +
                    '<th style="padding: 8px; border: 1px solid #ddd;">Вызываемый</th>' +
                    '<th style="padding: 8px; border: 1px solid #ddd;">Длительность</th>' +
                    '<th style="padding: 8px; border: 1px solid #ddd;">Прослушать</th>' +
                    '<th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Действия</th></tr></table>';
                table = container.querySelector('table');
            }
            table.insertAdjacentHTML('beforeend', data.items.map(rowHtml).join(''));
            shown += data.items.length;
            el('recMoreBtn').style.display = shown < total ? 'inline-block' : 'none';
        } catch (err) {
            container.innerHTML = `<p style="color: red;">${TEXT.loadFailed}</p>`;
        }
    }

    async function remove(id) {
        if (!confirm(TEXT.confirmDelete)) return;
        try {
            await fetch('/api/recordings/' + id, { method: 'DELETE' });
        } catch (err) { /* список обновится ниже */ }
        load(false);
    }

    function resetFilters() {
        ['recFilterNumber', 'recFilterFrom', 'recFilterTo', 'recFilterMin'].forEach(id => { el(id).value = ''; });
        load(false);
    }

    function init() {
        el('saveRecSettingsBtn').addEventListener('click', saveSettings);
        el('recSearchBtn').addEventListener('click', () => load(false));
        el('recResetBtn').addEventListener('click', resetFilters);
        el('recMoreBtn').addEventListener('click', () => load(true));
        el('recFilterNumber').addEventListener('keydown', (e) => { if (e.key === 'Enter') load(false); });
    }

    function open() {
        loadSettings();
        load(false);
    }

    return { init, open, remove };
})();
