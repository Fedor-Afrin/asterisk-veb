#!/usr/bin/env python3
"""
apply_languages.py - делает frontend/ru настоящим русским, frontend/he - ивритом (RTL).

Запуск из корня репозитория:   python3 apply_languages.py
Источник правды - frontend/en. Скрипт можно запускать сколько угодно раз:
ru и he каждый раз пересобираются из en заново.
"""
import os, re, sys

ROOT = os.path.join(os.getcwd(), "frontend")
FILES = ["index.html", "style.css", "js/api.js", "js/app.js", "js/extensions.js",
         "js/groups.js", "js/ivr.js", "js/trunks.js", "js/auth.js", "js/admin.js", "js/recordings.js"]

# Остатки русских слов в английской версии
EN_FIX = {
    "js/extensions.js": [(">Транспорт<", ">Transport<"), (">Пароль<", ">Password<")],
    "js/trunks.js":     [(">Транки<", ">Trunks<")],
}

# (английский, русский, иврит). Заменяется только строка целиком между разделителями
# (кавычки, обратные кавычки, > и <), поэтому код не ломается.
T = [
 ("Asterisk Admin Panel", "Панель администрирования Asterisk", "לוח ניהול Asterisk"),
 ("Asterisk PBX Administration", "Администрирование АТС Asterisk", "ניהול מרכזיית Asterisk"),
 ("PBX Management", "Управление АТС", "ניהול המרכזייה"),
 ("After adding or deleting extensions and groups, apply the changes to Asterisk.",
  "После добавления или удаления номеров и групп примените изменения в Asterisk.",
  "לאחר הוספה או מחיקה של שלוחות וקבוצות, יש להחיל את השינויים ב-Asterisk."),
 ("Apply Configuration", "Применить конфигурацию", "החלת תצורה"),
 ("Applying configuration...", "Применяю конфигурацию...", "מחיל תצורה..."),
 ("Failed to apply configuration", "Не удалось применить конфигурацию", "החלת התצורה נכשלה"),
 ("Extensions", "Номера", "שלוחות"),
 ("Call Groups", "Группы вызова", "קבוצות שיחה"),
 ("Trunks", "Транки", "טראנקים"),
 ("IVR Menus", "IVR-меню", "תפריטי IVR"),
 ("Call Recordings", "Записи разговоров", "הקלטות שיחות"),
 ("Create SIP Extension", "Создать SIP-номер", "יצירת שלוחת SIP"),
 ("Extension (e.g. 101)", "Номер (например, 101)", "שלוחה (לדוגמה: 101)"),
 ("Password (minimum 6 characters)", "Пароль (минимум 6 символов)", "סיסמה (לפחות 6 תווים)"),
 ("Generate", "Сгенерировать", "יצירה"),
 ("Caller ID (e.g. Office Phone <101>)", "Caller ID (например, Office Phone <101>)", "מזהה מתקשר (לדוגמה: Office Phone <101>)"),
 ("SIP Transport: UDP (port 5060)", "SIP-транспорт: UDP (порт 5060)", "העברת SIP: UDP (פורט 5060)"),
 ("Create Extension", "Создать номер", "יצירת שלוחה"),
 ("Cancel", "Отмена", "ביטול"),
 ("Configured Extensions", "Настроенные номера", "שלוחות מוגדרות"),
 ("Refresh List", "Обновить список", "רענון רשימה"),
 ("Loading list...", "Загрузка списка...", "טוען רשימה..."),
 ("Create Call Group", "Создать группу вызова", "יצירת קבוצת שיחה"),
 ("Group Name (e.g. Sales)", "Название группы (например, Продажи)", "שם קבוצה (לדוגמה: מכירות)"),
 ("Group Number (e.g. 600)", "Номер группы (например, 600)", "מספר קבוצה (לדוגמה: 600)"),
 ("Ring Strategy:", "Стратегия вызова:", "אסטרטגיית צלצול:"),
 ("Ring All (all extensions ring simultaneously)", "Звонить всем (все номера звонят одновременно)", "צלצול לכולם (כל השלוחות מצלצלות בו-זמנית)"),
 ("Hunt (ring extensions sequentially)", "Последовательно (номера звонят по очереди)", "חיפוש (צלצול לשלוחות לפי הסדר)"),
 ("Round Robin (distribute calls in rotation)", "По кругу (вызовы распределяются по очереди)", "סבב (חלוקת שיחות לסירוגין)"),
 ("Pickup Group (call pickup group)", "Группа перехвата (перехват вызова)", "קבוצת תפיסה (תפיסת שיחה)"),
 ("Boss Group (executive and assistant)", "Группа «руководитель и секретарь»", "קבוצת מנהל (מנהל ועוזר)"),
 ("Page Group (paging / intercom)", "Группа оповещения (пейджинг / интерком)", "קבוצת כריזה (כריזה / אינטרקום)"),
 ("Select Members (Extensions):", "Выберите участников (номера):", "בחירת חברים (שלוחות):"),
 ("Loading extensions...", "Загрузка номеров...", "טוען שלוחות..."),
 ("Create Group", "Создать группу", "יצירת קבוצה"),
 ("Configured Call Groups", "Настроенные группы вызова", "קבוצות שיחה מוגדרות"),
 ("Add Trunk (PJSIP / IAX2)", "Добавить транк (PJSIP / IAX2)", "הוספת טראנק (PJSIP / IAX2)"),
 ("Name (e.g. Zadarma_Main)", "Название (например, Zadarma_Main)", "שם (לדוגמה: Zadarma_Main)"),
 ("PJSIP (Recommended)", "PJSIP (рекомендуется)", "PJSIP (מומלץ)"),
 ("IAX2 (Asterisk interconnection)", "IAX2 (связь между серверами Asterisk)", "IAX2 (חיבור בין שרתי Asterisk)"),
 ("Server Address (host / IP)", "Адрес сервера (хост / IP)", "כתובת שרת (שם מארח / IP)"),
 ("Username", "Имя пользователя", "שם משתמש"),
 ("Password (Secret)", "Пароль (secret)", "סיסמה (Secret)"),
 ("Add Trunk", "Добавить транк", "הוספת טראנק"),
 ("Configured Trunks", "Настроенные транки", "טראנקים מוגדרים"),
 ("Loading...", "Загрузка...", "טוען..."),
 ("Create Trunk Group", "Создать транковую группу", "יצירת קבוצת טראנקים"),
 ("Name (e.g. Outbound_Providers)", "Название (например, Outbound_Providers)", "שם (לדוגמה: Outbound_Providers)"),
 ("Outbound Prefix:", "Префикс исходящих:", "קידומת יוצאות:"),
 ("For example, 9, 0, or 8", "Например, 9, 0 или 8", "לדוגמה: 9, 0 או 8"),
 ("Strategy:", "Стратегия:", "אסטרטגיה:"),
 ("Failover (try trunks in order)", "Резервирование (транки по очереди)", "גיבוי (ניסיון טראנקים לפי הסדר)"),
 ("Load Balancing (distribute calls)", "Балансировка (распределение вызовов)", "איזון עומסים (חלוקת שיחות)"),
 ("Members (Trunks):", "Участники (транки):", "חברים (טראנקים):"),
 ("Create trunks first...", "Сначала создайте транки...", "יש ליצור טראנקים קודם..."),
 ("Save Group", "Сохранить группу", "שמירת קבוצה"),
 ("Configured Trunk Groups", "Настроенные транковые группы", "קבוצות טראנקים מוגדרות"),
 ("Create Interactive Voice Response (IVR)", "Создать голосовое меню (IVR)", "יצירת תפריט קולי אינטראקטיבי (IVR)"),
 ("Name (e.g. Main Menu)", "Название (например, Главное меню)", "שם (לדוגמה: תפריט ראשי)"),
 ("Access Extension (e.g. 500)", "Номер доступа (например, 500)", "שלוחת גישה (לדוגמה: 500)"),
 ("Audio File Name (e.g. main_greeting)", "Имя аудиофайла (например, main_greeting)", "שם קובץ שמע (לדוגמה: main_greeting)"),
 ("Keypad Options", "Кнопки меню", "אפשרויות מקלדת"),
 ("+ Add Option", "+ Добавить пункт", "+ הוספת אפשרות"),
 ("If No Key Is Pressed (Timeout)", "Если ни одна кнопка не нажата (таймаут)", "אם לא נלחץ מקש (פסק זמן)"),
 ("Hang Up", "Положить трубку", "ניתוק"),
 ("Transfer to Extension", "Перевести на номер", "העברה לשלוחה"),
 ("Transfer to Group", "Перевести на группу", "העברה לקבוצה"),
 ("Transfer to Another IVR", "Перевести на другое IVR", "העברה ל-IVR אחר"),
 ("Enter extension/group (not required for Hang Up)", "Введите номер/группу (для «Положить трубку» не нужно)", "הזינו שלוחה/קבוצה (לא נדרש לניתוק)"),
 ("Greeting Audio File (e.g. custom/ivr_500):", "Файл приветствия (например, custom/ivr_500):", "קובץ שמע לברכה (לדוגמה: custom/ivr_500):"),
 ("Or upload:", "Или загрузите:", "או העלאה:"),
 ("Tip:", "Подсказка:", "טיפ:"),
 (" Record the greeting directly from a phone! Dial ", " Запишите приветствие прямо с телефона! Наберите ", " הקליטו את הברכה ישירות מהטלפון! חייגו "),
 ("*77 + IVR extension", "*77 + номер IVR", "\u200e*77\u200e + שלוחת ה-IVR"),
 (" (for example, ", " (например, ", " (לדוגמה: "),
 ("). The file will automatically be saved as ", "). Файл автоматически сохранится как ", "). הקובץ יישמר אוטומטית בשם "),
 ("Save IVR", "Сохранить IVR", "שמירת IVR"),
 ("Configured IVR Menus", "Настроенные IVR-меню", "תפריטי IVR מוגדרים"),
 ("Waiting for data...", "Ожидание данных...", "ממתין לנתונים..."),
 ("Call Recording Archive", "Архив записей разговоров", "ארכיון הקלטות שיחות"),
 ("The call history and audio player will appear here.", "Здесь появятся история звонков и аудиоплеер.", "היסטוריית השיחות ונגן השמע יופיעו כאן."),
 ("Show/Hide Password", "Показать/скрыть пароль", "הצג/הסתר סיסמה"),
 # вход в веб-интерфейс
 ("Sign in", "Вход", "כניסה"),
 ("Sign out", "Выйти", "יציאה"),
 ("Repeat password", "Повторите пароль", "הקלידו שוב את הסיסמה"),
 ("Create administrator password", "Создайте пароль администратора", "יצירת סיסמת מנהל"),
 ("First start. Create a password for the administrator. Minimum 8 characters.",
  "Первый запуск. Создайте пароль администратора. Минимум 8 символов.",
  "הפעלה ראשונה. צרו סיסמה למנהל המערכת. לפחות 8 תווים."),
 ("Enter the administrator password.", "Введите пароль администратора.", "הזינו את סיסמת המנהל."),
 ("Create password", "Создать пароль", "יצירת סיסמה"),
 ("Password must be at least 8 characters", "Пароль должен содержать не менее 8 символов", "הסיסמה חייבת להכיל לפחות 8 תווים"),
 ("Passwords do not match", "Пароли не совпадают", "הסיסמאות אינן תואמות"),
 ("Wrong password", "Неверный пароль", "סיסמה שגויה"),
 ("Too many attempts, try again in a minute", "Слишком много попыток, повторите через минуту", "יותר מדי ניסיונות, נסו שוב בעוד דקה"),
 ("Password is already set. Please sign in.", "Пароль уже задан. Выполните вход.", "הסיסמה כבר הוגדרה. יש להתחבר."),
 # вкладка "Администрирование"
 ("Administration", "Администрирование", "ניהול מערכת"),
 ("System Status", "Состояние системы", "מצב המערכת"),
 ("Containers", "Контейнеры", "קונטיינרים"),
 ("Backup and Restore", "Резервная копия и восстановление", "גיבוי ושחזור"),
 ("The backup contains extensions, call groups, trunks, trunk groups, IVR menus and IVR audio files. Call recordings and the administrator password are not included. The file contains SIP passwords, so keep it secret.",
  "В резервную копию входят номера, группы вызова, транки, транковые группы, IVR-меню и аудиофайлы IVR. Записи разговоров и пароль администратора в неё не входят. Файл содержит SIP-пароли, поэтому храните его в секрете.",
  "הגיבוי כולל שלוחות, קבוצות שיחה, טראנקים, קבוצות טראנקים, תפריטי IVR וקובצי שמע של IVR. הקלטות שיחות וסיסמת המנהל אינן נכללות. הקובץ מכיל סיסמאות SIP, ולכן יש לשמור אותו בסוד."),
 ("Download Backup", "Скачать резервную копию", "הורדת גיבוי"),
 ("Restore from backup file:", "Восстановить из файла резервной копии:", "שחזור מקובץ גיבוי:"),
 ("Restore", "Восстановить", "שחזור"),
 ("Change Password", "Сменить пароль", "שינוי סיסמה"),
 ("Current password", "Текущий пароль", "סיסמה נוכחית"),
 ("New password", "Новый пароль", "סיסמה חדשה"),
 ("Repeat new password", "Повторите новый пароль", "הקלידו שוב את הסיסמה החדשה"),
 ("GB", "ГБ", "GB"),
 ("days", "дн.", "ימים"),
 ("hours", "ч", "שעות"),
 ("min", "мин", "דקות"),
 ("CPU load", "Нагрузка процессора", "עומס מעבד"),
 ("Memory", "Память", "זיכרון"),
 ("Disk", "Диск", "דיסק"),
 ("Uptime", "Время работы", "זמן פעולה"),
 ("cores", "ядер", "ליבות"),
 ("free", "свободно", "פנוי"),
 ("Running", "Работает", "פועל"),
 ("Failed to read system status.", "Не удалось получить состояние системы.", "קריאת מצב המערכת נכשלה."),
 ("Container information is unavailable.", "Сведения о контейнерах недоступны.", "המידע על הקונטיינרים אינו זמין."),
 ("Choose a backup file first", "Сначала выберите файл резервной копии", "יש לבחור קובץ גיבוי קודם"),
 ("All current settings will be replaced with the contents of the backup. Continue?",
  "Все текущие настройки будут заменены содержимым резервной копии. Продолжить?",
  "כל ההגדרות הנוכחיות יוחלפו בתוכן הגיבוי. להמשיך?"),
 ("Restoring...", "Восстанавливаю...", "משחזר..."),
 ("Backup restored and applied to Asterisk.", "Резервная копия восстановлена и применена в Asterisk.", "הגיבוי שוחזר והוחל ב-Asterisk."),
 ("Backup restored, but applying it to Asterisk failed. Use the Apply Configuration button.",
  "Резервная копия восстановлена, но применить её в Asterisk не удалось. Нажмите кнопку «Применить конфигурацию».",
  "הגיבוי שוחזר, אך החלתו ב-Asterisk נכשלה. יש ללחוץ על הכפתור «החלת תצורה»."),
 ("Backup downloaded", "Резервная копия скачана", "הגיבוי הורד"),
 ("Current password is incorrect", "Текущий пароль неверный", "הסיסמה הנוכחית שגויה"),
 ("Password changed", "Пароль изменён", "הסיסמה שונתה"),
 # таблицы
 ("Extension", "Номер", "שלוחה"),
 ("Caller ID", "Caller ID", "מזהה מתקשר"),
 ("Status", "Статус", "סטטוס"),
 ("Transport", "Транспорт", "העברה"),
 ("Password", "Пароль", "סיסמה"),
 ("Actions", "Действия", "פעולות"),
 ("Name", "Название", "שם"),
 ("Strategy", "Стратегия", "אסטרטגיה"),
 ("Members", "Участники", "חברים"),
 ("Audio File", "Аудиофайл", "קובץ שמע"),
 ("Routing", "Маршрутизация", "ניתוב"),
 ("Protocol", "Протокол", "פרוטוקול"),
 ("Host", "Хост", "מארח"),
 ("Prefix", "Префикс", "קידומת"),
 ("Group", "Группа", "קבוצה"),
 ("Another IVR", "Другое IVR", "IVR אחר"),
 ("Edit", "Изменить", "עריכה"),
 ("Delete", "Удалить", "מחיקה"),
 ("Save Changes", "Сохранить изменения", "שמירת שינויים"),
 ("Save Trunk", "Сохранить транк", "שמירת טראנק"),
 ("Not set", "Не задан", "לא הוגדר"),
 ("Timeout", "Таймаут", "פסק זמן"),
 ("Invalid Input", "Неверный ввод", "קלט שגוי"),
 ("Key (0-9, *, #)", "Кнопка (0-9, *, #)", "מקש (0-9, *, #)"),
 ("Destination (101, 600...)", "Назначение (101, 600...)", "יעד (101, 600...)"),
 ("Key [ ${digit} ]", "Кнопка [ ${digit} ]", "מקש [ ${digit} ]"),
 ("Extension <b>${action.target}</b>", "Номер <b>${action.target}</b>", "שלוחה <b>${action.target}</b>"),
 ("Group <b>${action.target}</b>", "Группа <b>${action.target}</b>", "קבוצה <b>${action.target}</b>"),
 ("No actions (greeting only)", "Нет действий (только приветствие)", "אין פעולות (ברכה בלבד)"),
 # сообщения и подтверждения
 ("No extensions have been created yet.", "Номера ещё не созданы.", "עדיין לא נוצרו שלוחות."),
 ("No call groups have been created yet.", "Группы вызова ещё не созданы.", "עדיין לא נוצרו קבוצות שיחה."),
 ("No trunks have been created yet.", "Транки ещё не созданы.", "עדיין לא נוצרו טראנקים."),
 ("No trunk groups have been created yet.", "Транковые группы ещё не созданы.", "עדיין לא נוצרו קבוצות טראנקים."),
 ("No IVR menus have been created yet.", "IVR-меню ещё не созданы.", "עדיין לא נוצרו תפריטי IVR."),
 ("Failed to load extensions.", "Не удалось загрузить номера.", "טעינת השלוחות נכשלה."),
 ("Failed to load call groups.", "Не удалось загрузить группы вызова.", "טעינת קבוצות השיחה נכשלה."),
 ("Failed to load IVR menus.", "Не удалось загрузить IVR-меню.", "טעינת תפריטי ה-IVR נכשלה."),
 ("Failed to load data.", "Не удалось загрузить данные.", "טעינת הנתונים נכשלה."),
 ("Create phone extensions in the Extensions tab first.", "Сначала создайте номера на вкладке «Номера».", "יש ליצור שלוחות בלשונית «שלוחות» קודם."),
 ("Create trunks first.", "Сначала создайте транки.", "יש ליצור טראנקים קודם."),
 ("Are you sure you want to delete this extension?", "Вы уверены, что хотите удалить этот номер?", "האם למחוק שלוחה זו?"),
 ("Are you sure you want to delete this group?", "Вы уверены, что хотите удалить эту группу?", "האם למחוק קבוצה זו?"),
 ("Delete this IVR menu?", "Удалить это IVR-меню?", "האם למחוק תפריט IVR זה?"),
 ("Delete this trunk?", "Удалить этот транк?", "האם למחוק טראנק זה?"),
 ("Delete this trunk group?", "Удалить эту транковую группу?", "האם למחוק קבוצת טראנקים זו?"),
 ("Failed to delete group", "Не удалось удалить группу", "מחיקת הקבוצה נכשלה"),
 ("Failed to delete", "Не удалось удалить", "המחיקה נכשלה"),
 ("Failed to save group", "Не удалось сохранить группу", "שמירת הקבוצה נכשלה"),
 ("Request failed", "Запрос не выполнен", "הבקשה נכשלה"),
 ("Network error", "Ошибка сети", "שגיאת רשת"),
 ("Server connection error", "Ошибка соединения с сервером", "שגיאת התחברות לשרת"),
 ("Error: ", "Ошибка: ", "שגיאה: "),
 ("Validation error: ", "Ошибка проверки: ", "שגיאת אימות: "),
 ("Editing Extension: ", "Редактирование номера: ", "עריכת שלוחה: "),
 ("Editing IVR: ", "Редактирование IVR: ", "עריכת IVR: "),
 ("Editing Trunk: ", "Редактирование транка: ", "עריכת טראנק: "),
 ("Editing Group: ", "Редактирование группы: ", "עריכת קבוצה: "),
 ("Edit Group", "Редактирование группы", "עריכת קבוצה"),
 ("Changes saved!", "Изменения сохранены!", "השינויים נשמרו!"),
 ("Extension created successfully!", "Номер успешно создан!", "השלוחה נוצרה בהצלחה!"),
 ('Group "${name}" updated!', 'Группа "${name}" обновлена!', 'הקבוצה "${name}" עודכנה!'),
 ('Group "${name}" created successfully!', 'Группа "${name}" успешно создана!', 'הקבוצה "${name}" נוצרה בהצלחה!'),
 ("Select at least one member!", "Выберите хотя бы одного участника!", "יש לבחור לפחות חבר אחד!"),
 ("IVR menu created successfully!", "IVR-меню успешно создано!", "תפריט ה-IVR נוצר בהצלחה!"),
 ("Trunk updated!", "Транк обновлён!", "הטראנק עודכן!"),
 ("Trunk ${payload.name} added!", "Транк ${payload.name} добавлен!", "הטראנק ${payload.name} נוסף!"),
 ("Group updated!", "Группа обновлена!", "הקבוצה עודכנה!"),
 ('Group "${payload.name}" created!', 'Группа "${payload.name}" создана!', 'הקבוצה "${payload.name}" נוצרה!'),
 ("Select at least one trunk!", "Выберите хотя бы один транк!", "יש לבחור לפחות טראנק אחד!"),
 # записи разговоров
 ("Recording Settings", "Настройки записи", "הגדרות הקלטה"),
 ("Calls of the selected extensions are recorded, both incoming and outgoing. After saving, press Apply Configuration.",
  "Записываются разговоры выбранных номеров, входящие и исходящие. После сохранения нажмите «Применить конфигурацию».",
  "שיחות של השלוחות שנבחרו מוקלטות, נכנסות ויוצאות. לאחר השמירה יש ללחוץ על «החלת תצורה»."),
 ("Select extensions", "Выберите номера", "בחירת שלוחות"),
 ("Save Settings", "Сохранить настройки", "שמירת הגדרות"),
 ("Call Recording Archive", "Архив записей разговоров", "ארכיון הקלטות שיחות"),
 ("Extension or number", "Номер или телефон", "שלוחה או מספר"),
 ("Min. duration (sec)", "Мин. длительность (сек)", "משך מינימלי (שניות)"),
 ("Duration", "Длительность", "משך"),
 ("From", "С", "מתאריך"),
 ("To", "По", "עד תאריך"),
 ("Search", "Найти", "חיפוש"),
 ("Reset", "Сбросить", "איפוס"),
 ("Date", "Дата", "תאריך"),
 ("Caller", "Звонящий", "מתקשר"),
 ("Callee", "Вызываемый", "נמען"),
 ("Listen", "Прослушать", "האזנה"),
 ("Download", "Скачать", "הורדה"),
 ("Show more", "Показать ещё", "הצג עוד"),
 ("Recording enabled for:", "Запись включена для:", "ההקלטה מופעלת עבור:"),
 ("Create extensions first.", "Сначала создайте номера.", "יש ליצור שלוחות קודם."),
 ("Saved. Press Apply Configuration to start recording.", "Сохранено. Нажмите «Применить конфигурацию», чтобы запись началась.", "נשמר. יש ללחוץ על «החלת תצורה» כדי להתחיל להקליט."),
 ("Failed to save settings.", "Не удалось сохранить настройки.", "שמירת ההגדרות נכשלה."),
 ("Failed to load recordings.", "Не удалось загрузить записи.", "טעינת ההקלטות נכשלה."),
 ("Recordings found:", "Найдено записей:", "נמצאו הקלטות:"),
 ("No recordings found.", "Записи не найдены.", "לא נמצאו הקלטות."),
 ("Delete this recording?", "Удалить эту запись?", "האם למחוק הקלטה זו?"),
]

