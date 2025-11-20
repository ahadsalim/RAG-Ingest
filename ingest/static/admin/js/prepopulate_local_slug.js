(function($) {
    'use strict';
    
    // Custom slug generation for InstrumentWork
    function generateLocalSlug() {
        var docTypeField = $('#id_doc_type');
        var titleField = $('#id_title_official');
        var slugField = $('#id_local_slug');
        
        if (docTypeField.length && titleField.length && slugField.length) {
            function updateSlug() {
                var docType = docTypeField.find('option:selected').text().trim();
                var title = titleField.val().trim();
                
                if (docType && title && docType !== '---------') {
                    // Convert Persian/Arabic title to English transliteration
                    var englishTitle = transliterateToEnglish(title);
                    
                    // Create slug: doc_type - short_english_title
                    var slug = docType.toLowerCase() + '-' + englishTitle;
                    
                    // Clean and format slug
                    slug = slug
                        .replace(/[^\w\s-]/g, '') // Remove special chars except spaces and hyphens
                        .replace(/\s+/g, '-')     // Replace spaces with hyphens
                        .replace(/-+/g, '-')      // Replace multiple hyphens with single
                        .toLowerCase()
                        .substring(0, 90);       // Limit length
                    
                    slugField.val(slug);
                }
            }
            
            // Bind events
            docTypeField.on('change', updateSlug);
            titleField.on('input blur', updateSlug);
        }
    }
    
    // Simple Persian/Arabic to English transliteration
    function transliterateToEnglish(text) {
        var persianToEnglish = {
            'ا': 'a', 'آ': 'aa', 'ب': 'b', 'پ': 'p', 'ت': 't', 'ث': 's',
            'ج': 'j', 'چ': 'ch', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'z',
            'ر': 'r', 'ز': 'z', 'ژ': 'zh', 'س': 's', 'ش': 'sh', 'ص': 's',
            'ض': 'z', 'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f',
            'ق': 'gh', 'ک': 'k', 'گ': 'g', 'ل': 'l', 'م': 'm', 'ن': 'n',
            'و': 'v', 'ه': 'h', 'ی': 'y', 'ء': '', 'ئ': 'y', 'ؤ': 'v',
            '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5',
            '۶': '6', '۷': '7', '۸': '8', '۹': '9'
        };
        
        var result = '';
        for (var i = 0; i < text.length; i++) {
            var char = text[i];
            if (persianToEnglish[char]) {
                result += persianToEnglish[char];
            } else if (char.match(/[a-zA-Z0-9\s]/)) {
                result += char;
            }
        }
        
        // Shorten long titles
        var words = result.split(/\s+/);
        if (words.length > 4) {
            result = words.slice(0, 4).join(' ');
        }
        
        return result.trim();
    }
    
    // Initialize when DOM is ready
    $(document).ready(function() {
        generateLocalSlug();
    });
    
})(django.jQuery);
