/**
 * JavaScript برای کنترل نمایش بخش تغییرات LegalUnit
 */

document.addEventListener('DOMContentLoaded', function() {
    // اضافه کردن checkbox برای فعال/غیرفعال کردن بخش تغییرات
    addChangesToggle();
    
    // مدیریت نمایش فرم‌های تغییرات
    manageChangesDisplay();
});

function addChangesToggle() {
    // پیدا کردن بخش تغییرات
    const changesSection = document.querySelector('.inline-group[id*="legalunitchange"]');
    if (!changesSection) return;
    
    // ایجاد checkbox برای کنترل
    const toggleContainer = document.createElement('div');
    toggleContainer.className = 'changes-toggle-container';
    toggleContainer.style.cssText = `
        background: #f8f8f8;
        border: 1px solid #ddd;
        padding: 10px;
        margin-bottom: 10px;
        border-radius: 4px;
        font-family: 'Vazirmatn', 'Tahoma', sans-serif;
    `;
    
    const toggleLabel = document.createElement('label');
    toggleLabel.style.cssText = `
        display: flex;
        align-items: center;
        cursor: pointer;
        font-weight: bold;
        color: #333;
    `;
    
    const toggleCheckbox = document.createElement('input');
    toggleCheckbox.type = 'checkbox';
    toggleCheckbox.id = 'changes-toggle';
    toggleCheckbox.style.cssText = `
        margin-left: 8px;
        transform: scale(1.2);
    `;
    
    const toggleText = document.createElement('span');
    toggleText.textContent = 'این بند قانونی تغییرات داشته است';
    
    toggleLabel.appendChild(toggleCheckbox);
    toggleLabel.appendChild(toggleText);
    toggleContainer.appendChild(toggleLabel);
    
    // اضافه کردن توضیحات
    const description = document.createElement('p');
    description.style.cssText = `
        margin: 8px 0 0 0;
        font-size: 12px;
        color: #666;
        line-height: 1.4;
    `;
    description.textContent = 'با فعال کردن این گزینه، می‌توانید تغییرات احتمالی این بند قانونی را ثبت کنید. هر قانون ممکن است چندین بار تغییر کند.';
    toggleContainer.appendChild(description);
    
    // قرار دادن قبل از بخش تغییرات
    changesSection.parentNode.insertBefore(toggleContainer, changesSection);
    
    // مخفی کردن اولیه بخش تغییرات
    changesSection.style.display = 'none';
    
    // اضافه کردن event listener
    toggleCheckbox.addEventListener('change', function() {
        if (this.checked) {
            changesSection.style.display = 'block';
            // باز کردن اولین fieldset
            const firstFieldset = changesSection.querySelector('.collapse');
            if (firstFieldset) {
                firstFieldset.classList.remove('collapsed');
            }
        } else {
            changesSection.style.display = 'none';
        }
    });
    
    // بررسی اینکه آیا تغییرات موجود وجود دارد
    const existingChanges = changesSection.querySelectorAll('.has_original');
    if (existingChanges.length > 0) {
        toggleCheckbox.checked = true;
        changesSection.style.display = 'block';
    }
}

function manageChangesDisplay() {
    // اضافه کردن استایل‌های بهتر برای فرم‌های تغییرات
    const changeInlines = document.querySelectorAll('.inline-group[id*="legalunitchange"] .inline-related');
    
    changeInlines.forEach((inline, index) => {
        // اضافه کردن شماره تغییر
        const header = inline.querySelector('h3');
        if (header && !header.textContent.includes('تغییر #')) {
            header.textContent = `تغییر #${index + 1} - ${header.textContent}`;
        }
        
        // اضافه کردن کلاس برای استایل بهتر
        inline.classList.add('change-form');
        
        // استایل‌دهی
        inline.style.cssText = `
            border: 1px solid #e1e1e1;
            border-radius: 6px;
            margin-bottom: 15px;
            background: #fafafa;
        `;
    });
}

// اضافه کردن استایل‌های CSS
const style = document.createElement('style');
style.textContent = `
    .changes-toggle-container {
        font-family: 'Vazirmatn', 'Tahoma', sans-serif !important;
        direction: rtl;
        text-align: right;
    }
    
    .change-form .form-row {
        direction: rtl;
        text-align: right;
    }
    
    .change-form label {
        font-family: 'Vazirmatn', 'Tahoma', sans-serif;
    }
    
    .inline-group[id*="legalunitchange"] h2 {
        background: #417690;
        color: white;
        padding: 10px 15px;
        margin: 0;
        border-radius: 6px 6px 0 0;
        font-family: 'Vazirmatn', 'Tahoma', sans-serif;
    }
    
    .inline-group[id*="legalunitchange"] .module {
        border-radius: 0 0 6px 6px;
    }
`;
document.head.appendChild(style);
