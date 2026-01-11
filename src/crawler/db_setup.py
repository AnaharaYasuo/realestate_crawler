import os
import sys
import django
from django.core.management import call_command
import realestateSettings

def setup_db():
    print("Configuring Django settings...")
    realestateSettings.configure()
    # django.setup() is called inside realestateSettings.configure() at the end, 
    # but we can ensure it's ready.
    
    print("Running migrations...")
    try:
        call_command('makemigrations', 'package')
        call_command('migrate')
        print("Migrations completed successfully.")
    except Exception as e:
        print(f"Error running migrations: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_db()
