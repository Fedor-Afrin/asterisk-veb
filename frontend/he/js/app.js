function switchTab(tabId, btn) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    btn.classList.add('active');
    
    AdminModule.stop();
    if (tabId === 'adminTab') {
        AdminModule.start();
    } else if (tabId === 'groupsTab') {
        GroupsModule.loadGroups();
    } else if (tabId === 'trunksTab') {
        TrunksModule.loadTrunksAndGroups();
    } else if (tabId === 'ivrTab') {
        IvrModule.loadIvrs();
    } else if (tabId === 'recordsTab') {
        RecordingsModule.open();
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
    AdminModule.init();
    RecordingsModule.init();

    // Загрузка начальных данных и запуск интервала
    ExtensionsModule.loadExtensions();
    setInterval(ExtensionsModule.loadExtensions, 5000);

    // Кнопка применения конфигурации (Reload PBX)
    document.getElementById('reloadPbxBtn').addEventListener('click', async () => {
        const resultDiv = document.getElementById('reloadResult');
        resultDiv.style.color = '#555';
        resultDiv.textContent = 'מחיל תצורה...';
        try {
            const response = await API.reloadPbx();
            const data = await response.json();
            if (response.ok) {
                resultDiv.style.color = 'green';
                resultDiv.textContent = data.message;
            } else {
                resultDiv.style.color = 'red';
                resultDiv.textContent = `שגיאה: ${data.detail || 'החלת התצורה נכשלה'}`;
            }
        } catch (err) {
            resultDiv.style.color = 'red';
            resultDiv.textContent = `שגיאת התחברות לשרת`;
        }
    });
});