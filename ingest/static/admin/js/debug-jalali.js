/**
 * Debug Jalali Date Picker - Very Simple Version
 */

console.log('🔍 Debug Jalali script loaded!');

// Wait for page to load completely
window.addEventListener('load', function() {
    console.log('🔍 Page loaded, searching for inputs...');
    
    // Find ALL input fields
    const allInputs = document.querySelectorAll('input[type="text"], input[type="date"]');
    console.log('🔍 Found', allInputs.length, 'text inputs total');
    
    allInputs.forEach(function(input, index) {
        console.log('🔍 Input', index, ':', input.className, input.placeholder, input.name);
        
        // Check if this looks like a date input
        const isDateInput = 
            input.className.includes('jalali') ||
            input.placeholder.includes('1402') ||
            input.placeholder.includes('1403') ||
            input.name.includes('date') ||
            (input.previousElementSibling && input.previousElementSibling.textContent.includes('تاریخ'));
            
        if (isDateInput) {
            console.log('✅ Adding picker to input:', input);
            addSimplePicker(input);
        }
    });
    
    // Also check after a delay for dynamically loaded content
    setTimeout(function() {
        console.log('🔍 Delayed search...');
        const newInputs = document.querySelectorAll('input[type="text"]:not([data-picker-added])');
        newInputs.forEach(function(input) {
            if (input.className.includes('jalali') || input.placeholder.includes('140')) {
                console.log('✅ Adding delayed picker to:', input);
                addSimplePicker(input);
            }
        });
    }, 2000);
});

function addSimplePicker(input) {
    // Mark as processed
    input.setAttribute('data-picker-added', 'true');
    
    // Create a simple button
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.innerHTML = '📅 تقویم';
    btn.style.cssText = `
        margin-left: 10px;
        padding: 5px 10px;
        background: #007cba;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
    `;
    
    // Add click handler
    btn.onclick = function() {
        console.log('📅 Calendar button clicked for:', input);
        
        const currentValue = input.value || '1403/01/15';
        const newDate = prompt('تاریخ شمسی را وارد کنید (مثال: 1403/05/20):', currentValue);
        
        if (newDate && newDate.trim()) {
            input.value = newDate.trim();
            console.log('✅ Date set to:', newDate);
            
            // Trigger events
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        }
    };
    
    // Insert button after input
    if (input.parentNode) {
        input.parentNode.insertBefore(btn, input.nextSibling);
        console.log('✅ Button added successfully');
    }
}

console.log('🔍 Debug Jalali script ready!');
