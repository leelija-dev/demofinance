// Initialize flatpickr datepicker for disbursement date
function setupDisbursementDatepicker() {
    if (window.flatpickr) {
        const today = new Date();
        const disbursementDateInput = document.getElementById('disbursement_date');
        
        if (disbursementDateInput) {
            flatpickr(disbursementDateInput, {
                mode: 'single',
                dateFormat: 'Y-m-d',
                maxDate: today, // Cannot select future dates
                defaultDate: today, // Set default to today
                allowInput: true,
                disableMobile: false, // Use native mobile picker on mobile devices
                placeholder: 'Select disbursement date',
                onChange: function(selectedDates, dateStr, instance) {
                    // Trigger net amount calculation when date changes
                    if (typeof calculateNetAmount === 'function') {
                        calculateNetAmount();
                    }
                }
            });
        }
    }
}
