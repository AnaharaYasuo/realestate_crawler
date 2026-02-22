import os
import sys
import django
from django.core.management import call_command
import realestateSettings

def run_migrations():
    print("Configuring Django settings...")
    realestateSettings.configure()
    
    print("Making migrations for 'package'...")
    call_command('makemigrations', 'package')
    
    print("Applying migrations...")
    call_command('migrate')

if __name__ == "__main__":
    run_migrations()
