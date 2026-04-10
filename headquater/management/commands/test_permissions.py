from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from headquater.models import Headquarters

class Command(BaseCommand):
    help = 'Test the permission system'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Test Django superuser
        superusers = User.objects.filter(is_superuser=True)
        if superusers.exists():
            superuser = superusers.first()
            self.stdout.write(f"\n=== Django Superuser Test ===")
            self.stdout.write(f"Username: {superuser.username}")
            self.stdout.write(f"Email: {superuser.email}")
            self.stdout.write(f"Is Superuser: {superuser.is_superuser}")
            
            # Test permission methods
            if hasattr(superuser, 'is_super_admin'):
                self.stdout.write(f"Is Super Admin: {superuser.is_super_admin()}")
            if hasattr(superuser, 'can_access_user_management'):
                self.stdout.write(f"Can Access User Management: {superuser.can_access_user_management()}")
            if hasattr(superuser, 'can_access_role_management'):
                self.stdout.write(f"Can Access Role Management: {superuser.can_access_role_management()}")
        
        # Test Headquarters users
        hq_users = Headquarters.objects.all()
        if hq_users.exists():
            self.stdout.write(f"\n=== Headquarters Users Test ===")
            for user in hq_users:
                self.stdout.write(f"\nUsername: {user.username}")
                self.stdout.write(f"Email: {user.email}")
                self.stdout.write(f"Is Superuser: {user.is_superuser}")
                self.stdout.write(f"Is Super Admin: {user.is_super_admin()}")
                self.stdout.write(f"Can Access User Management: {user.can_access_user_management()}")
                self.stdout.write(f"Can Access Role Management: {user.can_access_role_management()}")
                self.stdout.write(f"Role: {user.get_role_name()}")
        
        self.stdout.write(self.style.SUCCESS('\nPermission test completed!')) 