from django.core.management.base import BaseCommand
from headquater.models import Headquarters

class Command(BaseCommand):
    help = 'Fixes headquarters admin permissions for a user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username to fix permissions for')

    def handle(self, *args, **options):
        username = options['username']

        try:
            # Get the user
            user = Headquarters.objects.get(username=username)
            
            # Print current status
            self.stdout.write(f"Current status for {username}:")
            self.stdout.write(f"is_headquater_admin: {user.is_headquater_admin}")
            self.stdout.write(f"is_staff: {user.is_staff}")
            self.stdout.write(f"is_superuser: {user.is_superuser}")
            self.stdout.write(f"is_active: {user.is_active}")
            
            # Fix permissions
            user.is_headquater_admin = True
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()
            
            self.stdout.write(self.style.SUCCESS(f'\nSuccessfully updated permissions for {username}'))
            self.stdout.write("\nNew status:")
            self.stdout.write(f"is_headquater_admin: {user.is_headquater_admin}")
            self.stdout.write(f"is_staff: {user.is_staff}")
            self.stdout.write(f"is_superuser: {user.is_superuser}")
            self.stdout.write(f"is_active: {user.is_active}")

        except Headquarters.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User {username} does not exist in Headquarters model')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error fixing permissions: {str(e)}')
            ) 