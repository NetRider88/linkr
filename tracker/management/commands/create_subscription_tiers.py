# tracker/management/commands/create_subscription_tiers.py

from django.core.management.base import BaseCommand
from tracker.models import SubscriptionTier
from decimal import Decimal

class Command(BaseCommand):
    help = 'Create initial subscription tiers'

    def handle(self, *args, **options):
        tiers = [
            {
                'name': 'FREE',
                'price': Decimal('0'),
                'yearly_price': Decimal('0'),
                'max_links': 5,
                'max_clicks': 1000,
                'retention_days': 30,
                'max_variables': 0,
                'allow_export': False,
                'description': 'Basic link tracking'
            },
            {
                'name': 'PRO',
                'price': Decimal('19'),
                'yearly_price': Decimal('182.40'),  # 20% off yearly (19 * 12 * 0.8)
                'max_links': 20,
                'max_clicks': 10000,
                'retention_days': 90,
                'max_variables': 0,
                'allow_export': True,
                'description': 'Advanced link tracking with exports'
            },
            {
                'name': 'BUSINESS',
                'price': Decimal('49'),
                'yearly_price': Decimal('470.40'),  # 20% off yearly (49 * 12 * 0.8)
                'max_links': 200,
                'max_clicks': 50000,
                'retention_days': 180,
                'max_variables': 10,
                'allow_export': True,
                'description': 'Full analytics suite with variables'
            },
            {
                'name': 'ENTERPRISE',
                'price': Decimal('99'),
                'yearly_price': Decimal('950.40'),  # 20% off yearly (99 * 12 * 0.8)
                'max_links': 1000,
                'max_clicks': 250000,
                'retention_days': 365,
                'max_variables': 20,
                'allow_export': True,
                'description': 'Unlimited analytics and customization'
            }
        ]
        
        for tier in tiers:
            # Try to get existing tier or create new one with all fields
            obj, created = SubscriptionTier.objects.get_or_create(
                name=tier['name'],
                defaults=tier  # Pass all fields as defaults
            )
            
            if not created:
                # Update existing tier with new values
                for key, value in tier.items():
                    setattr(obj, key, value)
                # Set removed features to False
                obj.api_access = False
                obj.custom_domain = False
                obj.team_members = 1
                obj.save()
            
            status = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f'{status} {tier["name"]} tier'))
        
        self.stdout.write(self.style.SUCCESS('Successfully created/updated all subscription tiers'))
