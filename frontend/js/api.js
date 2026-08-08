// Единый модуль для всех запросов к серверу
const API = {
    async getExtensions() {
        const res = await fetch('/api/extensions');
        return res.json();
    },
    async createExtension(data) {
        return fetch('/api/extensions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    async deleteExtension(id) {
        return fetch(`/api/extensions/${id}`, { method: 'DELETE' });
    },
    async getStatus() {
        const res = await fetch('/api/status');
        return res.json();
    },
    async reloadPbx() {
        return fetch('/api/pbx/reload', { method: 'POST' });
    },
    async getGroups() {
        const res = await fetch('/api/groups');
        return res.json();
    },
    async createGroup(data) {
        return fetch('/api/groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    async updateGroup(id, data) {
        return fetch(`/api/groups/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    async deleteGroup(id) {
        return fetch(`/api/groups/${id}`, { method: 'DELETE' });
    },

    // --- Транки ---
    async getTrunks() {
        const res = await fetch('/api/trunks');
        return res.json();
    },
    async createTrunk(data) {
        return fetch('/api/trunks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    async deleteTrunk(id) {
        return fetch(`/api/trunks/${id}`, { method: 'DELETE' });
    },
    // --- Транковые группы ---
    async getTrunkGroups() {
        const res = await fetch('/api/trunk-groups');
        return res.json();
    },
    async createTrunkGroup(data) {
        return fetch('/api/trunk-groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    async deleteTrunkGroup(id) {
        return fetch(`/api/trunk-groups/${id}`, { method: 'DELETE' });
    }
};