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
        from crawler.package.utils.db_safety import assert_production_db_safety
        subcmd = sys.argv[1] if len(sys.argv) > 1 else ""
        assert_production_db_safety(subcmd)
    except Exception as e:
        print(f"Failed to configure settings or safety check failed: {e}")
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
