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
    
    def __init__(self, manifestation_id=None, model_name='lunit', *args, **kwargs):
        self.manifestation_id = manifestation_id
        self.model_name = model_name  # 'lunit' or 'legalunit'
        super().__init__(*args, **kwargs)
        self.attrs.update({
            'class': 'parent-autocomplete vTextField',
            'placeholder': 'نوع واحد (باب/بخش، فصل، ماده، ...) یا شماره',
            'autocomplete': 'off',
            'style': 'width: 500px; display: inline-block;',
            'data-model-name': model_name
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
        <div class="parent-autocomplete-wrapper" style="position: relative; display: inline-flex; align-items: center; gap: 8px;">
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
            <button type="button" 
                    id="id_{name}_clear" 
                    class="parent-clear-btn"
                    title="حذف والد (بدون والد)"
                    style="
                        padding: 6px 12px;
                        background: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 12px;
                        white-space: nowrap;
                    "
            >🗑️ بدون والد</button>
            <div id="id_{name}_results" class="autocomplete-results" style="
                display: none;
                position: absolute;
                top: 100%;
                left: 0;
                width: 600px;
                background: white;
                border: 1px solid #ccc;
                border-top: none;
                max-height: 400px;
                overflow-y: auto;
                z-index: 1000;
                box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            "></div>
        </div>
        
        <script>
        (function() {{
            const searchInput = document.getElementById('id_{name}_search');
            const hiddenInput = document.getElementById('id_{name}');
            const resultsDiv = document.getElementById('id_{name}_results');
            let searchTimeout;
            
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
                const modelName = searchInput.dataset.modelName || 'lunit';
                if (!manifestationId) {{
                    console.error('Manifestation ID not found');
                    return;
                }}
                
                const url = '/admin/documents/' + modelName + '/search-parents/?q=' + encodeURIComponent(query) + '&manifestation_id=' + manifestationId;
                
                fetch(url)
                    .then(response => response.json())
                    .then(data => {{
                        displayResults(data.results);
                    }})
                    .catch(error => {{
                        console.error('Error:', error);
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
                resultsDiv.style.display = 'block';
                
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
            
            // دکمه پاک کردن والد
            const clearBtn = document.getElementById('id_{name}_clear');
            if (clearBtn) {{
                clearBtn.addEventListener('click', function() {{
                    hiddenInput.value = '';
                    searchInput.value = '';
                    resultsDiv.style.display = 'none';
                    // نشان دادن پیام تایید
                    searchInput.placeholder = '✓ والد حذف شد - ذخیره کنید';
                    searchInput.style.borderColor = '#28a745';
                    setTimeout(function() {{
                        searchInput.placeholder = '{attrs.get('placeholder', 'تایپ کنید...')}';
                        searchInput.style.borderColor = '';
                    }}, 2000);
                }});
            }}
        }})();
        </script>
        '''
        
        return mark_safe(html)
    
    class Media:
        css = {
            'all': ()
        }
        js = ()
