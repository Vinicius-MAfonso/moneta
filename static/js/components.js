document.addEventListener('alpine:init', () => {
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
        selectedAccountLimit: initialData.selectedAccountLimit,
        categories: initialData.categories,
        
        get availableLimit() {
            return this.selectedAccountId === this.originalAccountId 
                ? this.selectedAccountLimit + this.originalAmount 
                : this.selectedAccountLimit;
        },
        
        get availableLimitFormatted() {
            return this.availableLimit.toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        },

        get isAmountOverLimit() {
            const amountInput = this.$refs.amountInput;
            const amount = parseFloat(amountInput ? amountInput.value : 0);
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

