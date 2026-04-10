from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from headquater.models import Headquarters

class Command(BaseCommand):
    help = 'Converts an existing superuser to a Headquarters admin user'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username of the superuser to convert')

    def handle(self, *args, **options):
        username = options['username']
        User = get_user_model()

        try:
            # Get the existing superuser
            user = User.objects.get(username=username)
            
            # Check if a Headquarters user already exists with this email
            try:
                hq_user = Headquarters.objects.get(email=user.email)
                # Update existing Headquarters user
                hq_user.username = user.username
                hq_user.password = user.password
                hq_user.is_headquater_admin = True
                hq_user.is_staff = True
                hq_user.is_superuser = True
                hq_user.is_active = True
                hq_user.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully updated existing Headquarters user {username}')
                )
            except Headquarters.DoesNotExist:
                # Create new Headquarters user
                hq_user = Headquarters.objects.create(
                    username=user.username,
                    email=user.email,
                    password=user.password,
                    is_headquater_admin=True,
                    is_staff=True,
                    is_superuser=True,
                    is_active=True
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created new Headquarters admin {username}')
                )

        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User {username} does not exist')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error converting user: {str(e)}')
            ) 