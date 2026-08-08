function switchTab(tabId, btn) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    btn.classList.add('active');
    
    if(tabId === 'groupsTab') {
        GroupsModule.loadGroups();
    } else if(tabId === 'trunksTab') {
        TrunksModule.loadTrunksAndGroups();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Инициализация модулей
    ExtensionsModule.init();
    GroupsModule.init();
    TrunksModule.init();

    // Загрузка начальных данных и запуск интервала
    ExtensionsModule.loadExtensions();
    setInterval(ExtensionsModule.loadExtensions, 5000);

    // Кнопка применения конфигурации (Reload PBX)
    document.getElementById('reloadPbxBtn').addEventListener('click', async () => {
        const resultDiv = document.getElementById('reloadResult');
        resultDiv.style.color = '#555';
        resultDiv.textContent = 'Применение конфигурации...';
        try {
            const response = await API.reloadPbx();
            const data = await response.json();
            if (response.ok) {
                resultDiv.style.color = 'green';
                resultDiv.textContent = data.message;
            } else {
                resultDiv.style.color = 'red';
                resultDiv.textContent = `Ошибка: ${data.detail || 'Не удалось применить'}`;
            }
        } catch (err) {
            resultDiv.style.color = 'red';
            resultDiv.textContent = `Ошибка соединения с сервером`;
        }
    });
});