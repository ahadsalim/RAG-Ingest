/**
 * JavaScript for filtering parent LegalUnit options based on selected manifestation
 * Used in LegalUnit admin form
 */

// Simple approach without jQuery wrapper
document.addEventListener('DOMContentLoaded', function() {
    console.log('LegalUnit parent filter script loaded');
    
    // Wait a bit for Django admin to initialize
    setTimeout(function() {
        var $ = window.django && window.django.jQuery ? window.django.jQuery : window.jQuery;
        
        if (!$) {
            console.error('jQuery not found. Trying alternative approach...');
            
            // Fallback to vanilla JavaScript
            var manifestationSelect = document.getElementById('id_manifestation');
            var parentSelect = document.getElementById('id_parent');
            
            if (manifestationSelect && parentSelect) {
                console.log('Using vanilla JavaScript approach');
                manifestationSelect.addEventListener('change', function() {
                    updateParentOptionsVanilla(this.value, parentSelect);
                });
            }
            return;
        }
        
        console.log('jQuery found, using jQuery approach');
        
        // Get the manifestation and parent select elements
        var $manifestationSelect = $('#id_manifestation');
        var $parentSelect = $('#id_parent');
        
        console.log('Manifestation select found:', $manifestationSelect.length);
        console.log('Parent select found:', $parentSelect.length);
        
        if ($manifestationSelect.length && $parentSelect.length) {
            // Store the original selected parent value
            var originalParentValue = $parentSelect.val();
            console.log('Original parent value:', originalParentValue);
            
            // Function to update parent options
            function updateParentOptions() {
                var manifestationId = $manifestationSelect.val();
                console.log('Updating parent options for manifestation ID:', manifestationId);
                
                if (!manifestationId) {
                    $parentSelect.html('<option value="">---------</option>');
                    console.log('No manifestation selected, clearing parent options');
                    return;
                }
                
                // Get current object ID if editing
                var currentId = null;
                var urlParts = window.location.pathname.split('/');
                
                // Check if we're editing (URL contains change/)
                var isEditing = window.location.pathname.includes('/change/');
                if (isEditing) {
                    // Extract ID from URL like /admin/documents/legalunit/UUID/change/
                    for (var i = 0; i < urlParts.length; i++) {
                        if (urlParts[i] === 'legalunit' && i + 1 < urlParts.length) {
                            var potentialId = urlParts[i + 1];
                            // Check if it looks like a UUID (basic check)
                            if (potentialId && potentialId.length > 30 && potentialId.includes('-')) {
                                currentId = potentialId;
                                break;
                            }
                        }
                    }
                }
                
                console.log('Current ID detected:', currentId);
                
                console.log('Making AJAX request...');
                
                $.ajax({
                    url: '/ajax/documents/parent-options/',
                    data: {
                        'manifestation_id': manifestationId,
                        'current_id': currentId
                    },
                    dataType: 'json',
                    success: function(data) {
                        console.log('AJAX response received:', data);
                        $parentSelect.html('<option value="">---------</option>');
                        
                        var validParentFound = false;
                        
                        if (data.options && data.options.length > 0) {
                            $.each(data.options, function(index, option) {
                                $parentSelect.append(
                                    $('<option></option>').attr('value', option.value).text(option.text)
                                );
                                
                                // Check if original parent value is still valid
                                if (originalParentValue && option.value == originalParentValue) {
                                    validParentFound = true;
                                }
                            });
                            
                            // Restore original parent value if it's still valid
                            if (validParentFound) {
                                $parentSelect.val(originalParentValue);
                                console.log('Restored original parent value:', originalParentValue);
                            } else if (originalParentValue) {
                                console.log('Original parent value is no longer valid for this manifestation:', originalParentValue);
                            }
                        } else {
                            $parentSelect.append(
                                $('<option></option>').attr('value', '').text('هیچ واحد قانونی برای این انتشار سند یافت نشد')
                            );
                        }
                    },
                    error: function(xhr, status, error) {
                        console.error('AJAX Error:', error);
                        console.error('Status:', status);
                        console.error('Response:', xhr.responseText);
                    }
                });
            }
            
            // Bind change event
            $manifestationSelect.on('change', updateParentOptions);
            
            // Initialize if already selected
            if ($manifestationSelect.val()) {
                updateParentOptions();
            }
        }
    }, 500); // Wait 500ms for Django admin to initialize
});

// Vanilla JavaScript fallback function
function updateParentOptionsVanilla(manifestationId, parentSelect) {
    console.log('Using vanilla JS to update parent options for:', manifestationId);
    
    if (!manifestationId) {
        parentSelect.innerHTML = '<option value="">---------</option>';
        return;
    }
    
    // Use fetch API for AJAX
    var url = '/ajax/documents/parent-options/?manifestation_id=' + encodeURIComponent(manifestationId);
    
    fetch(url)
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            console.log('Vanilla JS AJAX response:', data);
            parentSelect.innerHTML = '<option value="">---------</option>';
            
            if (data.options && data.options.length > 0) {
                data.options.forEach(function(option) {
                    var optionElement = document.createElement('option');
                    optionElement.value = option.value;
                    optionElement.textContent = option.text;
                    parentSelect.appendChild(optionElement);
                });
            } else {
                var noOptionsElement = document.createElement('option');
                noOptionsElement.value = '';
                noOptionsElement.textContent = 'هیچ واحد قانونی برای این انتشار سند یافت نشد';
                parentSelect.appendChild(noOptionsElement);
            }
        })
        .catch(function(error) {
            console.error('Vanilla JS AJAX Error:', error);
        });
}
