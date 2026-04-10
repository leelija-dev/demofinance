from django.core.management.base import BaseCommand
from branch.models import BranchPermission, BranchRole
from headquater.models import Branch
from collections import OrderedDict

class Command(BaseCommand):
    help = 'Sets up initial branch permissions and roles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--truncate',
            action='store_true',
            help='Truncate all permissions and roles before seeding'
        )

    def handle(self, *args, **options):
        self.stdout.write('Setting up branch permissions...')
        
        if options['truncate']:
            self.stdout.write(self.style.WARNING('Truncating all permissions and roles...'))
            BranchPermission.objects.all().delete()
            BranchRole.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Successfully truncated all data'))
            return
        self.stdout.write('Setting up branch permissions...')
        

        # Define common permissions for branch operations with groups
        PERMISSION_GROUPS = [
            ('Branch Operations', {
                'group': 'branch',
                'permissions': [
                    ('view_branch_settings', 'Can view settings'),
                    ('change_branch_settings', 'Can change settings'),
                    ('view_branch_wallet', 'Can view wallet'),
                    ('change_branch_wallet', 'Can change wallet'),
                ]
            }),
            ('Role Management', {
                'group': 'role',
                'permissions': [
                    ('view_branch_role', 'Can view role'),
                    ('add_branch_role', 'Can add role'),
                    ('change_branch_role', 'Can change role'),
                    ('delete_branch_role', 'Can delete role'),
                ]
            }),
            ('Staff Management', {
                'group': 'staff',
                'permissions': [
                    ('view_branch_employee', 'Can view employee'),
                    ('add_branch_employee', 'Can add employee'),
                    ('change_branch_employee', 'Can change employee'),
                    ('delete_branch_employee', 'Can delete employee'),
                ]
            }),
            ('Agent Management', {
                'group': 'agent',
                'permissions': [
                    ('add_agent', 'Can add agent'),
                    ('view_agent', 'Can view agent'),
                    ('change_agent', 'Can change agent'),
                    ('delete_agent', 'Can delete agent'),
                ]
            }),
            
            ('Customer Management', {
                'group': 'customer',
                'permissions': [
                    ('view_customers', 'Can view customer information'),
                    ('add_customer', 'Can add new customers'),
                    ('edit_customer', 'Can edit customer information'),
                ]
            }),
            ('Loan Management', {
                'group': 'loan',
                'permissions': [
                    ('view_loans', 'Can view loan applications'),
                    ('add_loan', 'Can add new loan applications'),
                    ('approve_loan', 'Can approve loan applications'),
                    ('reject_loan', 'Can reject loan applications'),
                    ('disburse_loan', 'Can disburse approved loans'),
                    ('close_loan', 'Can close loan'),
                ]
            }),
            ('EMI Management', {
                'group': 'emi',
                'permissions': [
                    ('view_emis', 'Can view emis'),
                    ('collect_emi', 'Can collect emi'),
                    ('receive_emi', 'Can receive/approve emi'),
                    ('reject_emi', 'Can reject emis'),
                ]
            }),
            ('Fund Management', {
                'group': 'payment',
                'permissions': [
                    ('view_fund', 'Can view fund'),
                    ('add_fund_record', 'Can credit/debit fund'),
                ]
            }),
            ('Reports', {
                'group': 'report',
                'permissions': [
                    ('view_reports', 'Can view reports'),
                    ('export_reports', 'Can export reports'),
                ]
            }),
        ]

        # Create permissions
        created_permissions = {}
        for group_name, group_data in PERMISSION_GROUPS:
            group_code = group_data['group']
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n{group_name}:"))
            
            for codename, name in group_data['permissions']:
                perm, created = BranchPermission.objects.update_or_create(
                    codename=codename,
                    defaults={
                        'name': name,
                        'group': group_code
                    }
                )
                created_permissions[codename] = perm
                status = self.style.SUCCESS('CREATED') if created else self.style.NOTICE('UPDATED')
                self.stdout.write(f"  {name}: {status}")

        # Define roles and their permissions
        ROLES = {
            'Branch Manager': [
                # Branch
                'view_branch_settings', 'change_branch_settings',
                'view_branch_wallet', 'change_branch_wallet',
                # Role
                'view_branch_role',
                # Staff
                'add_branch_employee', 'view_branch_employee', 'change_branch_employee',
                # Agent
                'add_agent', 'view_agent', 'change_agent',
                # Loan
                'view_loans', 'add_loan', 'approve_loan', 'reject_loan', 'disburse_loan',
                # Customer
                'view_customers', 'add_customer', 'edit_customer',
                # Payment
                'view_fund', 'add_fund_record',
                # Reports
                'view_reports', 'export_reports',
            ],
            'Loan Officer': [
                'view_loans', 'add_loan',
                'view_customers', 'add_customer', 'edit_customer',
                'add_fund_record', 'view_reports'
            ],

            'Accountant': [
                'view_loans', 'view_customers', 'view_fund', 'add_fund_record',
                'view_reports', 'export_reports'
            ]
        }

        # Create roles and assign permissions
        self.stdout.write(self.style.MIGRATE_HEADING("\nSetting up roles:"))
        for role_name, permission_codenames in ROLES.items():
            role, created = BranchRole.objects.get_or_create(
                name=role_name,
                defaults={'description': f'{role_name} role with appropriate permissions'}
            )
            
            # Get permission objects that exist
            permissions_to_add = []
            for codename in permission_codenames:
                if codename in created_permissions:
                    permissions_to_add.append(created_permissions[codename])
                else:
                    self.stdout.write(
                        self.style.WARNING(f"  Warning: Permission '{codename}' not found for role '{role_name}'")
                    )
            
            # Clear and set new permissions
            role.permissions.clear()
            if permissions_to_add:
                role.permissions.add(*permissions_to_add)
            
            status = self.style.SUCCESS('CREATED') if created else self.style.NOTICE('UPDATED')
            self.stdout.write(f"\n{role_name} - {status}")
            self.stdout.write(f"  Assigned {len(permissions_to_add)} permissions")
            if not created:
                self.stdout.write(self.style.SUCCESS("  ✓ Permissions updated"))

        self.stdout.write(self.style.SUCCESS('\nSuccessfully set up branch permissions and roles!'))