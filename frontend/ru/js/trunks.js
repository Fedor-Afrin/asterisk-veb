const ТранкиModule = (() => {
    let editingTrunkId = null;
    let editingTrunkGroupId = null;
    let loadedТранки = [];
    let loadedTrunkGroups = [];

    async function loadТранкиAndGroups() {
        const container = document.getElementById('trunksContainer');
        const memberList = document.getElementById('trunkMemberList');
        const groupsContainer = document.getElementById('trunkGroupsContainer');
        
        try {
            const [trunks, groups] = await Promise.all([
                API.getТранки(),
                API.getTrunkGroups()
            ]);
            
            loadedТранки = trunks || [];
            loadedTrunkGroups = groups || [];

            // 1. Рендер Транков
            if (loadedТранки.length === 0) {
                container.innerHTML = '<p>No trunks have been created yet.</p>';
                if (memberList) memberList.innerHTML = '<p style="color: red;">Create trunks first.</p>';
            } else {
                let html = '<table style="width:100%; border-collapse: collapse; margin-top: 10px;">';
                html += '<tr style="background: #f1f1f1; text-align: left;"><th style="padding: 8px; border: 1px solid #ddd;">Name</th><th style="padding: 8px; border: 1px solid #ddd;">Protocol</th><th style="padding: 8px; border: 1px solid #ddd;">Host</th><th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Actions</th></tr>';
                
                let chkHtml = '';
                loadedТранки.forEach(t => {
                    html += `<tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${t.name}</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">${t.protocol.toUpperCase()}</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">${t.host}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                            <button onclick="ТранкиModule.startРедактироватьTrunk(${t.id})" style="background-color: #ffc107; color: #333; padding: 4px 8px; font-size: 12px; margin-right: 5px; border: none; cursor: pointer; border-radius: 3px;">Редактировать</button>
                            <button onclick="ТранкиModule.deleteTrunk(${t.id})" style="background-color: #dc3545; color: white; padding: 4px 8px; font-size: 12px; border: none; cursor: pointer; border-radius: 3px;">Удалить</button>
                        </td>
                    </tr>`;
                    
                    chkHtml += `<label style="display: block; margin-bottom: 5px; cursor: pointer;">
                        <input type="checkbox" name="tgMember" value="${t.id}"> 
                        <b>${t.name}</b> (${t.protocol.toUpperCase()} -> ${t.host})
                    </label>`;
                });
                html += '</table>';
                container.innerHTML = html;
                if (memberList && !editingTrunkGroupId) memberList.innerHTML = chkHtml;
            }

            // 2. Рендер Транковых Групп
            if (loadedTrunkGroups.length === 0) {
                groupsContainer.innerHTML = '<p>No trunk groups have been created yet.</p>';
            } else {
                const trunkMap = {};
                loadedТранки.forEach(t => trunkMap[t.id] = t.name);
                
                let gHtml = '<table style="width:100%; border-collapse: collapse; margin-top: 10px;">';
                gHtml += '<tr style="background: #f1f1f1; text-align: left;"><th style="padding: 8px; border: 1px solid #ddd;">Name</th><th style="padding: 8px; border: 1px solid #ddd;">Prefix</th><th style="padding: 8px; border: 1px solid #ddd;">Strategy</th><th style="padding: 8px; border: 1px solid #ddd;">Транки</th><th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Actions</th></tr>';
                
                loadedTrunkGroups.forEach(g => {
                    const trunkNames = (g.trunks || []).map(id => trunkMap[id]).filter(n => n !== undefined);
                    gHtml += `<tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${g.name}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; font-family: monospace; font-weight: bold; color: #007bff;">${g.prefix || '9'}</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">${g.strategy}</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">${trunkNames.join(', ')}</td>
                        <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                            <button onclick="ТранкиModule.startРедактироватьTrunkGroup(${g.id})" style="background-color: #ffc107; color: #333; padding: 4px 8px; font-size: 12px; margin-right: 5px; border: none; cursor: pointer; border-radius: 3px;">Редактировать</button>
                            <button onclick="ТранкиModule.deleteTrunkGroup(${g.id})" style="background-color: #dc3545; color: white; padding: 4px 8px; font-size: 12px; border: none; cursor: pointer; border-radius: 3px;">Удалить</button>
                        </td>
                    </tr>`;
                });
                gHtml += '</table>';
                groupsContainer.innerHTML = gHtml;
            }
        } catch (err) {
            container.innerHTML = '<p style="color: red;">Failed to load data.</p>';
        }
    }

    // --- Управление Транками ---
    function startРедактироватьTrunk(id) {
        const trunk = loadedТранки.find(t => t.id === id);
        if (!trunk) return;

        editingTrunkId = id;
        document.getElementById('trunkFormTitle').textContent = 'Редактироватьing Trunk: ' + trunk.name;
        document.getElementById('trunkName').value = trunk.name;
        document.getElementById('trunkProtocol').value = trunk.protocol;
        document.getElementById('trunkHost').value = trunk.host;
        document.getElementById('trunkUser').value = trunk.username || '';
        document.getElementById('trunkSecret').value = trunk.secret || '';

        const btn = document.getElementById('submitTrunkBtn');
        btn.textContent = 'Save Trunk';
        btn.style.backgroundColor = '#ffc107';
        btn.style.color = '#333';
        
        document.getElementById('cancelTrunkРедактироватьBtn').style.display = 'inline-block';
        document.getElementById('trunkResult').textContent = '';
        document.getElementById('trunkFormTitle').scrollIntoView({ behavior: 'smooth' });
    }

    function cancelРедактироватьTrunk() {
        editingTrunkId = null;
        document.getElementById('trunkForm').reset();
        document.getElementById('trunkFormTitle').textContent = 'Add Trunk (PJSIP / IAX2)';
        document.getElementById('trunkResult').textContent = '';
        
        const btn = document.getElementById('submitTrunkBtn');
        btn.textContent = 'Add Trunk';
        btn.style.backgroundColor = '#007bff';
        btn.style.color = 'white';
        document.getElementById('cancelTrunkРедактироватьBtn').style.display = 'none';
    }

    async function deleteTrunk(id) {
        if (!confirm('Удалить this trunk?')) return;
        try {
            await API.deleteTrunk(id);
            if (editingTrunkId === id) cancelРедактироватьTrunk();
            loadТранкиAndGroups();
        } catch (err) { alert('Failed to delete'); }
    }

    // --- Управление Транковыми Группами ---
    function startРедактироватьTrunkGroup(id) {
        const tg = loadedTrunkGroups.find(g => g.id === id);
        if (!tg) return;

        editingTrunkGroupId = id;
        document.getElementById('tgFormTitle').textContent = 'Редактироватьing Group: ' + tg.name;
        document.getElementById('tgName').value = tg.name;
        document.getElementById('tgPrefix').value = tg.prefix || '9';
        document.getElementById('tgStrategy').value = tg.strategy;

        // Восстанавливаем галочки
        let chkHtml = '';
        loadedТранки.forEach(t => {
            const isChecked = tg.trunks.includes(t.id) ? 'checked' : '';
            chkHtml += `<label style="display: block; margin-bottom: 5px; cursor: pointer;">
                <input type="checkbox" name="tgMember" value="${t.id}" ${isChecked}> 
                <b>${t.name}</b> (${t.protocol.toUpperCase()} -> ${t.host})
            </label>`;
        });
        document.getElementById('trunkMemberList').innerHTML = chkHtml;

        const btn = document.getElementById('submitTgBtn');
        btn.textContent = 'Сохранить изменения';
        btn.style.backgroundColor = '#ffc107';
        btn.style.color = '#333';
        
        document.getElementById('cancelTgРедактироватьBtn').style.display = 'inline-block';
        document.getElementById('tgResult').textContent = '';
        document.getElementById('tgFormTitle').scrollIntoView({ behavior: 'smooth' });
    }

    function cancelРедактироватьTrunkGroup() {
        editingTrunkGroupId = null;
        document.getElementById('trunkGroupForm').reset();
        document.getElementById('tgFormTitle').textContent = 'Create Trunk Group';
        document.getElementById('tgResult').textContent = '';
        
        const btn = document.getElementById('submitTgBtn');
        btn.textContent = 'Save Group';
        btn.style.backgroundColor = '#28a745';
        btn.style.color = 'white';
        document.getElementById('cancelTgРедактироватьBtn').style.display = 'none';
        
        // Перерисовываем список транков без галочек
        loadТранкиAndGroups();
    }

    async function deleteTrunkGroup(id) {
        if (!confirm('Удалить this trunk group?')) return;
        try {
            await API.deleteTrunkGroup(id);
            if (editingTrunkGroupId === id) cancelРедактироватьTrunkGroup();
            loadТранкиAndGroups();
        } catch (err) { alert('Failed to delete'); }
    }

    function init() {
        // Форма Транка
        const trunkForm = document.getElementById('trunkForm');
        if (trunkForm) {
            trunkForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const resultDiv = document.getElementById('trunkResult');
                const payload = {
                    name: document.getElementById('trunkName').value,
                    protocol: document.getElementById('trunkProtocol').value,
                    host: document.getElementById('trunkHost').value,
                    username: document.getElementById('trunkUser').value || null,
                    secret: document.getElementById('trunkSecret').value || null
                };
                
                try {
                    let res;
                    if (editingTrunkId) res = await API.updateTrunk(editingTrunkId, payload);
                    else res = await API.createTrunk(payload);

                    if (res.ok) {
                        resultDiv.style.color = 'green';
                        resultDiv.textContent = editingTrunkId ? 'Trunk updated!' : `Trunk ${payload.name} added!`;
                        cancelРедактироватьTrunk();
                        loadТранкиAndGroups();
                    } else {
                        const data = await res.json();
                        resultDiv.style.color = 'red';
                        resultDiv.textContent = `Error: ${data.detail || 'Request failed'}`;
                    }
                } catch (err) {
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = 'Network error';
                }
            });
        }

        // Форма Транковой Группы
        const trunkGroupForm = document.getElementById('trunkGroupForm');
        if (trunkGroupForm) {
            trunkGroupForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const resultDiv = document.getElementById('tgResult');
                
                const checkboxes = document.querySelectorAll('input[name="tgMember"]:checked');
                const trunks = Array.from(checkboxes).map(cb => parseInt(cb.value));
                if (trunks.length === 0) {
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = 'Select at least one trunk!';
                    return;
                }

                const payload = {
                    name: document.getElementById('tgName').value,
                    strategy: document.getElementById('tgStrategy').value,
                    prefix: document.getElementById('tgPrefix').value || "9",
                    trunks: trunks
                };

                try {
                    let res;
                    if (editingTrunkGroupId) res = await API.updateTrunkGroup(editingTrunkGroupId, payload);
                    else res = await API.createTrunkGroup(payload);

                    if (res.ok) {
                        resultDiv.style.color = 'green';
                        resultDiv.textContent = editingTrunkGroupId ? 'Group updated!' : `Group "${payload.name}" created!`;
                        cancelРедактироватьTrunkGroup();
                    } else {
                        const data = await res.json();
                        resultDiv.style.color = 'red';
                        resultDiv.textContent = `Error: ${data.detail || 'Request failed'}`;
                    }
                } catch (err) {
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = 'Network error';
                }
            });
        }
    }

    return { init, loadТранкиAndGroups, deleteTrunk, deleteTrunkGroup, startРедактироватьTrunk, cancelРедактироватьTrunk, startРедактироватьTrunkGroup, cancelРедактироватьTrunkGroup };
})();