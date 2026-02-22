#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys

def main():
    """Run administrative tasks."""
    # Add src and crawler dirs to sys.path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    crawler_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(base_dir)
    sys.path.append(crawler_dir)
    
    # Manually configure settings using the existing module logic
    try:
        from crawler import realestateSettings
        realestateSettings.configure()
    except Exception as e:
        print(f"Failed to configure settings: {e}")
        sys.exit(1)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