# Эти слова ещё и сравниваются с ответами Asterisk (includes('Unavailable')) -
# поэтому меняем только отображаемый вариант, с точным контекстом.
RAW = [
 (">Unknown</span>",     ">Неизвестно</span>",    ">לא ידוע</span>"),
 (">Available</span>",   ">Доступен</span>",      ">זמין</span>"),
 (">Busy</span>",        ">Занят</span>",         ">תפוס</span>"),
 (">Unavailable</span>", ">Недоступен</span>",    ">לא זמין</span>"),
]

BEFORE = "['\"`>]"
AFTER = "['\"`<$]"
hits = {}

def translate(text, idx, lang):
    for e, *tr in RAW:
        n = text.count(e)
        hits[(lang, e)] = hits.get((lang, e), 0) + n
        text = text.replace(e, tr[idx])
    for e, ru, he in sorted(T, key=lambda t: -len(t[0])):
        pat = re.compile("(?<=" + BEFORE + ")" + re.escape(e) + "(?=" + AFTER + ")")
        new = (ru, he)[idx]
        text, n = pat.subn(lambda m: new, text)
        hits[(lang, e)] = hits.get((lang, e), 0) + n
    return text

SWAP = {"margin-left": "margin-right", "margin-right": "margin-left",
        "padding-left": "padding-right", "padding-right": "padding-left",
        "border-left": "border-right", "border-right": "border-left"}

