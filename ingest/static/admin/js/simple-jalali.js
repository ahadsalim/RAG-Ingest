/**
 * Simple Jalali Date Picker
 */

(function() {
    'use strict';
    
    // Simple Jalali date conversion
    function toJalali(gy, gm, gd) {
        const jy = gy - 621;
        return { year: jy, month: gm, day: gd };
    }
    
    // Add date picker to Jalali inputs
    function addDatePicker(input) {
        // Create calendar button
        const button = document.createElement('button');
        button.type = 'button';
        button.innerHTML = '📅';
        button.style.cssText = `
            margin-left: 5px;
            padding: 5px;
            border: 1px solid #ccc;
            background: #f8f9fa;
            cursor: pointer;
            border-radius: 3px;
        `;
        
        // Insert button after input
        input.parentNode.insertBefore(button, input.nextSibling);
        
        // Add click handler
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Simple date selection
            const today = new Date();
            const jalaliToday = toJalali(today.getFullYear(), today.getMonth() + 1, today.getDate());
            
            const selectedDate = prompt(
                'تاریخ شمسی را وارد کنید (فرمت: 1402/01/15):', 
                `${jalaliToday.year}/${String(jalaliToday.month).padStart(2,'0')}/${String(jalaliToday.day).padStart(2,'0')}`
            );
            
            if (selectedDate) {
                input.value = selectedDate;
                // Trigger change event
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    }
    
    // Initialize when DOM is ready
    function initJalaliInputs() {
        console.log('Initializing Jalali inputs...');
        
        // Find all Jalali date inputs with multiple selectors
        const selectors = [
            '.jalali-date-input', 
            '.jalali-datetime-input',
            'input[class*="jalali"]',
            'input[placeholder*="1402"]',
            'input[placeholder*="1403"]'
        ];
        
        let inputs = [];
        selectors.forEach(selector => {
            const found = document.querySelectorAll(selector);
            inputs = inputs.concat(Array.from(found));
        });
        
        // Remove duplicates
        inputs = inputs.filter((input, index, self) => self.indexOf(input) === index);
        
        console.log('Found', inputs.length, 'Jalali inputs');
        
        inputs.forEach(function(input) {
            // Skip if already processed
            if (input.nextElementSibling && input.nextElementSibling.innerHTML === '📅') {
                return;
            }
            
            console.log('Adding picker to input:', input);
            addDatePicker(input);
        });
        
        // Also try to find inputs by their labels
        const labels = document.querySelectorAll('label');
        labels.forEach(label => {
            if (label.textContent.includes('شمسی') || label.textContent.includes('تاریخ')) {
                const input = document.getElementById(label.getAttribute('for')) || 
                             label.nextElementSibling;
                if (input && input.tagName === 'INPUT' && input.type !== 'hidden') {
                    if (!input.nextElementSibling || input.nextElementSibling.innerHTML !== '📅') {
                        console.log('Adding picker to labeled input:', input);
                        addDatePicker(input);
                    }
                }
            }
        });
    }
    
    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initJalaliInputs);
    } else {
        initJalaliInputs();
    }
    
    // Also initialize on window load (fallback)
    window.addEventListener('load', initJalaliInputs);
    
    // Re-initialize for dynamically added content
    if (typeof django !== 'undefined' && django.jQuery) {
        django.jQuery(document).on('formset:added', initJalaliInputs);
    }
    
})();
