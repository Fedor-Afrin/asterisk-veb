const ExtensionsModule = (() => {
    function generatePassword(length = 12) {
        const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*";
        return Array.from({length}, () => charset[Math.floor(Math.random() * charset.length)]).join('');
    }

    function renderStatusBadge(statusText) {
        if (!statusText) return '<span style="color: gray;">⚫ Не в сети</span>';
        if (statusText.includes('Not in use')) return '<span style="color: green; font-weight: bold;">📞 Свободен</span>';
        if (statusText.includes('In use') || statusText.includes('Ringing')) return '<span style="color: red; font-weight: bold;">🔴 Занят</span>';
        if (statusText.includes('Unavailable')) return '<span style="color: #666;">⚫ Не в сети</span>';
        return `<span style="color: #333;">⚪ ${statusText}</span>`;
    }

    async function loadExtensions() {
        const container = document.getElementById('extensionsContainer');
        try {
            const [extensions, statusData] = await Promise.all([
                API.getExtensions(),
                API.getStatus()
            ]);
            const statuses = statusData.statuses || {};

            if (extensions.length === 0) {
                container.innerHTML = '<p>Номера пока не созданы.</p>';
                return;
            }

            let html = '<table style="width:100%; border-collapse: collapse; margin-top: 10px;">';
            html += '<tr style="background: #f1f1f1; text-align: left;">';
            html += '<th style="padding: 8px; border: 1px solid #ddd;">Номер</th>';
            html += '<th style="padding: 8px; border: 1px solid #ddd;">Caller ID</th>';
            html += '<th style="padding: 8px; border: 1px solid #ddd;">Статус</th>'; 
            html += '<th style="padding: 8px; border: 1px solid #ddd;">Транспорт</th>';
            html += '<th style="padding: 8px; border: 1px solid #ddd;">Пароль</th>';
            html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Действия</th>';
            html += '</tr>';

            extensions.forEach(ext => {
                const extStr = String(ext.extension);
                const currentStatus = statuses[extStr] || '';
                html += `<tr>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${ext.extension}</td>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd;">${ext.callerid}</td>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd;">${renderStatusBadge(currentStatus)}</td>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd;">${ext.transport === 'transport-tls' ? 'TLS' : 'UDP'}</td>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd;"><span class="secret-text" data-secret="${ext.secret}" style="font-family: monospace;">••••••••</span> <button onclick="ExtensionsModule.toggleSecret(this)" style="padding: 2px 6px; font-size: 11px; margin-left: 5px; width: auto; background:#6c757d;">👁</button></td>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd; text-align: center;"><button onclick="ExtensionsModule.deleteExtension(${ext.id})" style="background-color: #dc3545; color: white; padding: 4px 8px; font-size: 12px; width: auto;">Удалить</button></td>`;
                html += `</tr>`;
            });
            html += '</table>';
            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = '<p style="color: red;">Не удалось загрузить список номеров.</p>';
        }
    }

    function toggleSecret(btn) {
        const span = btn.previousElementSibling;
        const currentSecret = span.getAttribute('data-secret');
        if (span.textContent === '••••••••') {
            span.textContent = currentSecret;
            btn.textContent = '🔒';
        } else {
            span.textContent = '••••••••';
            btn.textContent = '👁';
        }
    }

    async function deleteExtension(id) {
        if (!confirm('Вы уверены, что хотите удалить этот номер?')) return;
        try {
            const response = await API.deleteExtension(id);
            if (response.ok) loadExtensions();
            else alert('Не удалось удалить номер');
        } catch (err) { alert('Ошибка соединения с сервером'); }
    }

    function init() {
        document.getElementById('generateBtn').addEventListener('click', () => {
            document.getElementById('extSecret').value = generatePassword(12);
        });

        document.getElementById('extForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const extension = parseInt(document.getElementById('extNumber').value);
            const secret = document.getElementById('extSecret').value;
            const callerid = document.getElementById('extCallerId').value;
            const transport = document.getElementById('extTransport').value;
            const resultDiv = document.getElementById('extResult');

            try {
                const response = await API.createExtension({ extension, secret, callerid, transport });
                const data = await response.json();
                if (response.ok) {
                    resultDiv.style.color = 'green';
                    resultDiv.textContent = `Номер ${data.extension} успешно создан!`;
                    document.getElementById('extForm').reset();
                    loadExtensions();
                } else {
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = `Ошибка: ${data.detail || 'Не удалось создать номер'}`;
                }
            } catch (err) {
                resultDiv.style.color = 'red';
                resultDiv.textContent = `Ошибка соединения с сервером`;
            }
        });

        document.getElementById('loadExtsBtn').addEventListener('click', loadExtensions);
    }

    return { init, loadExtensions, toggleSecret, deleteExtension };
})();