def mirror(text):
    text = re.sub(r"\b(margin|padding|border)-(left|right)\b",
                  lambda m: SWAP[m.group(0)], text)
    return re.sub(r"text-align:\s*left", "text-align: right", text)

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()

def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f: f.write(s)

def main():
    if not os.path.isdir(os.path.join(ROOT, "en")):
        sys.exit("Запустите из корня репозитория (должна быть папка frontend/en)")
    # 1. чистим русские остатки в en
    for rel, pairs in EN_FIX.items():
        p = os.path.join(ROOT, "en", rel); s = read(p)
        for a, b in pairs: s = s.replace(a, b)
        write(p, s)
    # 2. собираем ru и he из en
    for lang, idx in (("ru", 0), ("he", 1)):
        for rel in FILES:
            s = read(os.path.join(ROOT, "en", rel))
            if rel.endswith((".html", ".js")):
                if rel.endswith(".html"):
                    s = s.replace('<html lang="en">',
                                  '<html lang="ru">' if lang == "ru" else '<html lang="he" dir="rtl">')
                s = translate(s, idx, lang)
                if lang == "he":
                    s = mirror(s).replace("<b>*77500</b>", '<b dir="ltr">*77500</b>')
            elif rel == "style.css" and lang == "he":
                s = s.rstrip("\n") + "\nbody { direction: rtl; text-align: right; }\n"
            s = re.sub(r"\?v=\d+", "?v=22", s)   # сброс кеша браузера
            write(os.path.join(ROOT, lang, rel), s)
    # en тоже обновляем версию скриптов
    p = os.path.join(ROOT, "en", "index.html")
    write(p, re.sub(r"\?v=\d+", "?v=22", read(p)))
    missing = sorted({e for (l, e), n in hits.items() if n == 0 and (l == "ru")})
    print("Готово: frontend/en исправлен, frontend/ru и frontend/he пересобраны.")
    if missing:
        print("Предупреждение: не встретились строки:", missing)

if __name__ == "__main__":
    main()
