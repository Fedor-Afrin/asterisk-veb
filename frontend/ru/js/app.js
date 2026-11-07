function switchTab(tabId, btn) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    btn.classList.add('active');
    
    if (tabId === 'groupsTab') {
        GroupsModule.loadGroups();
    } else if (tabId === 'trunksTab') {
        TrunksModule.loadTrunksAndGroups();
    } else if (tabId === 'ivrTab') {
        IvrModule.loadIvrs();
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Без входа приложение не запускаем: сначала форма пароля
    if (!(await Auth.init())) return;

    // Инициализация модулей
    ExtensionsModule.init();
    GroupsModule.init();
    TrunksModule.init();
    IvrModule.init(); // <--- ВОТ ЭТА СТРОКА ОЖИВЛЯЕТ ФОРМУ IVR

    // Загрузка начальных данных и запуск интервала
    ExtensionsModule.loadExtensions();
    setInterval(ExtensionsModule.loadExtensions, 5000);

    // Кнопка применения конфигурации (Reload PBX)
    document.getElementById('reloadPbxBtn').addEventListener('click', async () => {
        const resultDiv = document.getElementById('reloadResult');
        resultDiv.style.color = '#555';
        resultDiv.textContent = 'Применяю конфигурацию...';
        try {
            const response = await API.reloadPbx();
            const data = await response.json();
            if (response.ok) {
                resultDiv.style.color = 'green';
                resultDiv.textContent = data.message;
            } else {
                resultDiv.style.color = 'red';
                resultDiv.textContent = `Ошибка: ${data.detail || 'Не удалось применить конфигурацию'}`;
            }
        } catch (err) {
            resultDiv.style.color = 'red';
            resultDiv.textContent = `Ошибка соединения с сервером`;
        }
    });
});