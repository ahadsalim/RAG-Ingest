"""
Management command to check for duplicate admin template basenames.
This helps ensure template resolution is deterministic.
"""
import os
from collections import defaultdict
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Check for duplicate admin template basenames that could cause ambiguous template resolution'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--fail-on-duplicates',
            action='store_true',
            help='Exit with error code if duplicates are found (useful for CI)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about template locations',
        )
    
    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.verbose = options.get('verbose', False)
        self.fail_on_duplicates = options.get('fail_on_duplicates', False)
        
        # Find all admin templates
        admin_templates = self.find_admin_templates()
        
        # Check for duplicates
        duplicates = self.find_duplicates(admin_templates)
        
        # Report results
        self.report_results(admin_templates, duplicates)
        
        # Exit with error if requested and duplicates found
        if self.fail_on_duplicates and duplicates:
            raise CommandError(f"Found {len(duplicates)} duplicate template basenames")
    
    def find_admin_templates(self):
        """Find all admin templates in the project."""
        templates = []
        base_dir = Path(settings.BASE_DIR)
        
        # Search patterns for admin templates
        search_patterns = [
            '**/templates/admin/**/*.html',
            '**/admin/**/*.html',
        ]
        
        for pattern in search_patterns:
            for template_path in base_dir.glob(pattern):
                if template_path.is_file():
                    # Get relative path from project root
                    rel_path = template_path.relative_to(base_dir)
                    
                    # Extract the admin-relative path
                    path_parts = rel_path.parts
                    admin_index = None
                    
                    for i, part in enumerate(path_parts):
                        if part == 'admin':
                            admin_index = i
                            break
                    
                    if admin_index is not None:
                        # Get path relative to admin directory
                        admin_rel_path = '/'.join(path_parts[admin_index:])
                        templates.append({
                            'full_path': str(template_path),
                            'relative_path': str(rel_path),
                            'admin_path': admin_rel_path,
                            'basename': template_path.name,
                        })
        
        return templates
    
    def find_duplicates(self, templates):
        """Find templates with duplicate basenames."""
        basename_map = defaultdict(list)
        
        for template in templates:
            basename_map[template['basename']].append(template)
        
        # Return only basenames with multiple templates
        duplicates = {
            basename: template_list 
            for basename, template_list in basename_map.items() 
            if len(template_list) > 1
        }
        
        return duplicates
    
    def report_results(self, templates, duplicates):
        """Report the results of the template check."""
        if self.verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(f"Found {len(templates)} admin templates")
            )
        
        if self.verbose:
            self.stdout.write("\nAll admin templates:")
            for template in sorted(templates, key=lambda t: t['admin_path']):
                self.stdout.write(f"  {template['admin_path']} -> {template['relative_path']}")
        
        if duplicates:
            self.stdout.write(
                self.style.WARNING(f"\nFound {len(duplicates)} duplicate template basenames:")
            )
            
            for basename, template_list in duplicates.items():
                self.stdout.write(f"\n  {basename}:")
                for template in template_list:
                    self.stdout.write(f"    - {template['relative_path']}")
                
                # Warn about potential resolution issues
                self.stdout.write(
                    self.style.WARNING(
                        f"    ⚠️  Django will use the first template found in TEMPLATE_DIRS order"
                    )
                )
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✅ No duplicate template basenames found")
            )
        
        # Show template directory order
        if self.verbose or duplicates:
            self.stdout.write("\nTemplate directory resolution order:")
            template_dirs = settings.TEMPLATES[0]['DIRS']
            for i, template_dir in enumerate(template_dirs, 1):
                self.stdout.write(f"  {i}. {template_dir}")
            
            if settings.TEMPLATES[0]['APP_DIRS']:
                self.stdout.write("  + App directories (in INSTALLED_APPS order)")
    
    def get_template_resolution_order(self):
        """Get the order in which Django resolves templates."""
        from django.template.loader import get_template
        from django.template.backends.django import DjangoTemplates
        
        # This is a simplified version - actual resolution is more complex
        template_dirs = []
        
        # Add TEMPLATE_DIRS
        for backend in settings.TEMPLATES:
            if backend['BACKEND'] == 'django.template.backends.django.DjangoTemplates':
                template_dirs.extend(backend['DIRS'])
        
        # Add app directories if APP_DIRS is True
        if settings.TEMPLATES[0].get('APP_DIRS', False):
            from django.apps import apps
            for app_config in apps.get_app_configs():
                app_template_dir = Path(app_config.path) / 'templates'
                if app_template_dir.exists():
                    template_dirs.append(str(app_template_dir))
        
        return template_dirs
