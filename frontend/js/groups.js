const GroupsModule = (() => {
    let editingGroupId = null;

    async function loadGroups() {
        const container = document.getElementById('groupsContainer');
        const membersList = document.getElementById('membersList');
        
        try {
            const [extensions, groups] = await Promise.all([
                API.getExtensions(),
                API.getGroups()
            ]);
            
            const extMap = {};
            extensions.forEach(e => extMap[e.id] = e.extension);

            if (extensions.length === 0) {
                membersList.innerHTML = '<p style="color: red;">Сначала создайте телефонные номера во вкладке "Номера".</p>';
            } else {
                let chkHtml = '';
                extensions.forEach(ext => {
                    chkHtml += `<label style="display: block; margin-bottom: 5px; cursor: pointer;">
                        <input type="checkbox" name="groupMember" value="${ext.id}"> 
                        <b>${ext.extension}</b> (${ext.callerid})
                    </label>`;
                });
                membersList.innerHTML = chkHtml;
            }

            if (groups.length === 0) {
                container.innerHTML = '<p>Группы пока не созданы.</p>';
                return;
            }

            let html = '<table style="width:100%; border-collapse: collapse; margin-top: 10px;">';
            html += '<tr style="background: #f1f1f1; text-align: left;">';
            html += '<th style="padding: 8px; border: 1px solid #ddd;">Название</th>';
            html += '<th style="padding: 8px; border: 1px solid #ddd;">Стратегия</th>';
            html += '<th style="padding: 8px; border: 1px solid #ddd;">Участники</th>';
            html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Действия</th>';
            html += '</tr>';
            
            groups.forEach(g => {
                const realNumbers = g.members.map(id => extMap[id]).filter(num => num !== undefined);
                const membersStr = g.members.join(',');

                html += `<tr>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${g.name}</td>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd;">${g.strategy}</td>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd;">${realNumbers.join(', ')}</td>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                    <button onclick="GroupsModule.startEditGroup(${g.id}, '${g.name}', '${g.strategy}', '${membersStr}')" style="background-color: #ffc107; color: #333; padding: 4px 8px; font-size: 12px; margin-right: 5px;">Ред.</button>
                    <button onclick="GroupsModule.deleteGroup(${g.id})" style="background-color: #dc3545; color: white; padding: 4px 8px; font-size: 12px;">Удалить</button>
                </td>`;
                html += `</tr>`;
            });
            html += '</table>';
            container.innerHTML = html;

        } catch (err) {
            container.innerHTML = '<p style="color: red;">Ошибка загрузки списка групп.</p>';
            membersList.innerHTML = '<p style="color: red;">Ошибка загрузки номеров.</p>';
        }
    }

    async function deleteGroup(id) {
        if (!confirm('Вы уверены, что хотите удалить эту группу?')) return;
        try {
            const response = await API.deleteGroup(id);
            if (response.ok) {
                if (editingGroupId === id) cancelEdit();
                loadGroups();
            } else {
                alert('Не удалось удалить группу');
            }
        } catch (err) { alert('Ошибка соединения с сервером'); }
    }

    function startEditGroup(id, name, strategy, membersStr) {
        editingGroupId = id;
        document.getElementById('groupFormTitle').textContent = 'Редактировать группу';
        document.getElementById('groupName').value = name;
        document.getElementById('groupStrategy').value = strategy;
        
        const submitBtn = document.getElementById('submitGroupBtn');
        submitBtn.textContent = 'Сохранить изменения';
        submitBtn.style.backgroundColor = '#ffc107';
        submitBtn.style.color = '#333';
        
        document.getElementById('cancelEditBtn').style.display = 'inline-block';
        document.getElementById('groupResult').textContent = '';

        const membersArray = membersStr.split(',').map(Number);
        document.querySelectorAll('input[name="groupMember"]').forEach(cb => {
            cb.checked = membersArray.includes(parseInt(cb.value));
        });

        document.getElementById('groupFormTitle').scrollIntoView({ behavior: 'smooth' });
    }

    function cancelEdit() {
        editingGroupId = null;
        document.getElementById('groupForm').reset();
        document.getElementById('groupFormTitle').textContent = 'Создать группу вызовов';
        
        const submitBtn = document.getElementById('submitGroupBtn');
        submitBtn.textContent = 'Создать группу';
        submitBtn.style.backgroundColor = '#28a745';
        submitBtn.style.color = 'white';
        
        document.getElementById('cancelEditBtn').style.display = 'none';
        document.getElementById('groupResult').textContent = '';
    }

    function init() {
        document.getElementById('groupForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const resultDiv = document.getElementById('groupResult');
            const name = document.getElementById('groupName').value;
            const strategy = document.getElementById('groupStrategy').value;
            
            const checkboxes = document.querySelectorAll('input[name="groupMember"]:checked');
            const members = Array.from(checkboxes).map(cb => parseInt(cb.value));

            if (members.length === 0) {
                resultDiv.style.color = 'red';
                resultDiv.textContent = 'Выберите хотя бы одного участника!';
                return;
            }

            try {
                let response;
                if (editingGroupId) {
                    response = await API.updateGroup(editingGroupId, { name, strategy, members });
                } else {
                    response = await API.createGroup({ name, strategy, members });
                }
                
                if (response.ok) {
                    resultDiv.style.color = 'green';
                    resultDiv.textContent = editingGroupId ? `Группа "${name}" обновлена!` : `Группа "${name}" успешно создана!`;
                    cancelEdit();
                    loadGroups();
                } else {
                    const data = await response.json();
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = `Ошибка: ${data.detail || 'Не удалось сохранить группу'}`;
                }
            } catch (err) {
                resultDiv.style.color = 'red';
                resultDiv.textContent = `Ошибка соединения с сервером`;
            }
        });

        document.getElementById('loadGroupsBtn').addEventListener('click', loadGroups);
    }

    return { init, loadGroups, deleteGroup, startEditGroup, cancelEdit };
})();