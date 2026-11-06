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
                membersList.innerHTML = '<p style="color: red;">יש ליצור שלוחות בלשונית «שלוחות» קודם.</p>';
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
                container.innerHTML = '<p>עדיין לא נוצרו קבוצות שיחה.</p>';
                return;
            }

            let html = '<table style="width:100%; border-collapse: collapse; margin-top: 10px;">';
            html += '<tr style="background: #f1f1f1; text-align: right;">';
            html += '<th style="padding: 8px; border: 1px solid #ddd;">שם</th>';
            html += '<th style="padding: 8px; border: 1px solid #ddd;">שלוחה</th>'; // ДОБАВЛЕНО: Колонка номера
            html += '<th style="padding: 8px; border: 1px solid #ddd;">אסטרטגיה</th>';
            html += '<th style="padding: 8px; border: 1px solid #ddd;">חברים</th>';
            html += '<th style="padding: 8px; border: 1px solid #ddd; text-align: center;">פעולות</th>';
            html += '</tr>';
            
            groups.forEach(g => {
                const realNumbers = g.members.map(id => extMap[id]).filter(num => num !== undefined);
                const membersStr = g.members.join(',');

                html += `<tr>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${g.name}</td>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd; color: #007bff; font-weight: bold;">${g.exten || 'לא הוגדר'}</td>`; // ДОБАВЛЕНО: Вывод номера
                html += `<td style="padding: 8px; border: 1px solid #ddd;">${g.strategy}</td>`;
                html += `<td style="padding: 8px; border: 1px solid #ddd;">${realNumbers.join(', ')}</td>`;
                // ДОБАВЛЕНО: Передача g.exten в функцию редактирования
                html += `<td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                    <button onclick="GroupsModule.startEditGroup(${g.id}, '${g.name}', '${g.exten || ''}', '${g.strategy}', '${membersStr}')" style="background-color: #ffc107; color: #333; padding: 4px 8px; font-size: 12px; margin-left: 5px;">עריכה</button>
                    <button onclick="GroupsModule.deleteGroup(${g.id})" style="background-color: #dc3545; color: white; padding: 4px 8px; font-size: 12px;">מחיקה</button>
                </td>`;
                html += `</tr>`;
            });
            html += '</table>';
            container.innerHTML = html;

        } catch (err) {
            container.innerHTML = '<p style="color: red;">טעינת קבוצות השיחה נכשלה.</p>';
            membersList.innerHTML = '<p style="color: red;">טעינת השלוחות נכשלה.</p>';
        }
    }

    async function deleteGroup(id) {
        if (!confirm('האם למחוק קבוצה זו?')) return;
        try {
            const response = await API.deleteGroup(id);
            if (response.ok) {
                if (editingGroupId === id) cancelEdit();
                loadGroups();
            } else {
                alert('מחיקת הקבוצה נכשלה');
            }
        } catch (err) { alert('שגיאת התחברות לשרת'); }
    }

    // ДОБАВЛЕНО: параметр exten
    function startEditGroup(id, name, exten, strategy, membersStr) {
        editingGroupId = id;
        document.getElementById('groupFormTitle').textContent = 'עריכת קבוצה';
        document.getElementById('groupName').value = name;
        document.getElementById('groupExten').value = exten; // ДОБАВЛЕНО: заполнение поля номера
        document.getElementById('groupStrategy').value = strategy;
        
        const submitBtn = document.getElementById('submitGroupBtn');
        submitBtn.textContent = 'שמירת שינויים';
        submitBtn.style.backgroundColor = '#ffc107';
        submitBtn.style.color = '#333';
        
        document.getElementById('cancelEditBtn').style.display = 'inline-block';
        document.getElementById('groupResult').textContent = '';

        // ДОБАВЛЕНО: безопасный сплит (чтобы не падало, если участников 0)
        const membersArray = membersStr ? membersStr.split(',').map(Number) : [];
        document.querySelectorAll('input[name="groupMember"]').forEach(cb => {
            cb.checked = membersArray.includes(parseInt(cb.value));
        });

        document.getElementById('groupFormTitle').scrollIntoView({ behavior: 'smooth' });
    }

    function cancelEdit() {
        editingGroupId = null;
        document.getElementById('groupForm').reset();
        document.getElementById('groupFormTitle').textContent = 'יצירת קבוצת שיחה';
        
        const submitBtn = document.getElementById('submitGroupBtn');
        submitBtn.textContent = 'יצירת קבוצה';
        submitBtn.style.backgroundColor = '#28a745';
        submitBtn.style.color = 'white';
        
        document.getElementById('cancelEditBtn').style.display = 'none';
        document.getElementById('groupResult').textContent = '';
    }

    function init() {
        const form = document.getElementById('groupForm');
        if (form) {
            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                const resultDiv = document.getElementById('groupResult');
                const name = document.getElementById('groupName').value;
                const exten = parseInt(document.getElementById('groupExten').value); // ДОБАВЛЕНО: Чтение номера из поля
                const strategy = document.getElementById('groupStrategy').value;
                
                const checkboxes = document.querySelectorAll('input[name="groupMember"]:checked');
                const members = Array.from(checkboxes).map(cb => parseInt(cb.value));

                if (members.length === 0) {
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = 'יש לבחור לפחות חבר אחד!';
                    return;
                }

                try {
                    let response;
                    if (editingGroupId) {
                        // ДОБАВЛЕНО: передача exten в API
                        response = await API.updateGroup(editingGroupId, { name, exten, strategy, members });
                    } else {
                        // ДОБАВЛЕНО: передача exten в API
                        response = await API.createGroup({ name, exten, strategy, members });
                    }
                    
                    if (response.ok) {
                        resultDiv.style.color = 'green';
                        resultDiv.textContent = editingGroupId ? `הקבוצה "${name}" עודכנה!` : `הקבוצה "${name}" נוצרה בהצלחה!`;
                        cancelEdit();
                        loadGroups();
                    } else {
                        const data = await response.json();
                        resultDiv.style.color = 'red';
                        
                        // ДОБАВЛЕНО: Корректный разбор ошибки от Pydantic (защита от [object Object])
                        if (data.detail && Array.isArray(data.detail)) {
                            resultDiv.textContent = `שגיאת אימות: ${data.detail[0].msg}`;
                        } else {
                            resultDiv.textContent = `שגיאה: ${data.detail || 'שמירת הקבוצה נכשלה'}`;
                        }
                    }
                } catch (err) {
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = `שגיאת התחברות לשרת`;
                }
            });
        }

        const loadBtn = document.getElementById('loadGroupsBtn');
        if (loadBtn) {
            loadBtn.addEventListener('click', loadGroups);
        }
    }

    return { init, loadGroups, deleteGroup, startEditGroup, cancelEdit };
})();