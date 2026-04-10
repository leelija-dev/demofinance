document.addEventListener('DOMContentLoaded', function () {

    // Initialize date range picker
    if (dateRangeFilter) {
        flatpickr(dateRangeFilter, {
            mode: 'range',
            dateFormat: 'd M Y',
            allowInput: true,
            position: 'below',
            static: true,
            appendTo: dateRangeFilter.parentElement || document.body,
            onReady: function (selectedDates, dateStr, instance) {
                if (window.innerWidth <= 640) {
                    instance.calendarContainer.style.left = 'auto';
                    instance.calendarContainer.style.right = 'auto';
                    instance.calendarContainer.style.transform = 'translateX(-29%)';
                }
            },
            onOpen: function (selectedDates, dateStr, instance) {
                if (window.innerWidth <= 640) {
                    instance.calendarContainer.style.left = 'auto';
                    instance.calendarContainer.style.right = 'auto';
                    instance.calendarContainer.style.transform = 'translateX(-29%)';
                }
            }
        });
    }
});