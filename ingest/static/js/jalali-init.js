/**
 * Jalali datepicker initialization for uniform date handling
 */
(function() {
    'use strict';
    
    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', function() {
        initializeJalaliDatepickers();
    });
    
    // Also initialize when new content is added (for admin inlines)
    document.addEventListener('formset:added', function() {
        initializeJalaliDatepickers();
    });
    
    function initializeJalaliDatepickers() {
        // Check if Persian datepicker library is available
        if (typeof persianDatepicker === 'undefined') {
            console.warn('Persian datepicker library not loaded. Jalali datepickers will not work.');
            return;
        }
        
        // Initialize date inputs
        var dateInputs = document.querySelectorAll('input[data-jalali="1"]:not([data-jalali-initialized])');
        dateInputs.forEach(function(input) {
            initializeDateInput(input);
        });
    }
    
    function initializeDateInput(input) {
        var hasTimepicker = input.hasAttribute('data-timepicker');
        
        var config = {
            initialValue: false,
            format: hasTimepicker ? 'YYYY/MM/DD HH:mm' : 'YYYY/MM/DD',
            timePicker: {
                enabled: hasTimepicker,
                format: 'HH:mm'
            },
            calendar: {
                persian: {
                    locale: 'fa'
                }
            },
            navigator: {
                enabled: true,
                text: {
                    btnNextText: '>',
                    btnPrevText: '<'
                }
            },
            toolbox: {
                enabled: true,
                calendarSwitch: {
                    enabled: false  // Force Persian calendar
                },
                todayButton: {
                    enabled: true,
                    text: {
                        fa: 'امروز'
                    }
                },
                submitButton: {
                    enabled: true,
                    text: {
                        fa: 'تأیید'
                    }
                },
                calendarToggle: {
                    enabled: false
                }
            },
            onSelect: function(unix) {
                // Convert selected date to display format
                var selectedDate = new persianDate(unix);
                var formattedDate = selectedDate.format(config.format);
                input.value = formattedDate;
                
                // Trigger change event for form validation
                var event = new Event('change', { bubbles: true });
                input.dispatchEvent(event);
            }
        };
        
        // Initialize the datepicker
        try {
            persianDatepicker(input, config);
            input.setAttribute('data-jalali-initialized', 'true');
            
            // Add CSS classes for styling
            input.classList.add('jalali-datepicker-input');
            if (hasTimepicker) {
                input.classList.add('jalali-datetime-input');
            } else {
                input.classList.add('jalali-date-input');
            }
            
        } catch (error) {
            console.error('Failed to initialize Jalali datepicker:', error);
        }
    }
    
    // Helper function to convert Persian digits to English
    function persianToEnglishDigits(str) {
        var persianDigits = '۰۱۲۳۴۵۶۷۸۹';
        var englishDigits = '0123456789';
        
        for (var i = 0; i < persianDigits.length; i++) {
            str = str.replace(new RegExp(persianDigits[i], 'g'), englishDigits[i]);
        }
        
        return str;
    }
    
    // Helper function to convert English digits to Persian
    function englishToPersianDigits(str) {
        var englishDigits = '0123456789';
        var persianDigits = '۰۱۲۳۴۵۶۷۸۹';
        
        for (var i = 0; i < englishDigits.length; i++) {
            str = str.replace(new RegExp(englishDigits[i], 'g'), persianDigits[i]);
        }
        
        return str;
    }
    
    // Expose helper functions globally if needed
    window.JalaliDatepicker = {
        initialize: initializeJalaliDatepickers,
        persianToEnglishDigits: persianToEnglishDigits,
        englishToPersianDigits: englishToPersianDigits
    };
})();
