// Вход в веб-интерфейс: первый запуск (создать пароль) и обычный вход.
const Auth = (() => {
    const TEXT = {
        signIn: 'Вход',
        setupTitle: 'Создайте пароль администратора',
        setupHint: 'Первый запуск. Создайте пароль администратора. Минимум 8 символов.',
        loginHint: 'Введите пароль администратора.',
        createPassword: 'Создать пароль',
        tooShort: 'Пароль должен содержать не менее 8 символов',
        mismatch: 'Пароли не совпадают',
        wrongPassword: 'Неверный пароль',
        tooMany: 'Слишком много попыток, повторите через минуту',
        alreadySet: 'Пароль уже задан. Выполните вход.',
        connectionError: 'Ошибка соединения с сервером'
    };

    const nativeFetch = window.fetch.bind(window);
    let mode = null; // 'setup' | 'login'

    const el = (id) => document.getElementById(id);

    function show(newMode) {
        mode = newMode;
        document.body.classList.add('auth-locked');
        el('authOverlay').style.display = 'flex';
        el('logoutRow').style.display = 'none';
        el('authResult').textContent = '';
        el('authPassword').value = '';
        el('authPassword2').value = '';
        const setup = newMode === 'setup';
        el('authTitle').textContent = setup ? TEXT.setupTitle : TEXT.signIn;
        el('authHint').textContent = setup ? TEXT.setupHint : TEXT.loginHint;
        el('authSubmit').textContent = setup ? TEXT.createPassword : TEXT.signIn;
        el('authPassword').autocomplete = setup ? 'new-password' : 'current-password';
        el('authPassword2').style.display = setup ? 'block' : 'none';
        el('authPassword2').required = setup;
        el('authPassword').focus();
    }

    function hide() {
        mode = null;
        document.body.classList.remove('auth-locked');
        el('authOverlay').style.display = 'none';
        el('logoutRow').style.display = 'flex';
    }

    // Любой ответ 401 от API (например, сессия истекла) снова показывает форму входа
    window.fetch = async (...args) => {
        const res = await nativeFetch(...args);
        const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url) || '';
        if (res.status === 401 && url.startsWith('/api/') && !url.startsWith('/api/auth/') && mode === null) {
            show('login');
        }
        return res;
    };

    async function submit(e) {
        e.preventDefault();
        const result = el('authResult');
        const password = el('authPassword').value;
        result.textContent = '';

        if (mode === 'setup') {
            if (password.length < 8) { result.textContent = TEXT.tooShort; return; }
            if (password !== el('authPassword2').value) { result.textContent = TEXT.mismatch; return; }
        }

        try {
            const res = await nativeFetch(mode === 'setup' ? '/api/auth/setup' : '/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            if (res.ok) { location.reload(); return; }
            if (res.status === 401) result.textContent = TEXT.wrongPassword;
            else if (res.status === 429) result.textContent = TEXT.tooMany;
            else if (res.status === 409) { show('login'); el('authResult').textContent = TEXT.alreadySet; }
            else {
                const data = await res.json().catch(() => ({}));
                result.textContent = typeof data.detail === 'string' ? data.detail : TEXT.connectionError;
            }
        } catch (err) {
            result.textContent = TEXT.connectionError;
        }
    }

    // true - можно работать; false - показана форма, приложение не запускаем
    async function init() {
        el('authForm').addEventListener('submit', submit);
        el('logoutBtn').addEventListener('click', async () => {
            try { await nativeFetch('/api/auth/logout', { method: 'POST' }); } catch (err) {}
            location.reload();
        });
        try {
            const res = await nativeFetch('/api/auth/status');
            const state = await res.json();
            if (!state.configured) { show('setup'); return false; }
            if (!state.authenticated) { show('login'); return false; }
            hide();
            return true;
        } catch (err) {
            show('login');
            el('authResult').textContent = TEXT.connectionError;
            return false;
        }
    }

    return { init };
})();
