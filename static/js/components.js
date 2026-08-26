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
        status: initialData.status || 'concluída',
        categories: initialData.categories,
        
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
});

