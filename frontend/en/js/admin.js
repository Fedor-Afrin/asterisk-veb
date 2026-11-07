// Вкладка "Администрирование": состояние системы, резервная копия, смена пароля.
const AdminModule = (() => {
    const TEXT = {
        gb: 'GB',
        days: 'days',
        hours: 'hours',
        minutes: 'min',
        cpuLoad: 'CPU load',
        memory: 'Memory',
        disk: 'Disk',
        uptime: 'Uptime',
        cores: 'cores',
        free: 'free',
        running: 'Running',
        statusError: 'Failed to read system status.',
        noContainers: 'Container information is unavailable.',
        chooseFile: 'Choose a backup file first',
        confirmRestore: 'All current settings will be replaced with the contents of the backup. Continue?',
        restoring: 'Restoring...',
        restored: 'Backup restored and applied to Asterisk.',
        restoredNotApplied: 'Backup restored, but applying it to Asterisk failed. Use the Apply Configuration button.',
        downloaded: 'Backup downloaded',
        oldIncorrect: 'Current password is incorrect',
        passwordChanged: 'Password changed',
        minLength: 'Password must be at least 8 characters',
        mismatch: 'Passwords do not match',
        connectionError: 'Server connection error'
    };

    let timer = null;
    const el = (id) => document.getElementById(id);

    function fmtGb(bytes) { return (bytes / 1073741824).toFixed(1) + ' ' + TEXT.gb; }

    function fmtUptime(sec) {
        const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60);
        return (d ? d + ' ' + TEXT.days + ' ' : '') + (d || h ? h + ' ' + TEXT.hours + ' ' : '') + m + ' ' + TEXT.minutes;
    }

    function meter(label, valueText, percent, note) {
        const color = percent >= 90 ? '#dc3545' : percent >= 70 ? '#ffc107' : '#28a745';
        return `<div class="metric-row">
            <div class="metric-head"><span>${label}</span><span>${valueText}</span></div>
            <div class="meter"><div class="meter-fill" style="width: ${Math.min(percent, 100)}%; background: ${color};"></div></div>
            <div class="metric-note"><span dir="ltr">${note}</span></div>
        </div>`;
    }

    function lamp(color) {
        return `<span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: ${color}; margin-right: 6px; box-shadow: 0 0 5px ${color};"></span>`;
    }

    async function refresh() {
        const metrics = el('sysMetrics');
        const containers = el('sysContainers');
        try {
            const res = await fetch('/api/admin/system');
            if (!res.ok) throw new Error('status ' + res.status);
            const d = await res.json();

            metrics.innerHTML =
                meter(TEXT.cpuLoad, d.cpu.percent + '%', d.cpu.percent,
                      d.cpu.load.map(x => x.toFixed(2)).join(' / ') + ' &middot; ' + d.cpu.cores + ' ' + TEXT.cores) +
                meter(TEXT.memory, d.memory.percent + '%', d.memory.percent,
                      fmtGb(d.memory.used) + ' / ' + fmtGb(d.memory.total)) +
                meter(TEXT.disk, d.disk.percent + '%', d.disk.percent,
                      fmtGb(d.disk.used) + ' / ' + fmtGb(d.disk.total) + ' &middot; ' + fmtGb(d.disk.free) + ' ' + TEXT.free) +
                `<div class="metric-head"><span>${TEXT.uptime}</span><span>${fmtUptime(d.uptime)}</span></div>`;

            if (!d.containers || d.containers.length === 0) {
                containers.innerHTML = `<p style="color: #666; font-style: italic;">${TEXT.noContainers}</p>`;
            } else {
                let html = '<table style="width:100%; border-collapse: collapse;">';
                html += '<tr style="background: #f1f1f1; text-align: left;"><th style="padding: 8px; border: 1px solid #ddd;">Name</th><th style="padding: 8px; border: 1px solid #ddd;">Status</th></tr>';
                d.containers.forEach(c => {
                    const up = c.state === 'running';
                    html += `<tr>
                        <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">${c.name}</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">${lamp(up ? '#28a745' : '#dc3545')}<span style="color: ${up ? '#28a745' : '#dc3545'}; font-weight: bold;">${up ? TEXT.running : c.state}</span> <span class="metric-note">${c.status || ''}</span></td>
                    </tr>`;
                });
                containers.innerHTML = html + '</table>';
            }
        } catch (err) {
            metrics.innerHTML = `<p style="color: red;">${TEXT.statusError}</p>`;
        }
    }

    function start() {
        refresh();
        if (!timer) timer = setInterval(refresh, 5000);
    }

    function stop() {
        if (timer) { clearInterval(timer); timer = null; }
    }

    async function downloadBackup() {
        const result = el('backupResult');
        result.style.color = '#555';
        result.textContent = '';
        try {
            const res = await fetch('/api/admin/backup');
            if (!res.ok) throw new Error('status ' + res.status);
            const blob = await res.blob();
            const disposition = res.headers.get('Content-Disposition') || '';
            const match = /filename="([^"]+)"/.exec(disposition);
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = match ? match[1] : 'asterisk-pbx-backup.zip';
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(link.href), 1000);
            result.style.color = 'green';
            result.textContent = TEXT.downloaded;
        } catch (err) {
            result.style.color = 'red';
            result.textContent = TEXT.connectionError;
        }
    }

    async function restoreBackup() {
        const result = el('backupResult');
        const input = el('restoreFile');
        if (!input.files.length) {
            result.style.color = 'red';
            result.textContent = TEXT.chooseFile;
            return;
        }
        if (!confirm(TEXT.confirmRestore)) return;

        result.style.color = '#555';
        result.textContent = TEXT.restoring;
        const form = new FormData();
        form.append('file', input.files[0]);
        try {
            const res = await fetch('/api/admin/restore', { method: 'POST', body: form });
            const data = await res.json().catch(() => ({}));
            if (res.ok) {
                result.style.color = data.applied ? 'green' : '#b36b00';
                result.textContent = data.applied ? TEXT.restored : TEXT.restoredNotApplied;
                input.value = '';
            } else if (res.status !== 401) {
                result.style.color = 'red';
                result.textContent = `Error: ${typeof data.detail === 'string' ? data.detail : 'Request failed'}`;
            }
        } catch (err) {
            result.style.color = 'red';
            result.textContent = TEXT.connectionError;
        }
    }

    async function changePassword(e) {
        e.preventDefault();
        const result = el('passwordResult');
        const oldPw = el('pwOld').value, newPw = el('pwNew').value, newPw2 = el('pwNew2').value;
        result.style.color = 'red';
        if (newPw.length < 8) { result.textContent = TEXT.minLength; return; }
        if (newPw !== newPw2) { result.textContent = TEXT.mismatch; return; }
        try {
            const res = await fetch('/api/admin/password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ old_password: oldPw, new_password: newPw })
            });
            if (res.ok) {
                result.style.color = 'green';
                result.textContent = TEXT.passwordChanged;
                el('passwordForm').reset();
            } else if (res.status === 403) {
                result.textContent = TEXT.oldIncorrect;
            } else if (res.status !== 401) {
                const data = await res.json().catch(() => ({}));
                result.textContent = typeof data.detail === 'string' ? data.detail : TEXT.connectionError;
            }
        } catch (err) {
            result.textContent = TEXT.connectionError;
        }
    }

    function init() {
        el('backupDownloadBtn').addEventListener('click', downloadBackup);
        el('restoreBtn').addEventListener('click', restoreBackup);
        el('passwordForm').addEventListener('submit', changePassword);
    }

    return { init, start, stop };
})();
