document.addEventListener('alpine:init', () => {
    Alpine.data('moneyInput', (initialValue = 0, allowNegative = false) => ({
        displayValue: '',
        rawValue: '0.00',
        isNegative: false,
        allowNegative: allowNegative,
        
        init() {
            let num = 0;
            if (typeof initialValue === 'number') {
                num = initialValue;
            } else if (typeof initialValue === 'string' && initialValue.trim() !== '') {
                num = parseFloat(initialValue.replace(',', '.')) || 0;
            }
            if (this.allowNegative && num < 0) {
                this.isNegative = true;
                num = Math.abs(num);
            }
            const cents = Math.round(num * 100);
            this.updateFromCents(cents);
        },

        format(cents) {
            const val = cents / 100;
            const formatted = val.toLocaleString('pt-BR', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
            return this.isNegative ? `-${formatted}` : formatted;
        },

        updateFromCents(cents) {
            const val = cents / 100;
            const numVal = this.isNegative ? -val : val;
            this.rawValue = numVal.toFixed(2);
            this.displayValue = this.format(cents);
        },

        onInput(event) {
            const inputVal = event.target.value;
            if (this.allowNegative) {
                if (inputVal.includes('-')) {
                    this.isNegative = true;
                } else if (event.data !== null && inputVal.startsWith('+')) {
                    this.isNegative = false;
                }
            }
            const digits = inputVal.replace(/\D/g, '');
            const cents = digits ? parseInt(digits, 10) : 0;
            this.updateFromCents(cents);
            event.target.value = this.displayValue;
            this.$dispatch('money-changed', { rawValue: parseFloat(this.rawValue) });
        }
    }));

    Alpine.data('transactionForm', (initialData) => ({
        txType: initialData.txType,
        isRecurring: initialData.isRecurring || false,
        frequency: initialData.frequency || 'monthly',
        recurringEndDate: initialData.recurringEndDate || '',
        installments: 1,
        selectedAccountType: initialData.selectedAccountType,
        originalAccountId: initialData.originalAccountId,
        selectedAccountId: initialData.selectedAccountId,
        originalAmount: initialData.originalAmount,
        amount: initialData.amount !== undefined ? initialData.amount : (parseFloat(initialData.originalAmount) || 0),
        selectedAccountLimit: initialData.selectedAccountLimit,
        selectedCategoryId: initialData.selectedCategoryId || '',
        selectedTagIds: initialData.selectedTagIds || [],
        status: initialData.status || 'concluída',
        categories: initialData.categories || [],
        descriptionHabits: initialData.descriptionHabits || {},
        descriptionQuery: '',
        showSuggestions: false,
        autoFillActive: false,
        
        init() {
            this.$watch('txType', () => this.handleTxTypeChange());
        },

        setTxType(type) {
            this.txType = type;
            this.handleTxTypeChange();
        },

        handleTxTypeChange() {
            if (this.txType === 'receita' && this.selectedAccountType === 'credit_card') {
                const accountSelect = this.$refs.accountSelect;
                if (accountSelect) {
                    const validOption = Array.from(accountSelect.options).find(opt => opt.dataset.type !== 'credit_card' && !opt.disabled && opt.value);
                    if (validOption) {
                        accountSelect.value = validOption.value;
                        this.selectedAccountId = validOption.value;
                        this.selectedAccountType = validOption.dataset.type;
                        this.selectedAccountLimit = parseFloat(validOption.dataset.limit || 0);
                    }
                }
            }
            if (this.selectedCategoryId) {
                const cat = this.categories.find(c => c.id === this.selectedCategoryId);
                if (cat && cat.type !== this.txType) {
                    this.selectedCategoryId = '';
                }
            }
        },

        get matchingSuggestions() {
            const q = (this.descriptionQuery || '').trim().toLowerCase();
            if (q.length < 3 || !this.descriptionHabits) return [];
            return Object.keys(this.descriptionHabits)
                .filter(desc => desc.toLowerCase().includes(q))
                .slice(0, 5);
        },

        onDescriptionInput(value) {
            this.descriptionQuery = value || '';
            this.showSuggestions = this.matchingSuggestions.length > 0;
            this.autoFillActive = false;
        },

        selectSuggestion(desc) {
            this.descriptionQuery = desc;
            if (this.$refs.descInput) {
                this.$refs.descInput.value = desc;
            }
            this.showSuggestions = false;
            const habit = this.descriptionHabits[desc];
            if (habit) {
                this.applyHabit(habit);
            }
        },

        applyHabit(habit) {
            if (habit.type && habit.type !== this.txType) {
                this.setTxType(habit.type);
            }

            if (habit.account_id && this.$refs.accountSelect) {
                const opt = Array.from(this.$refs.accountSelect.options).find(o => o.value === habit.account_id && !o.disabled);
                if (opt) {
                    this.$refs.accountSelect.value = habit.account_id;
                    this.selectedAccountId = habit.account_id;
                    this.selectedAccountType = opt.dataset.type || '';
                    this.selectedAccountLimit = parseFloat(opt.dataset.limit || 0);
                }
            }

            if (habit.category_id) {
                this.selectedCategoryId = habit.category_id;
            }

            if (Array.isArray(habit.tag_ids)) {
                this.selectedTagIds = [...habit.tag_ids];
            }

            this.autoFillActive = true;
        },

        clearAutoFill() {
            this.autoFillActive = false;
        },

        get availableLimit() {
            return this.selectedAccountId === this.originalAccountId 
                ? this.selectedAccountLimit + this.originalAmount 
                : this.selectedAccountLimit;
        },
        
        get availableLimitFormatted() {
            return this.availableLimit.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        },

        get isAmountOverLimit() {
            const amount = typeof this.amount === 'number' ? this.amount : parseFloat(this.amount || 0);
            return this.txType === 'despesa' && 
                   this.selectedAccountType === 'credit_card' && 
                   amount > this.availableLimit;
        },

        get filteredCategories() {
            return this.categories.filter(c => c.type === this.txType);
        }
    }));

    Alpine.data('categoryForm', () => ({
        open: false,
        selected: '',
        emojis: ['🍔', '🏠', '🚌', '🎉', '🏥', '📚', '👕', '📱', '🐾', '✈️', '💰', '⚖️', '🏷️', '💡']
    }));

    Alpine.data('tutorialModal', () => ({
        showTutorial: false,
        step: 1,
        totalSteps: 4,
        init() {
            if (!localStorage.getItem('moneta_tutorial_seen')) {
                setTimeout(() => { this.showTutorial = true; }, 500);
            }
        },
        next() {
            if (this.step < this.totalSteps) {
                this.step++;
            } else {
                this.close();
            }
        },
        prev() {
            if (this.step > 1) this.step--;
        },
        close() {
            this.showTutorial = false;
            localStorage.setItem('moneta_tutorial_seen', 'true');
        }
    }));

    Alpine.data('payModal', (initialDate) => ({
        open: true,
        dateMode: 'other',
        dateValue: initialDate,
        today: new Date(new Date().getTime() - new Date().getTimezoneOffset() * 60000).toISOString().split('T')[0],
        yesterday: new Date(new Date().getTime() - new Date().getTimezoneOffset() * 60000 - 86400000).toISOString().split('T')[0],
        init() {
            if (this.dateValue === this.today) this.dateMode = 'today';
            else if (this.dateValue === this.yesterday) this.dateMode = 'yesterday';
        },
        setDate(mode) {
            this.dateMode = mode;
            if (mode === 'today') this.dateValue = this.today;
            else if (mode === 'yesterday') this.dateValue = this.yesterday;
        },
        close() {
            this.open = false;
            setTimeout(() => {
                this.$el.closest('.fixed').remove();
            }, 300);
        }
    }));

    Alpine.data('toastContainer', () => ({
        toasts: [],
        init() {
            // Toasts that were still visible when the previous page unloaded (e.g. a reload right
            // after an HTMX action) are restored with their remaining lifetime.
            try {
                const pending = JSON.parse(sessionStorage.getItem(TOAST_STORAGE_KEY) || '[]');
                sessionStorage.removeItem(TOAST_STORAGE_KEY);
                pending.forEach(t => this.addToast(t.message, t.type, t.remaining));
            } catch (e) {
                sessionStorage.removeItem(TOAST_STORAGE_KEY);
            }

            // Django messages rendered server-side (full page loads / HX-Redirect flows).
            const source = document.getElementById('django-messages');
            if (source) {
                source.content.querySelectorAll('[data-toast-message]').forEach(el => {
                    this.addToast(el.dataset.toastMessage, el.dataset.toastType || 'info');
                });
            }

            window.addEventListener('pagehide', () => this.persist());
        },
        persist() {
            const now = Date.now();
            const visible = this.toasts
                .filter(t => t.show && t.expiresAt - now > TOAST_MIN_RESTORE_MS)
                .map(t => ({ message: t.message, type: t.type, remaining: t.expiresAt - now }));
            if (visible.length) {
                sessionStorage.setItem(TOAST_STORAGE_KEY, JSON.stringify(visible));
            } else {
                sessionStorage.removeItem(TOAST_STORAGE_KEY);
            }
        },
        addToast(message, type = 'success', duration = TOAST_DURATION_MS) {
            if (!message) return;
            const id = Date.now() + Math.random().toString(36).slice(2, 9);
            const toast = {
                id,
                message,
                type,
                show: true,
                expiresAt: Date.now() + duration
            };
            this.toasts.push(toast);

            setTimeout(() => {
                this.removeToast(id);
            }, duration);
        },
        removeToast(id) {
            const toast = this.toasts.find(t => t.id === id);
            if (toast) {
                toast.show = false;
                setTimeout(() => {
                    this.toasts = this.toasts.filter(t => t.id !== id);
                }, 300);
            }
        }
    }));
});

const TOAST_STORAGE_KEY = 'moneta_pending_toasts';
const TOAST_DURATION_MS = 4000;
const TOAST_MIN_RESTORE_MS = 500;


window.monetaCharts = window.monetaCharts || {};

function responseHasErrorToast(xhr) {
    const header = xhr && xhr.getResponseHeader('HX-Trigger');
    if (!header) return false;
    try {
        const toast = JSON.parse(header)['show-toast'];
        return !!toast && (toast.type === 'error' || toast.type === 'danger');
    } catch (e) {
        return false;
    }
}

window.afterModalSubmit = function(event) {
    if (!event || !event.detail || !event.detail.successful) return;

    const xhr = event.detail.xhr;
    // Validation/business errors come back as 204 + error toast: keep the modal open so the
    // user can fix the input instead of losing it to a reload.
    if (responseHasErrorToast(xhr)) return;
    // HTMX already navigates on these headers; reloading here would race with it.
    if (xhr && (xhr.getResponseHeader('HX-Redirect') || xhr.getResponseHeader('HX-Refresh'))) return;

    const filterForm = document.getElementById('filter-form');
    if (filterForm) {
        filterForm.dispatchEvent(new Event('submit'));
    } else {
        window.location.reload();
    }
    const modal = event.target ? event.target.closest('.fixed') : null;
    if (modal) {
        modal.remove();
    }
};

window.initChartWhenReady = window.initChartWhenReady || function(canvasId, renderFn) {
    function tryInit() {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        if (typeof Chart === 'undefined') {
            setTimeout(tryInit, 50);
            return;
        }
        renderFn(canvas);
    }

    if (document.readyState === 'loading') {
        document.addEventListener("DOMContentLoaded", tryInit);
    } else {
        tryInit();
    }
    document.addEventListener("htmx:afterSettle", function(evt) {
        if (document.getElementById(canvasId)) {
            tryInit();
        }
    });
};
