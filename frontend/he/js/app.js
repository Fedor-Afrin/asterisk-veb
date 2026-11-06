function switchTab(tabId, btn) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    btn.classList.add('active');
    
    if (tabId === 'groupsTab') {
        GroupsModule.loadGroups();
    } else if (tabId === 'trunksTab') {
        קווים (Trunks)Module.loadקווים (Trunks)AndGroups();
    } else if (tabId === 'ivrTab') {
        IvrModule.loadIvrs();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Инициализация модулей
    שלוחותModule.init();
    GroupsModule.init();
    קווים (Trunks)Module.init();
    IvrModule.init(); // <--- ВОТ ЭТА СТРОКА ОЖИВЛЯЕТ ФОРМУ IVR

    // Загрузка начальных данных и запуск интервала
    שלוחותModule.loadשלוחות();
    setInterval(שלוחותModule.loadשלוחות, 5000);

    // Кнопка применения конфигурации (Reload PBX)
    document.getElementById('reloadPbxBtn').addEventListener('click', async () => {
        const resultDiv = document.getElementById('reloadResult');
        resultDiv.style.color = '#555';
        resultDiv.textContent = 'Applying configuration...';
        try {
            const response = await API.reloadPbx();
            const data = await response.json();
            if (response.ok) {
                resultDiv.style.color = 'green';
                resultDiv.textContent = data.message;
            } else {
                resultDiv.style.color = 'red';
                resultDiv.textContent = `Error: ${data.detail || 'Failed to apply configuration'}`;
            }
        } catch (err) {
            resultDiv.style.color = 'red';
            resultDiv.textContent = `Server connection error`;
        }
    });
});