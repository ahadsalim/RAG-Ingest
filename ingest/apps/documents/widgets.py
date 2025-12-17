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
        
        # نمایش دکمه حذف والد فقط اگر والد انتخاب شده باشد
        clear_btn_style = "display:inline-block;" if value else "display:none;"
        
        # HTML output
        html = f'''
        <div class="parent-autocomplete-wrapper" style="position: relative; display: inline-block;">
            <input type="hidden" name="{name}" id="id_{name}" value="{value or ''}" />
            <input type="text" 
                   id="id_{name}_search" 
                   class="parent-autocomplete-search"
                   placeholder="{attrs.get('placeholder', 'تایپ کنید...')}"
                   value="{parent_display}"
                   autocomplete="off"
                   style="{attrs.get('style', '')}"
                   data-manifestation-id="{self.manifestation_id or ''}"
            /><button type="button" id="id_{name}_clear" style="{clear_btn_style}margin-right:8px;padding:4px 10px;background:#dc3545;color:#fff;border:none;border-radius:4px;cursor:pointer;vertical-align:middle;">✕</button>
            <div id="id_{name}_results" class="parent-search-dropdown" style="display:none;"></div>
        </div>
        
        <script>
        (function() {{
            const searchInput = document.getElementById('id_{name}_search');
            const hiddenInput = document.getElementById('id_{name}');
            const clearBtn = document.getElementById('id_{name}_clear');
            let resultsDiv = document.getElementById('id_{name}_results');
            let searchTimeout;
            
            if (!searchInput) return;
            
            // انتقال resultsDiv به body برای جلوگیری از مشکل overflow:hidden
            if (resultsDiv) {{
                document.body.appendChild(resultsDiv);
                resultsDiv.style.position = 'fixed';
                resultsDiv.style.zIndex = '99999';
            }}
            
            // دکمه حذف والد
            if (clearBtn) {{
                clearBtn.addEventListener('click', function() {{
                    hiddenInput.value = '';
                    searchInput.value = '';
                    clearBtn.style.display = 'none';
                }});
            }}
            
            // جستجو با تاخیر
            searchInput.addEventListener('input', function() {{
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
                
                fetch(url)
                    .then(response => response.json())
                    .then(data => {{
                        displayResults(data.results);
                    }})
                    .catch(error => {{
                        console.error('Fetch Error:', error);
                    }});
            }}
            
            // نمایش نتایج
            function displayResults(results) {{
                
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
                
                // اضافه کردن event listener به هر آیتم - فقط mousedown برای انتخاب
                resultsDiv.querySelectorAll('.autocomplete-item').forEach(function(item) {{
                    item.addEventListener('mousedown', function(e) {{
                        e.preventDefault();
                        e.stopPropagation();
                        selectParent(this.dataset.id, this.dataset.display);
                    }});
                }});
            }}
            
            // انتخاب والد
            function selectParent(id, display) {{
                hiddenInput.value = id;
                searchInput.value = display;
                hideResults();
                if (clearBtn) clearBtn.style.display = 'inline-block';
            }}
            
            function hideResults() {{
                resultsDiv.style.setProperty('display', 'none', 'important');
            }}
            
            // بستن نتایج فقط با Escape
            searchInput.addEventListener('keydown', function(e) {{
                if (e.key === 'Escape') {{
                    hideResults();
                }}
            }});
            
            // بستن با کلیک خارج - با تأخیر برای اجازه دادن به انتخاب آیتم
            searchInput.addEventListener('blur', function() {{
                setTimeout(hideResults, 300);
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
