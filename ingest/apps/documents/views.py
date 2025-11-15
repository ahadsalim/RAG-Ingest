"""
Views for documents app.
"""

from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import LegalUnit


@login_required
@csrf_exempt
@require_GET
def get_parent_options(request):
    """
    AJAX view to get parent LegalUnit options filtered by manifestation.
    Used in admin interface to dynamically filter parent choices.
    """
    manifestation_id = request.GET.get('manifestation_id')
    
    print(f"DEBUG: get_parent_options called with manifestation_id: {manifestation_id}")
    
    if not manifestation_id:
        print("DEBUG: No manifestation_id provided")
        return JsonResponse({'options': []})
    
    try:
        # Get LegalUnits for the selected manifestation
        legal_units = LegalUnit.objects.filter(
            manifestation_id=manifestation_id
        ).select_related('work', 'expr', 'manifestation').order_by('path_label')
        
        print(f"DEBUG: Found {legal_units.count()} legal units for manifestation {manifestation_id}")
        
        # Exclude the current object if editing (to prevent circular reference)
        current_id = request.GET.get('current_id')
        if current_id:
            legal_units = legal_units.exclude(pk=current_id)
            print(f"DEBUG: Excluded current object {current_id}, remaining: {legal_units.count()}")
        
        # Build options list
        options = []
        for unit in legal_units:
            # Use path_label if available, otherwise use unit_type + number
            if unit.path_label:
                option_text = unit.path_label
            else:
                option_text = f"{unit.get_unit_type_display()} {unit.number}".strip()
            
            # Add status indicator if unit is not active
            if not unit.is_active:
                option_text += " (غیرفعال)"
            
            options.append({
                'value': unit.pk,
                'text': option_text
            })
            print(f"DEBUG: Added option - {unit.pk}: {option_text} (Active: {unit.is_active})")
        
        print(f"DEBUG: Returning {len(options)} options")
        return JsonResponse({'options': options})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
