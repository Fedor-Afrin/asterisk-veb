const שלוחותModule = (() => {
    let editingExtId = null;
    let loadedשלוחות = [];

    function generatePassword(length = 12) {
        const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*";
        return Array.from({length}, () => charset[Math.floor(Math.random() * charset.length)]).join('');
    }

    // Восстановленные и улучшенные цветные лампочки
    function renderStatusBadge(statusText) {
        const lamp = (color) => `<span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: ${color}; margin-right: 6px; box-shadow: 0 0 5px ${color};"></span>`;
        
        if (!statusText) return lamp('#adb5bd') + '<span style="color: gray;">Unknown</span>';
        if (statusText.includes('Not in use')) return lamp('#28a745') + '<span style="color: #28a745; font-weight: bold;">Available</span>';
        if (statusText.includes('In use') || statusText.includes('Ringing')) return lamp('#dc3545') + '<span style="color: #dc3545; font-weight: bold;">Busy</span>';
        if (statusText.includes('Unavailable')) return lamp('#6c757d') + '<span style="color: #6c757d;">Unavailable</span>';
        return lamp('#adb5bd') + `<span style="color: #333;">${statusText}</span>`;
    }

    async function loadשלוחות() {
        const container = document.getElementById('extensionsContainer');
        try {
            const [extensions, statusData] = await Promise.all([
                API.getשלוחות(),
                API.getStatus()
            ]);
            
            loadedשלוחות = extensions;
            const statuses = statusData.statuses || {};
            
            if (extensions.length === 0) {
                container.innerHTML = '<p>No extensions have been created yet.</p>';
                return;
            }
            
            let html = '<table style="width:100%; border-collapse: collapse; margin-top: 10px;">';
            html += '<tr style="background: #f1f1f1; text-align: left;"><th style="padding: 8px; border: 1px solid #ddd;">Extension</th><th style="padding: 8px; border: 1px solid #ddd;">Caller ID</th><th style="padding: 8px; border: 1px solid #ddd;">Status</th><th style="padding: 8px; border: 1px solid #ddd;">Транспорт</th><th style="padding: 8px; border: 1px solid #ddd;">Пароль</th><th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Actions</th></tr>';
            
            extensions.forEach(ext => {
                const currentStatus = statuses[String(ext.extension)] || '';
                html += `<tr>
                    <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${ext.extension}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">${ext.callerid}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; vertical-align: middle;">${renderStatusBadge(currentStatus)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd;">UDP</td>
                    <td style="padding: 8px; border: 1px solid #ddd; vertical-align: middle;">
                        <span class="secret-text" data-secret="${ext.secret}" style="font-family: monospace; display: inline-block; min-width: 75px;">••••••••</span> 
                        <button onclick="שלוחותModule.toggleSecret(this)" style="padding: 0; font-size: 16px; margin-left: 5px; background: transparent; border: none; cursor: pointer; vertical-align: middle;" title="Show/Hide Password">👁️</button>
                    </td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                        <button onclick="שלוחותModule.startערוךExtension(${ext.id})" style="background-color: #ffc107; color: #333; padding: 4px 8px; margin-right: 5px; font-size: 12px; border: none; border-radius: 3px; cursor: pointer;">ערוך</button>
                        <button onclick="שלוחותModule.deleteExtension(${ext.id})" style="background-color: #dc3545; color: white; padding: 4px 8px; font-size: 12px; border: none; border-radius: 3px; cursor: pointer;">מחק</button>
                    </td>
                </tr>`;
            });
            html += '</table>';
            container.innerHTML = html;
        } catch (err) { container.innerHTML = '<p style="color: red;">Failed to load extensions.</p>'; }
    }

    // Восстановленный "Глазик"
    function toggleSecret(btn) {
        const span = btn.previousElementSibling;
        const currentSecret = span.getAttribute('data-secret');
        if (span.textContent === '••••••••') {
            span.textContent = currentSecret;
            btn.textContent = '🙈'; // Иконка закрытого глаза
        } else {
            span.textContent = '••••••••';
            btn.textContent = '👁️'; // Иконка открытого глаза
        }
    }

    async function deleteExtension(id) {
        if (!confirm('Are you sure you want to delete this extension?')) return;
        try {
            const response = await API.deleteExtension(id);
            if (response.ok) {
                if (editingExtId === id) cancelערוך();
                loadשלוחות();
            } else alert('Failed to delete');
        } catch (err) { alert('Network error'); }
    }

    function startערוךExtension(id) {
        const ext = loadedשלוחות.find(e => e.id === id);
        if (!ext) return;

        editingExtId = id;
        document.getElementById('extFormTitle').textContent = 'ערוךing Extension: ' + ext.extension;
        document.getElementById('extNumber').value = ext.extension;
        document.getElementById('extSecret').value = ext.secret;
        document.getElementById('extCallerId').value = ext.callerid;

        const submitBtn = document.getElementById('submitExtBtn');
        submitBtn.textContent = 'שמור שינויים';
        submitBtn.style.backgroundColor = '#ffc107';
        submitBtn.style.color = '#333';
        
        document.getElementById('cancelExtערוךBtn').style.display = 'inline-block';
        document.getElementById('extResult').textContent = '';
        document.getElementById('extFormTitle').scrollIntoView({ behavior: 'smooth' });
    }

    function cancelערוך() {
        editingExtId = null;
        document.getElementById('extForm').reset();
        document.getElementById('extFormTitle').textContent = 'Create SIP Extension';
        document.getElementById('extResult').textContent = '';
        
        const submitBtn = document.getElementById('submitExtBtn');
        submitBtn.textContent = 'Create Extension';
        submitBtn.style.backgroundColor = '#007bff';
        submitBtn.style.color = 'white';
        
        document.getElementById('cancelExtערוךBtn').style.display = 'none';
    }

    function init() {
        document.getElementById('generateBtn').addEventListener('click', () => {
            document.getElementById('extSecret').value = generatePassword(12);
        });

        document.getElementById('extForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const resultDiv = document.getElementById('extResult');
            const payload = {
                extension: parseInt(document.getElementById('extNumber').value),
                secret: document.getElementById('extSecret').value,
                callerid: document.getElementById('extCallerId').value
            };

            try {
                let response;
                if (editingExtId) {
                    response = await API.updateExtension(editingExtId, payload);
                } else {
                    response = await API.createExtension(payload);
                }

                if (response.ok) {
                    resultDiv.style.color = 'green';
                    resultDiv.textContent = editingExtId ? `Changes saved!` : `Extension created successfully!`;
                    cancelערוך();
                    loadשלוחות();
                } else {
                    const data = await response.json();
                    resultDiv.style.color = 'red';
                    resultDiv.textContent = `Error: ${data.detail || 'Request failed'}`;
                }
            } catch (err) {
                resultDiv.style.color = 'red';
                resultDiv.textContent = 'Network error';
            }
        });

        document.getElementById('loadExtsBtn').addEventListener('click', loadשלוחות);
    }

    return { init, loadשלוחות, toggleSecret, deleteExtension, startערוךExtension, cancelערוך };
})();