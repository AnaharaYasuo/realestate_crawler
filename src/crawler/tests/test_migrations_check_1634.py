from io import StringIO
from django.core.management import call_command


def test_no_pending_migrations():
    out = StringIO()
    call_command("makemigrations", check=True, dry_run=True, stdout=out)
