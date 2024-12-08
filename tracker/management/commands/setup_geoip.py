import os
import shutil
import urllib.request
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Downloads and sets up GeoIP2 databases'

    def handle(self, *args, **options):
        # Create GeoIP directory if it doesn't exist
        if not os.path.exists(settings.GEOIP_PATH):
            os.makedirs(settings.GEOIP_PATH)

        # URLs for the free GeoLite2 databases
        urls = {
            'GeoLite2-City.mmdb': 'https://raw.githubusercontent.com/P3TERX/GeoLite.mmdb/download/GeoLite2-City.mmdb',
            'GeoLite2-Country.mmdb': 'https://raw.githubusercontent.com/P3TERX/GeoLite.mmdb/download/GeoLite2-Country.mmdb'
        }

        for filename, url in urls.items():
            target_path = os.path.join(settings.GEOIP_PATH, filename)
            
            self.stdout.write(f'Downloading {filename}...')
            try:
                urllib.request.urlretrieve(url, target_path)
                self.stdout.write(self.style.SUCCESS(f'Successfully downloaded {filename}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to download {filename}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS('GeoIP2 setup complete!')) 