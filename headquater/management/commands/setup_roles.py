from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from headquater.models import Role

class Command(BaseCommand):
    help = 'Sets up initial roles and permissions for the headquarters system'

    def handle(self, *args, **kwargs):
        # Define roles and their permissions
        roles_data = {
            'HQ Super Admin': {
                'description': 'The highest-level user at HQ with unrestricted access and full administrative control',
                'permissions': [
                    'add_user', 'change_user', 'delete_user', 'view_user',
                    'add_loan', 'change_loan', 'delete_loan', 'view_loan',
                    'add_document', 'change_document', 'delete_document', 'view_document',
                    'add_setting', 'change_setting', 'delete_setting', 'view_setting',
                ]
            },
            'Loan Officer': {
                'description': 'Responsible for reviewing and making decisions on loan applications',
                'permissions': [
                    'view_loan', 'change_loan', 'approve_loan', 'reject_loan',
                    'view_document', 'request_document',
                ]
            },
            'Risk & Compliance Officer': {
                'description': 'Handles fraud detection, regulatory checks, and compliance assessments',
                'permissions': [
                    'view_loan', 'verify_kyc', 'flag_risk', 'view_document',
                    'view_compliance_report',
                ]
            },
            'Finance Officer': {
                'description': 'Manages disbursement, repayments, and financial reports',
                'permissions': [
                    'view_loan', 'disburse_loan', 'view_repayment', 'manage_repayment',
                    'view_financial_report', 'generate_report',
                ]
            },
            'Auditor': {
                'description': 'Read-only access for internal or external auditing purposes',
                'permissions': [
                    'view_loan', 'view_document', 'view_repayment', 'view_audit_log',
                    'export_data',
                ]
            },
            'Call Verification Officer': {
                'description': 'Performs phone-based verification of customer details',
                'permissions': [
                    'view_loan', 'verify_customer', 'update_verification_status',
                ]
            },
            'IT/Admin Support': {
                'description': 'Responsible for system health and user account management',
                'permissions': [
                    'view_user', 'reset_password', 'view_system_health',
                    'provide_support',
                ]
            },
            'Data Analyst': {
                'description': 'Handles data analytics, KPIs, and operational reporting',
                'permissions': [
                    'view_loan', 'view_repayment', 'view_analytics',
                    'generate_report', 'export_data',
                ]
            }
        }

        # Create roles and assign permissions
        for role_name, role_info in roles_data.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={'description': role_info['description']}
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created role: {role_name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Role already exists: {role_name}'))

            # Clear existing permissions
            role.permissions.clear()

            # Add new permissions
            for perm_codename in role_info['permissions']:
                try:
                    perm = Permission.objects.get(codename=perm_codename)
                    role.permissions.add(perm)
                except Permission.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f'Permission not found: {perm_codename}')
                    )

        self.stdout.write(self.style.SUCCESS('Successfully set up roles and permissions')) 