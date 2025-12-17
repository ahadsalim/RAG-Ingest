"""
Custom widgets for documents app.
"""
from django import forms
from django.urls import reverse
from django.utils.safestring import mark_safe


class ParentAutocompleteWidget(forms.TextInput):
    """
    Widget برای autocomplete والد با جستجوی AJAX.
    """
    template_name = 'admin/documents/widgets/parent_autocomplete.html'
    
    def __init__(self, manifestation_id=None, *args, **kwargs):
        self.manifestation_id = manifestation_id
        super().__init__(*args, **kwargs)
        self.attrs.update({
            'class': 'parent-autocomplete vTextField',
            'placeholder': 'نوع واحد (باب/بخش، فصل، ماده، ...) یا شماره',
            'autocomplete': 'off',
            'style': 'width: 500px; display: inline-block;'
        })
    
    def render(self, name, value, attrs=None, renderer=None):
        """Render widget با JavaScript برای autocomplete."""
        if attrs is None:
            attrs = {}
        
        attrs.update(self.attrs)
        
        # دریافت اطلاعات والد فعلی
        parent_display = ''
        if value:
            try:
                from .models import LegalUnit
                parent = LegalUnit.objects.get(pk=value)
                parent_display = f"{parent.get_unit_type_display()} {parent.number}"
                if parent.content:
                    parent_display += f" - {parent.content[:50]}"
            except:
                pass
        
        # HTML output
        html = f'''
        <div class="parent-autocomplete-wrapper" style="position: relative;">
            <input type="hidden" name="{name}" id="id_{name}" value="{value or ''}" />
            <input type="text" 
                   id="id_{name}_search" 
                   class="parent-autocomplete-search"
                   placeholder="{attrs.get('placeholder', 'تایپ کنید...')}"
                   value="{parent_display}"
                   autocomplete="off"
                   style="{attrs.get('style', '')}"
                   data-manifestation-id="{self.manifestation_id or ''}"
            />
            <div id="id_{name}_results" class="autocomplete-results" style="
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                width: 600px;
                background: red;
                border: 2px solid blue;
                max-height: 400px;
                overflow-y: auto;
                z-index: 1000;
                box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            ">TEST CONTENT</div>
        </div>
        
        <script>
        (function() {{
            console.log('=== Parent Autocomplete Script Loaded ===');
            const searchInput = document.getElementById('id_{name}_search');
            const hiddenInput = document.getElementById('id_{name}');
            let resultsDiv = document.getElementById('id_{name}_results');
            let searchTimeout;
            
            console.log('searchInput:', searchInput);
            console.log('manifestationId:', searchInput ? searchInput.dataset.manifestationId : 'N/A');
            
            if (!searchInput) {{
                console.error('searchInput not found!');
                return;
            }}
            
            // انتقال resultsDiv به body برای جلوگیری از مشکل overflow:hidden
            if (resultsDiv) {{
                document.body.appendChild(resultsDiv);
                resultsDiv.style.position = 'fixed';
                resultsDiv.style.zIndex = '99999';
                console.log('resultsDiv moved to body');
            }}
            
            // جستجو با تاخیر
            searchInput.addEventListener('input', function() {{
                console.log('Input event fired, value:', this.value);
                clearTimeout(searchTimeout);
                const query = this.value.trim();
                
                if (query.length < 1) {{
                    resultsDiv.style.display = 'none';
                    return;
                }}
                
                searchTimeout = setTimeout(function() {{
                    searchParents(query);
                }}, 300);
            }});
            
            // جستجو در والدها
            function searchParents(query) {{
                const manifestationId = searchInput.dataset.manifestationId;
                if (!manifestationId) {{
                    console.error('Manifestation ID not found');
                    return;
                }}
                
                const url = '/admin/documents/lunit/search-parents/?q=' + encodeURIComponent(query) + '&manifestation_id=' + manifestationId;
                
                console.log('Fetching URL:', url);
                fetch(url)
                    .then(response => response.json())
                    .then(data => {{
                        console.log('Got results:', data.results ? data.results.length : 0);
                        displayResults(data.results);
                    }})
                    .catch(error => {{
                        console.error('Fetch Error:', error);
                    }});
            }}
            
            // نمایش نتایج
            function displayResults(results) {{
                console.log('displayResults called, resultsDiv:', resultsDiv);
                console.log('resultsDiv parent:', resultsDiv ? resultsDiv.parentElement : 'N/A');
                
                if (results.length === 0) {{
                    resultsDiv.innerHTML = '<div style="padding: 10px; color: #999;">نتیجه‌ای یافت نشد</div>';
                    resultsDiv.style.display = 'block';
                    return;
                }}
                
                let html = '';
                results.forEach(function(item) {{
                    html += '<div class="autocomplete-item" data-id="' + item.id + '" data-display="' + item.display + '" style="';
                    html += 'padding: 10px 12px;';
                    html += 'cursor: pointer;';
                    html += 'border-bottom: 1px solid #eee;';
                    html += 'white-space: nowrap;';
                    html += 'overflow: hidden;';
                    html += 'text-overflow: ellipsis;';
                    html += '">';
                    html += '<div style="font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">' + item.display + '</div>';
                    if (item.content) {{
                        html += '<div style="color: #666; font-size: 11px; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">' + item.content + '</div>';
                    }}
                    html += '</div>';
                }});
                
                resultsDiv.innerHTML = html;
                
                // تنظیم موقعیت بر اساس searchInput
                const rect = searchInput.getBoundingClientRect();
                let leftPos = rect.left;
                
                // اگر از سمت راست خارج می‌شود، تنظیم کن
                if (leftPos + 600 > window.innerWidth) {{
                    leftPos = window.innerWidth - 620;
                }}
                if (leftPos < 10) leftPos = 10;
                
                // استفاده از setProperty با important برای override کردن CSS خارجی
                resultsDiv.style.setProperty('display', 'block', 'important');
                resultsDiv.style.setProperty('position', 'fixed', 'important');
                resultsDiv.style.setProperty('top', rect.bottom + 'px', 'important');
                resultsDiv.style.setProperty('left', leftPos + 'px', 'important');
                resultsDiv.style.setProperty('width', Math.min(600, window.innerWidth - 40) + 'px', 'important');
                resultsDiv.style.setProperty('background', 'white', 'important');
                resultsDiv.style.setProperty('z-index', '999999', 'important');
                resultsDiv.style.setProperty('max-height', '400px', 'important');
                resultsDiv.style.setProperty('overflow-y', 'auto', 'important');
                resultsDiv.style.setProperty('border', '1px solid #ccc', 'important');
                resultsDiv.style.setProperty('box-shadow', '0 4px 8px rgba(0,0,0,0.15)', 'important');
                
                console.log('Results displayed at top:', rect.bottom, 'left:', leftPos, 'viewport:', window.innerWidth);
                
                // اضافه کردن event listener به هر آیتم
                resultsDiv.querySelectorAll('.autocomplete-item').forEach(function(item) {{
                    item.addEventListener('click', function() {{
                        selectParent(this.dataset.id, this.dataset.display);
                    }});
                    
                    item.addEventListener('mouseenter', function() {{
                        this.style.backgroundColor = '#f0f0f0';
                    }});
                    
                    item.addEventListener('mouseleave', function() {{
                        this.style.backgroundColor = 'white';
                    }});
                }});
            }}
            
            // انتخاب والد
            function selectParent(id, display) {{
                hiddenInput.value = id;
                searchInput.value = display;
                resultsDiv.style.display = 'none';
            }}
            
            // بستن نتایج با کلیک خارج
            document.addEventListener('click', function(e) {{
                if (!searchInput.contains(e.target) && !resultsDiv.contains(e.target)) {{
                    resultsDiv.style.display = 'none';
                }}
            }});
            
            // پاک کردن با فشار Escape
            searchInput.addEventListener('keydown', function(e) {{
                if (e.key === 'Escape') {{
                    resultsDiv.style.display = 'none';
                }}
            }});
        }})();
        </script>
        '''
        
        return mark_safe(html)
    
    class Media:
        css = {
            'all': ()
        }
        js = ()
