import os
import sys
import django
from django.core.management import call_command
import realestateSettings

def show_migrations():
    print("Configuring Django settings...")
    realestateSettings.configure()
    
    print("Showing migrations for 'package'...")
    try:
        call_command('showmigrations', 'package')
    except Exception as e:
        print(f"Error showing migrations: {e}")

if __name__ == "__main__":
    show_migrations()
ー