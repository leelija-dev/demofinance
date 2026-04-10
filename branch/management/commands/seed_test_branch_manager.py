from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from headquater.models import Branch
from branch.models import BranchManager

class Command(BaseCommand):
    help = 'Create a test branch manager for testing authentication'

    def handle(self, *args, **options):
        # First, create a test branch if it doesn't exist
        branch, created = Branch.objects.get_or_create(
            name='Test Branch',
            defaults={
                'address_line_1': '123 Test Street',
                'city': 'Test City',
                'state': 'Test State',
                'country': 'Test Country',
                'postal_code': '12345',
                'phone': '+1234567890',
                'email': 'testbranch@example.com',
                'is_active': True,
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Created test branch: {branch.name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Test branch already exists: {branch.name}')
            )

        # Create a test branch manager
        branch_manager, created = BranchManager.objects.get_or_create(
            email='branchmanager@example.com',
            defaults={
                'manager_id': 'BM001',
                'branch': branch,
                'first_name': 'Test',
                'last_name': 'Manager',
                'phone_number': '+1234567890',
                'address': '123 Manager Street, Test City',
                'password': 'testpass123',  # In production, this should be hashed
                'is_active': True,
                'gov_id_type': 'aadhar',
                'gov_id_number': '123456789012',
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created test branch manager: {branch_manager.email}\n'
                    f'Password: testpass123\n'
                    f'Manager ID: {branch_manager.manager_id}'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Test branch manager already exists: {branch_manager.email}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                '\nYou can now test the branch authentication system:\n'
                '1. Go to http://127.0.0.1/branch/\n'
                '2. Login with email: branchmanager@example.com\n'
                '3. Password: testpass123'
            )
        ) 