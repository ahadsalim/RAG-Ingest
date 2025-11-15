"""
Domain service for managing LegalUnit changes with temporal validity.
Follows Akoma Ntoso semantics for legal document amendments.
"""
from django.db import transaction
from django.utils.timezone import localdate
from datetime import date, timedelta
from typing import Optional

from ..models import LegalUnit, LegalUnitChange, InstrumentExpression


class LegalUnitChangeService:
    """Service for applying changes to legal units with proper temporal semantics."""
    
    @staticmethod
    @transaction.atomic
    def apply_change(
        unit: LegalUnit,
        change_type: str,
        effective_date: date,
        *,
        superseded_by: Optional[LegalUnit] = None,
        source_expression: Optional[InstrumentExpression] = None,
        note: str = ""
    ) -> LegalUnitChange:
        """
        Apply a change to a legal unit with proper temporal validity updates.
        
        Args:
            unit: The legal unit to change
            change_type: Type of change (AMEND, REPEAL, SUBSTITUTE, ADD, REMOVE)
            effective_date: Date when the change takes effect
            superseded_by: New unit that replaces this one (for SUBSTITUTE)
            source_expression: Expression that introduces this change
            note: Additional notes about the change
            
        Returns:
            The created LegalUnitChange record
            
        Raises:
            ValueError: If invalid parameters are provided
        """
        # Validate change type
        if change_type not in [choice[0] for choice in LegalUnitChange.ChangeType.choices]:
            raise ValueError(f"Invalid change type: {change_type}")
        
        # Validate effective date
        if effective_date > localdate():
            raise ValueError("تاریخ اجرا نمی‌تواند در آینده باشد")
        
        # Validate superseded_by for SUBSTITUTE
        if change_type == LegalUnitChange.ChangeType.SUBSTITUTE and not superseded_by:
            raise ValueError("برای جایگزینی باید واحد جایگزین مشخص شود")
        
        # Create the change record
        change = LegalUnitChange.objects.create(
            unit=unit,
            change_type=change_type,
            effective_date=effective_date,
            source_expression=source_expression,
            superseded_by=superseded_by,
            note=note
        )
        
        # Apply temporal validity changes based on change type
        if change_type in [LegalUnitChange.ChangeType.REPEAL, LegalUnitChange.ChangeType.REMOVE]:
            # For repeal/remove, set valid_to to the day before effective date
            # (or same date if you prefer inclusive end dates)
            unit.valid_to = effective_date - timedelta(days=1)
            unit.save(update_fields=['valid_to'])
            
        elif change_type == LegalUnitChange.ChangeType.SUBSTITUTE:
            # For substitution, end validity of old unit and start validity of new unit
            unit.valid_to = effective_date - timedelta(days=1)
            unit.save(update_fields=['valid_to'])
            
            if superseded_by:
                superseded_by.valid_from = effective_date
                superseded_by.save(update_fields=['valid_from'])
        
        elif change_type == LegalUnitChange.ChangeType.ADD:
            # For addition, set valid_from if not already set
            if not unit.valid_from:
                unit.valid_from = effective_date
                unit.save(update_fields=['valid_from'])
        
        # For AMEND, we don't change validity dates by default
        # The amendment is recorded but the unit remains valid
        
        return change
    
    @staticmethod
    @transaction.atomic
    def repeal_unit(
        unit: LegalUnit,
        effective_date: date,
        *,
        source_expression: Optional[InstrumentExpression] = None,
        note: str = ""
    ) -> LegalUnitChange:
        """
        Convenience method to repeal a legal unit.
        
        Args:
            unit: The legal unit to repeal
            effective_date: Date when the repeal takes effect
            source_expression: Expression that introduces the repeal
            note: Additional notes about the repeal
            
        Returns:
            The created LegalUnitChange record
        """
        return LegalUnitChangeService.apply_change(
            unit=unit,
            change_type=LegalUnitChange.ChangeType.REPEAL,
            effective_date=effective_date,
            source_expression=source_expression,
            note=note
        )
    
    @staticmethod
    @transaction.atomic
    def substitute_unit(
        old_unit: LegalUnit,
        new_unit: LegalUnit,
        effective_date: date,
        *,
        source_expression: Optional[InstrumentExpression] = None,
        note: str = ""
    ) -> LegalUnitChange:
        """
        Convenience method to substitute one legal unit with another.
        
        Args:
            old_unit: The legal unit being replaced
            new_unit: The legal unit that replaces the old one
            effective_date: Date when the substitution takes effect
            source_expression: Expression that introduces the substitution
            note: Additional notes about the substitution
            
        Returns:
            The created LegalUnitChange record
        """
        return LegalUnitChangeService.apply_change(
            unit=old_unit,
            change_type=LegalUnitChange.ChangeType.SUBSTITUTE,
            effective_date=effective_date,
            superseded_by=new_unit,
            source_expression=source_expression,
            note=note
        )
    
    @staticmethod
    @transaction.atomic
    def amend_unit(
        unit: LegalUnit,
        effective_date: date,
        *,
        source_expression: Optional[InstrumentExpression] = None,
        note: str = ""
    ) -> LegalUnitChange:
        """
        Convenience method to record an amendment to a legal unit.
        
        Args:
            unit: The legal unit being amended
            effective_date: Date when the amendment takes effect
            source_expression: Expression that introduces the amendment
            note: Additional notes about the amendment
            
        Returns:
            The created LegalUnitChange record
        """
        return LegalUnitChangeService.apply_change(
            unit=unit,
            change_type=LegalUnitChange.ChangeType.AMEND,
            effective_date=effective_date,
            source_expression=source_expression,
            note=note
        )
    
    @staticmethod
    def get_unit_timeline(unit: LegalUnit) -> list:
        """
        Get the complete timeline of changes for a legal unit.
        
        Args:
            unit: The legal unit to get timeline for
            
        Returns:
            List of changes ordered by effective date
        """
        return list(unit.changes.all().order_by('effective_date'))
    
    @staticmethod
    def get_active_units_on_date(date_: date, work=None) -> 'QuerySet[LegalUnit]':
        """
        Get all legal units that were active on a specific date.
        
        Args:
            date_: The date to check
            work: Optional work to filter by
            
        Returns:
            QuerySet of active legal units
        """
        queryset = LegalUnit.objects.as_of(date_)
        if work:
            queryset = queryset.filter(work=work)
        return queryset
    
    @staticmethod
    def get_changes_between_dates(
        start_date: date, 
        end_date: date, 
        work=None
    ) -> 'QuerySet[LegalUnitChange]':
        """
        Get all changes that occurred between two dates.
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            work: Optional work to filter by
            
        Returns:
            QuerySet of changes in the date range
        """
        queryset = LegalUnitChange.objects.filter(
            effective_date__gte=start_date,
            effective_date__lte=end_date
        ).order_by('effective_date')
        
        if work:
            queryset = queryset.filter(unit__work=work)
            
        return queryset
    
    @staticmethod
    def validate_temporal_consistency(unit: LegalUnit) -> list:
        """
        Validate temporal consistency of a legal unit and its changes.
        
        Args:
            unit: The legal unit to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check basic validity interval
        if unit.valid_from and unit.valid_to and unit.valid_from > unit.valid_to:
            errors.append("تاریخ شروع اعتبار نمی‌تواند بعد از تاریخ پایان اعتبار باشد")
        
        # Check changes consistency
        changes = unit.changes.all().order_by('effective_date')
        
        for change in changes:
            # Check if change date is within unit's validity period
            if unit.valid_from and change.effective_date < unit.valid_from:
                errors.append(f"تغییر {change.get_change_type_display()} در تاریخ {change.effective_date} قبل از شروع اعتبار واحد است")
            
            # Check repeal/substitute logic
            if change.change_type in [LegalUnitChange.ChangeType.REPEAL, LegalUnitChange.ChangeType.SUBSTITUTE]:
                if not unit.valid_to:
                    errors.append(f"واحد با تغییر {change.get_change_type_display()} باید تاریخ پایان اعتبار داشته باشد")
                elif unit.valid_to >= change.effective_date:
                    errors.append(f"تاریخ پایان اعتبار باید قبل از تاریخ {change.get_change_type_display()} باشد")
        
        return errors
