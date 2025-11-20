/**
 * Jalali Date Input JavaScript Helper
 * Provides validation and formatting for Jalali date inputs
 */

(function() {
    'use strict';
    
    // Jalali month names
    const jalaliMonths = [
        'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
        'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
    ];
    
    // Validate Jalali date format
    function validateJalaliDate(dateStr) {
        if (!dateStr) return true; // Empty is valid
        
        const pattern = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/;
        const match = dateStr.match(pattern);
        
        if (!match) return false;
        
        const year = parseInt(match[1]);
        const month = parseInt(match[2]);
        const day = parseInt(match[3]);
        
        // Basic validation
        if (year < 1300 || year > 1500) return false;
        if (month < 1 || month > 12) return false;
        if (day < 1 || day > 31) return false;
        
        // Month-specific day validation
        if (month <= 6 && day > 31) return false;
        if (month > 6 && month <= 11 && day > 30) return false;
        if (month === 12 && day > 29) return false; // Simplified leap year check
        
        return true;
    }
    
    // Validate Jalali datetime format
    function validateJalaliDateTime(datetimeStr) {
        if (!datetimeStr) return true; // Empty is valid
        
        const parts = datetimeStr.split(' ');
        if (parts.length !== 2) return false;
        
        const [dateStr, timeStr] = parts;
        
        // Validate date part
        if (!validateJalaliDate(dateStr)) return false;
        
        // Validate time part
        const timePattern = /^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$/;
        const timeMatch = timeStr.match(timePattern);
        
        if (!timeMatch) return false;
        
        const hour = parseInt(timeMatch[1]);
        const minute = parseInt(timeMatch[2]);
        const second = timeMatch[3] ? parseInt(timeMatch[3]) : 0;
        
        if (hour < 0 || hour > 23) return false;
        if (minute < 0 || minute > 59) return false;
        if (second < 0 || second > 59) return false;
        
        return true;
    }
    
    // Format input as user types
    function formatJalaliInput(input, isDateTime = false) {
        let value = input.value.replace(/[^\d\/:\s]/g, ''); // Only allow digits, /, :, and space
        
        if (isDateTime) {
            // Handle datetime format
            const parts = value.split(' ');
            if (parts.length > 0) {
                // Format date part
                let datePart = parts[0].replace(/\//g, '');
                if (datePart.length >= 4) {
                    datePart = datePart.substring(0, 4) + '/' + datePart.substring(4);
                }
                if (datePart.length >= 7) {
                    datePart = datePart.substring(0, 7) + '/' + datePart.substring(7, 9);
                }
                
                value = datePart;
                if (parts.length > 1) {
                    value += ' ' + parts.slice(1).join(' ');
                }
            }
        } else {
            // Handle date format
            value = value.replace(/\//g, '');
            if (value.length >= 4) {
                value = value.substring(0, 4) + '/' + value.substring(4);
            }
            if (value.length >= 7) {
                value = value.substring(0, 7) + '/' + value.substring(7, 9);
            }
        }
        
        input.value = value;
    }
    
    // Add validation styling
    function updateValidationStyling(input, isValid) {
        input.classList.remove('error');
        const errorElement = input.parentNode.querySelector('.jalali-date-error');
        if (errorElement) {
            errorElement.remove();
        }
        
        if (!isValid && input.value.trim()) {
            input.classList.add('error');
            const error = document.createElement('div');
            error.className = 'jalali-date-error';
            error.textContent = 'فرمت تاریخ نامعتبر است';
            input.parentNode.appendChild(error);
        }
    }
    
    // Complete Jalali date picker functionality
    function createDatePicker(input) {
        const picker = document.createElement('div');
        picker.className = 'jalali-date-picker';
        picker.style.cssText = `
            position: absolute;
            background: white;
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 1000;
            display: none;
            direction: rtl;
            font-family: Tahoma, Arial, sans-serif;
            min-width: 280px;
        `;
        
        // Get current Jalali date
        const today = new Date();
        const jalaliToday = toJalali(today.getFullYear(), today.getMonth() + 1, today.getDate());
        const currentYear = jalaliToday.year;
        
        // Create year options (10 years back and forward)
        let yearOptions = '';
        for (let y = currentYear - 10; y <= currentYear + 10; y++) {
            yearOptions += `<option value="${y}" ${y === currentYear ? 'selected' : ''}>${y}</option>`;
        }
        
        // Create month options
        const monthNames = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
        let monthOptions = '';
        for (let m = 1; m <= 12; m++) {
            monthOptions += `<option value="${m}" ${m === jalaliToday.month ? 'selected' : ''}>${monthNames[m-1]}</option>`;
        }
        
        picker.innerHTML = `
            <div style="margin-bottom: 15px; text-align: center; font-weight: bold; color: #333;">
                انتخاب تاریخ شمسی
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                <div>
                    <label style="display: block; margin-bottom: 5px; font-size: 12px;">سال:</label>
                    <select id="jalali-year" style="width: 100%; padding: 5px; border: 1px solid #ccc; border-radius: 3px;">
                        ${yearOptions}
                    </select>
                </div>
                <div>
                    <label style="display: block; margin-bottom: 5px; font-size: 12px;">ماه:</label>
                    <select id="jalali-month" style="width: 100%; padding: 5px; border: 1px solid #ccc; border-radius: 3px;">
                        ${monthOptions}
                    </select>
                </div>
            </div>
            
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; font-size: 12px;">روز:</label>
                <select id="jalali-day" style="width: 100%; padding: 5px; border: 1px solid #ccc; border-radius: 3px;">
                    <!-- Days will be populated by JavaScript -->
                </select>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;">
                <button type="button" onclick="setJalaliToday(this)" 
                        style="background: #28a745; color: white; border: none; padding: 8px; border-radius: 3px; cursor: pointer; font-size: 11px;">
                    امروز
                </button>
                <button type="button" onclick="setJalaliDate(this)" 
                        style="background: #007cba; color: white; border: none; padding: 8px; border-radius: 3px; cursor: pointer; font-size: 11px;">
                    انتخاب
                </button>
                <button type="button" onclick="closeJalaliPicker(this)" 
                        style="background: #6c757d; color: white; border: none; padding: 8px; border-radius: 3px; cursor: pointer; font-size: 11px;">
                    بستن
                </button>
            </div>
        `;
        
        input.parentNode.appendChild(picker);
        
        // Update days when month/year changes
        const yearSelect = picker.querySelector('#jalali-year');
        const monthSelect = picker.querySelector('#jalali-month');
        const daySelect = picker.querySelector('#jalali-day');
        
        function updateDays() {
            const year = parseInt(yearSelect.value);
            const month = parseInt(monthSelect.value);
            let maxDays = 31;
            
            if (month <= 6) maxDays = 31;
            else if (month <= 11) maxDays = 30;
            else maxDays = isLeapYear(year) ? 30 : 29;
            
            daySelect.innerHTML = '';
            for (let d = 1; d <= maxDays; d++) {
                const option = document.createElement('option');
                option.value = d;
                option.textContent = d;
                if (d === jalaliToday.day && month === jalaliToday.month && year === jalaliToday.year) {
                    option.selected = true;
                }
                daySelect.appendChild(option);
            }
        }
        
        yearSelect.addEventListener('change', updateDays);
        monthSelect.addEventListener('change', updateDays);
        updateDays(); // Initial population
        
        return picker;
    }
    
    // Check if Jalali year is leap
    function isLeapYear(year) {
        const breaks = [
            -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
            1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178
        ];
        
        const gy = year + 1595;
        let leap = -14;
        let jp = breaks[0];
        
        let jump = 0;
        for (let j = 1; j <= 19; j++) {
            const jm = breaks[j];
            jump = jm - jp;
            if (year < jm) break;
            leap += Math.floor(jump / 33) * 8 + Math.floor(((jump % 33) / 4));
            jp = jm;
        }
        
        let n = year - jp;
        if (n < jump) {
            leap += Math.floor(n / 33) * 8 + Math.floor(((n % 33) + 3) / 4);
            if ((jump % 33) === 4 && (jump - n) === 4) leap++;
        }
        
        return (leap + 4) % 33 < 5;
    }
    
    // Improved Jalali to Gregorian conversion
    function toJalali(gy, gm, gd) {
        const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
        
        if (gy <= 1600) {
            let jy = 0; let gy2 = gy + 1; let days = 365 * gy + Math.floor((gy2 + 3) / 4) + Math.floor((gd)) + g_d_m[gm - 1] - 80 + 1;
            if (gm > 2) days += Math.floor((gy2 + 99) / 100) - Math.floor((gy2 + 399) / 400) - 2;
        } else {
            let jy = -1595; let gy2 = gy - 621; let days = 365 * gy + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) - 80 + gd + g_d_m[gm - 1];
        }
        
        let jy = Math.floor(days / 365.2422) + 979;
        days = Math.floor(days - (365.2422 * (jy - 979)));
        
        let jm, jd;
        if (days < 186) {
            jm = 1 + Math.floor(days / 31);
            jd = 1 + (days % 31);
        } else {
            jm = 7 + Math.floor((days - 186) / 30);
            jd = 1 + ((days - 186) % 30);
        }
        
        return { year: jy, month: jm, day: jd };
    }
    
    // Global functions for picker buttons
    window.setJalaliToday = function(button) {
        const picker = button.closest('.jalali-date-picker');
        const input = picker.previousElementSibling.previousElementSibling; // Skip icon
        const today = new Date();
        const jalaliToday = toJalali(today.getFullYear(), today.getMonth() + 1, today.getDate());
        input.value = `${jalaliToday.year}/${String(jalaliToday.month).padStart(2,'0')}/${String(jalaliToday.day).padStart(2,'0')}`;
        picker.style.display = 'none';
    };
    
    window.setJalaliDate = function(button) {
        const picker = button.closest('.jalali-date-picker');
        const input = picker.previousElementSibling.previousElementSibling; // Skip icon
        const year = picker.querySelector('#jalali-year').value;
        const month = picker.querySelector('#jalali-month').value;
        const day = picker.querySelector('#jalali-day').value;
        input.value = `${year}/${String(month).padStart(2,'0')}/${String(day).padStart(2,'0')}`;
        picker.style.display = 'none';
    };
    
    window.closeJalaliPicker = function(button) {
        const picker = button.closest('.jalali-date-picker');
        picker.style.display = 'none';
    };

    // Initialize Jalali date inputs
    function initJalaliInputs() {
        // Date inputs
        document.querySelectorAll('.jalali-date-input').forEach(input => {
            // Add calendar icon
            if (!input.nextElementSibling || !input.nextElementSibling.classList.contains('jalali-calendar-icon')) {
                const icon = document.createElement('span');
                icon.className = 'jalali-calendar-icon';
                icon.innerHTML = '📅';
                icon.style.cssText = `
                    cursor: pointer;
                    margin-left: 5px;
                    font-size: 16px;
                    user-select: none;
                `;
                input.parentNode.insertBefore(icon, input.nextSibling);
                
                // Create date picker
                const picker = createDatePicker(input);
                
                icon.addEventListener('click', function(e) {
                    e.preventDefault();
                    const isVisible = picker.style.display === 'block';
                    // Hide all other pickers
                    document.querySelectorAll('.jalali-date-picker').forEach(p => p.style.display = 'none');
                    picker.style.display = isVisible ? 'none' : 'block';
                });
            }
            
            input.addEventListener('input', function() {
                formatJalaliInput(this, false);
                const isValid = validateJalaliDate(this.value);
                updateValidationStyling(this, isValid);
            });
            
            input.addEventListener('blur', function() {
                const isValid = validateJalaliDate(this.value);
                updateValidationStyling(this, isValid);
            });
        });
        
        // DateTime inputs
        document.querySelectorAll('.jalali-datetime-input').forEach(input => {
            input.addEventListener('input', function() {
                formatJalaliInput(this, true);
                const isValid = validateJalaliDateTime(this.value);
                updateValidationStyling(this, isValid);
            });
            
            input.addEventListener('blur', function() {
                const isValid = validateJalaliDateTime(this.value);
                updateValidationStyling(this, isValid);
            });
        });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initJalaliInputs);
    } else {
        initJalaliInputs();
    }
    
    // Re-initialize for dynamically added content
    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('formset:added', initJalaliInputs);
    }
})();
