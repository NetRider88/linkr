from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tracker.models import UserProfile

class Command(BaseCommand):
    help = 'Create missing user profiles'

    def handle(self, *args, **kwargs):
        users_without_profiles = 0
        for user in User.objects.all():
            profile, created = UserProfile.objects.get_or_create(user=user)
            if created:
                users_without_profiles += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Created {users_without_profiles} missing user profiles'
            )
        )