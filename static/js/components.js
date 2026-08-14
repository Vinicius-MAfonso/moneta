document.addEventListener('alpine:init', () => {
    Alpine.data('transactionForm', (initialData) => ({
        txType: initialData.txType,
        isRecurring: false,
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
});
