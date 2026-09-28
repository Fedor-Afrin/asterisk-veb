const TrunksModule = (() => {
    async function loadTrunksAndGroups() {
        const container = document.getElementById('trunksContainer');
        const memberList = document.getElementById('trunkMemberList');
        const groupsContainer = document.getElementById('trunkGroupsContainer');

        try {
            const [trunks, groups] = await Promise.all([
                API.getTrunks(),
                API.getTrunkGroups()
            ]);

            // 1. Отображение списка транков
            if (!trunks || trunks.length === 0) {
                container.innerHTML = '<p>Транки пока не созданы.</p>';
                if (memberList) memberList.innerHTML = '<p style="color: red;">Сначала создайте хотя бы один транк.</p>';
            } else {
                let html = '<table style="width:100%; border-collapse: collapse; margin-top: 10px;">';
                html += '<tr style="background: #f1f1f1; text-align: left;"><th style="padding: 8px; border: 1px solid #ddd;">Имя</th><th style="padding: 8px; border: 1px solid #ddd;">Протокол</th><th style="padding: 8px; border: 1px solid #ddd;">Host</th><th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Действия</th></tr>';
                
                let chkHtml = '';
                trunks.forEach(t => {
                    html += `<tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${t.name}</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">${t.protocol.toUpperCase()}</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">${t.host}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: center;"><button onclick="TrunksModule.deleteTrunk(${t.id})" style="background-color: #dc3545; color: white; padding: 4px 8px; font-size: 12px;">Удалить</button></td>
                    </tr>`;

                    chkHtml += `<label style="display: block; margin-bottom: 5px; cursor: pointer;">
                        <input type="checkbox" name="tgMember" value="${t.id}"> 
                        <b>${t.name}</b> (${t.protocol.toUpperCase()} -> ${t.host})
                    </label>`;
                });
                html += '</table>';
                container.innerHTML = html;
                if (memberList) memberList.innerHTML = chkHtml;
            }

            // 2. Отображение транковых групп
            if (!groups || groups.length === 0) {
                groupsContainer.innerHTML = '<p>Транковые группы пока не созданы.</p>';
            } else {
                const trunkMap = {};
                trunks.forEach(t => trunkMap[t.id] = t.name);

                let gHtml = '<table style="width:100%; border-collapse: collapse; margin-top: 10px;">';
                gHtml += '<tr style="background: #f1f1f1; text-align: left;"><th style="padding: 8px; border: 1px solid #ddd;">Название</th><th style="padding: 8px; border: 1px solid #ddd;">Префикс</th><th style="padding: 8px; border: 1px solid #ddd;">Стратегия</th><th style="padding: 8px; border: 1px solid #ddd;">Состав транков</th><th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Действия</th></tr>';
                
                groups.forEach(g => {
                    const trunkNames = (g.trunks || []).map(id => trunkMap[id]).filter(n => n !== undefined);
                    gHtml += `<tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${g.name}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; font-family: monospace; font-weight: bold; color: #007bff;">${g.prefix || '9'}</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">${g.strategy}</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">${trunkNames.join(', ')}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: center;"><button onclick="TrunksModule.deleteTrunkGroup(${g.id})" style="background-color: #dc3545; color: white; padding: 4px 8px; font-size: 12px;">Удалить</button></td>
                    </tr>`;
                });
                gHtml += '</table>';
                groupsContainer.innerHTML = gHtml;
            }

        } catch (err) {
            console.error(err);
            container.innerHTML = '<p style="color: red;">Ошибка загрузки транков.</p>';
        }
    }

    async function deleteTrunk(id) {
        if (!confirm('Удалить этот транк?')) return;
        await API.deleteTrunk(id);
        loadTrunksAndGroups();
    }

    async function deleteTrunkGroup(id) {
        if (!confirm('Удалить эту транковую группу?')) return;
        await API.deleteTrunkGroup(id);
        loadTrunksAndGroups();
    }

    function init() {
 // Форма создания транковой группы
        const trunkGroupForm = document.getElementById('trunkGroupForm');
        if (trunkGroupForm) {
            trunkGroupForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const name = document.getElementById('tgName').value;
                const strategy = document.getElementById('tgStrategy').value;
                
                // СЧИТЫВАЕМ ПРЕФИКС ИЗ ПОЛЯ ВВОДА
                const prefixInput = document.getElementById('tgPrefix');
                const prefix = prefixInput ? prefixInput.value : "9";
                
                const checkboxes = document.querySelectorAll('input[name="tgMember"]:checked');
                const trunks = Array.from(checkboxes).map(cb => parseInt(cb.value));
                const resultDiv = document.getElementById('tgResult');

                if (trunks.length === 0) {
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = 'Выберите хотя бы один транк!';
                    return;
                }

                try {
                    // ПЕРЕДАЕМ ПРЕФИКС НА СЕРВЕР
                    const res = await API.createTrunkGroup({ name, strategy, prefix, trunks });
                    if (res.ok) {
                        resultDiv.style.color = 'green';
                        resultDiv.textContent = `Транковая группа "${name}" создана!`;
                        trunkGroupForm.reset();
                        // Возвращаем дефолтное значение префикса после сброса формы, если нужно
                        if (prefixInput) prefixInput.value = "9";
                        loadTrunksAndGroups();
                    } else {
                        const data = await res.json();
                        resultDiv.style.color = 'red';
                        resultDiv.textContent = `Ошибка: ${data.detail || 'Не удалось создать'}`;
                    }
                } catch (err) { resultDiv.style.color = 'red'; resultDiv.textContent = 'Ошибка сети'; }
            });
        }

        // Форма создания транковой группы
        const trunkGroupForm = document.getElementById('trunkGroupForm');
        if (trunkGroupForm) {
            trunkGroupForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const name = document.getElementById('tgName').value;
                const strategy = document.getElementById('tgStrategy').value;
                const prefixInput = document.getElementById('tgPrefix');
                const prefix = prefixInput ? prefixInput.value : "9";
                
                const checkboxes = document.querySelectorAll('input[name="tgMember"]:checked');
                const trunks = Array.from(checkboxes).map(cb => parseInt(cb.value));
                const resultDiv = document.getElementById('tgResult');

                if (trunks.length === 0) {
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = 'Выберите хотя бы один транк!';
                    return;
                }

                try {
                    const res = await API.createTrunkGroup({ name, strategy, prefix, trunks });
                    if (res.ok) {
                        resultDiv.style.color = 'green';
                        resultDiv.textContent = `Транковая группа "${name}" создана!`;
                        trunkGroupForm.reset();
                        loadTrunksAndGroups();
                    } else {
                        const data = await res.json();
                        resultDiv.style.color = 'red';
                        resultDiv.textContent = `Ошибка: ${data.detail || 'Не удалось создать'}`;
                    }
                } catch (err) { resultDiv.style.color = 'red'; resultDiv.textContent = 'Ошибка сети'; }
            });
        }
    }

    return { init, loadTrunksAndGroups, deleteTrunk, deleteTrunkGroup };
})();