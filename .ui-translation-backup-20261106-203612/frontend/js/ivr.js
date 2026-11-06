const IvrModule = (() => {
    let editingIvrId = null;
    let loadedIvrs = []; // Кэш для быстрого редактирования

    async function loadIvrs() {
        const container = document.getElementById('ivrContainer');
        try {
            loadedIvrs = await API.getIvrs();
            if (loadedIvrs.length === 0) {
                container.innerHTML = '<p>IVR меню пока не созданы.</p>';
                return;
            }
            
            let html = '<table style="width:100%; border-collapse: collapse; margin-top: 10px;">';
            html += '<tr style="background: #f1f1f1; text-align: left;"><th style="padding: 8px; border: 1px solid #ddd;">Название</th><th style="padding: 8px; border: 1px solid #ddd;">Вн. номер</th><th style="padding: 8px; border: 1px solid #ddd;">Аудиофайл</th><th style="padding: 8px; border: 1px solid #ddd; width: 35%;">Маршрутизация</th><th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Действия</th></tr>';
            
            loadedIvrs.forEach(i => {
                let routesHtml = '<ul style="margin: 0; padding-left: 20px; font-size: 13px; line-height: 1.4;">';
                if (i.options && Object.keys(i.options).length > 0) {
                    for (const [digit, action] of Object.entries(i.options)) {
                        let actionText = '';
                        if (action.type === 'extension') actionText = `Вн. номер <b>${action.target}</b>`;
                        else if (action.type === 'group') actionText = `Группа <b>${action.target}</b>`;
                        else if (action.type === 'ivr') actionText = `IVR <b>${action.target}</b>`;
                        else if (action.type === 'hangup') actionText = `Отбой`;

                        let keyName = `Кнопка [ ${digit} ]`;
                        if (digit === 't') keyName = `<span style="color:#d35400;">Таймаут</span>`;
                        if (digit === 'i') keyName = `<span style="color:#c0392b;">Ошибка ввода</span>`;

                        routesHtml += `<li>${keyName} ➔ ${actionText}</li>`;
                    }
                } else {
                    routesHtml += '<li style="color:#7f8c8d;">Нет действий (только приветствие)</li>';
                }
                routesHtml += '</ul>';

                html += `<tr>
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${i.name}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; color: #28a745;">${i.extension}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; font-family: monospace;">${i.greeting_file || 'beep'}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${routesHtml}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                        <button onclick="IvrModule.startEditIvr(${i.id})" style="background-color: #ffc107; color: #333; padding: 4px 8px; margin-right: 5px; font-size: 12px; border: none; cursor: pointer; border-radius: 3px;">Ред.</button>
                        <button onclick="IvrModule.deleteIvr(${i.id})" style="background-color: #dc3545; color: white; padding: 4px 8px; font-size: 12px; border: none; cursor: pointer; border-radius: 3px;">Удалить</button>
                    </td>
                </tr>`;
            });
            html += '</table>';
            container.innerHTML = html;
        } catch (err) { container.innerHTML = '<p style="color: red;">Ошибка загрузки IVR.</p>'; }
    }

    async function deleteIvr(id) {
        if (!confirm('Удалить это голосовое меню?')) return;
        await API.deleteIvr(id);
        if (editingIvrId === id) cancelEdit();
        loadIvrs();
    }

    function startEditIvr(id) {
        const ivr = loadedIvrs.find(i => i.id === id);
        if (!ivr) return;

        editingIvrId = id;
        document.getElementById('ivrFormTitle').textContent = 'Редактирование IVR: ' + ivr.name;
        document.getElementById('ivrName').value = ivr.name;
        document.getElementById('ivrExten').value = ivr.extension;
        document.getElementById('ivrAudio').value = ivr.greeting_file || '';

        // Очищаем списки
        document.getElementById('ivrOptionsList').innerHTML = '';
        document.getElementById('ivrTimeoutType').value = 'hangup';
        document.getElementById('ivrTimeoutTarget').value = '';
        document.getElementById('ivrResult').textContent = '';

        // Восстанавливаем кнопки из JSON
        if (ivr.options) {
            for (const [digit, action] of Object.entries(ivr.options)) {
                if (digit === 't') {
                    document.getElementById('ivrTimeoutType').value = action.type;
                    if (action.type !== 'hangup') {
                        document.getElementById('ivrTimeoutTarget').value = action.target || '';
                    }
                } else if (digit !== 'i') {
                    addOptionRowWithValue(digit, action.type, action.target);
                }
            }
        }

        const submitBtn = document.getElementById('submitIvrBtn');
        submitBtn.textContent = 'Сохранить изменения';
        submitBtn.style.backgroundColor = '#ffc107';
        submitBtn.style.color = '#333';
        
        document.getElementById('cancelIvrEditBtn').style.display = 'inline-block';
        document.getElementById('ivrFormTitle').scrollIntoView({ behavior: 'smooth' });
    }

    function cancelEdit() {
        editingIvrId = null;
        document.getElementById('ivrForm').reset();
        document.getElementById('ivrOptionsList').innerHTML = '';
        document.getElementById('ivrFormTitle').textContent = 'Создать Голосовое Меню (IVR)';
        document.getElementById('ivrResult').textContent = '';
        
        const submitBtn = document.getElementById('submitIvrBtn');
        submitBtn.textContent = 'Сохранить IVR';
        submitBtn.style.backgroundColor = '#28a745';
        submitBtn.style.color = 'white';
        
        document.getElementById('cancelIvrEditBtn').style.display = 'none';
    }

    function addOptionRow() {
        addOptionRowWithValue('', 'extension', '');
    }

    function addOptionRowWithValue(digit, type, target) {
        const container = document.getElementById('ivrOptionsList');
        const row = document.createElement('div');
        row.style.marginBottom = '10px';
        row.className = 'ivr-option-row';
        row.innerHTML = `
            <input type="text" class="opt-digit" value="${digit}" placeholder="Кнопка (0-9, *, #)" style="width: 140px; margin-right: 5px; padding: 5px;" required>
            <select class="opt-type" style="padding: 5px; margin-right: 5px;">
                <option value="extension" ${type === 'extension' ? 'selected' : ''}>Вн. номер</option>
                <option value="group" ${type === 'group' ? 'selected' : ''}>Группа</option>
                <option value="ivr" ${type === 'ivr' ? 'selected' : ''}>Другое IVR</option>
            </select>
            <input type="text" class="opt-target" value="${target}" placeholder="Назначение (101, 600...)" style="width: 200px; margin-right: 5px; padding: 5px;" required>
            <button type="button" onclick="this.parentElement.remove()" style="background: #dc3545; color: white; border: none; cursor: pointer; padding: 5px 10px; border-radius: 3px;">X</button>
        `;
        container.appendChild(row);
    }

    function init() {
        const form = document.getElementById('ivrForm');
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const resultDiv = document.getElementById('ivrResult');
                
                const options = {};
                document.querySelectorAll('.ivr-option-row').forEach(row => {
                    const digit = row.querySelector('.opt-digit').value.trim();
                    const type = row.querySelector('.opt-type').value;
                    const target = row.querySelector('.opt-target').value.trim();
                    if (digit && (target || type === 'hangup')) {
                        options[digit] = { type, target };
                    }
                });

                const tType = document.getElementById('ivrTimeoutType').value;
                const tTarget = document.getElementById('ivrTimeoutTarget').value.trim();
                if (tType === 'hangup') {
                    options['t'] = { type: 'hangup', target: '' };
                } else if (tTarget !== '') {
                    options['t'] = { type: tType, target: tTarget };
                }

                const payload = {
                    name: document.getElementById('ivrName').value,
                    extension: parseInt(document.getElementById('ivrExten').value),
                    greeting_file: document.getElementById('ivrAudio').value || null,
                    options: options
                };

                try {
                    let res;
                    if (editingIvrId) {
                        res = await API.updateIvr(editingIvrId, payload);
                    } else {
                        res = await API.createIvr(payload);
                    }
                    
                    if (res.ok) {
                        resultDiv.style.color = 'green';
                        resultDiv.textContent = editingIvrId ? `Изменения сохранены!` : `Голосовое меню создано!`;
                        cancelEdit();
                        loadIvrs();
                    } else {
                        const data = await res.json();
                        resultDiv.style.color = 'red';
                        resultDiv.textContent = `Ошибка: ${data.detail || 'Сбой'}`;
                    }
                } catch (err) {
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = 'Ошибка сети';
                }
            });
        }
    }

    return { init, loadIvrs, deleteIvr, addOptionRow, startEditIvr, cancelEdit };
})();