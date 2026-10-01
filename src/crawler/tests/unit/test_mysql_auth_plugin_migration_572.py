"""Unit tests for MySQL auth plugin migration to caching_sha2_password (Issue #572).

Tests:
1. Verify terraform/database.tf does not contain deprecated 'mysql_native_password'.
2. Verify terraform/proxysql.tf configures use_ssl=1 for backend MySQL connection.
3. Verify requirements.txt contains cryptography and mysqlclient for caching_sha2_password support.
"""

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[4]



class TestMysqlAuthPluginMigration572:
    """Verifies that mysql_native_password is removed and caching_sha2_password is supported."""

    def test_database_tf_removes_mysql_native_password(self):
        """Verify that default_authentication_plugin = 'mysql_native_password' is deleted from database.tf."""
        database_tf_path = REPO_ROOT / "terraform" / "database.tf"
        assert database_tf_path.exists(), f"database.tf not found at {database_tf_path}"

        content = database_tf_path.read_text(encoding="utf-8")
        assert "mysql_native_password" not in content, (
            "terraform/database.tf should not contain 'mysql_native_password' flag (Issue #572)"
        )
        assert 'name  = "default_authentication_plugin"' not in content, (
            "terraform/database.tf should not configure default_authentication_plugin explicitly"
        )

    def test_proxysql_tf_enables_use_ssl_for_backend(self):
        """Verify that proxysql.tf configures use_ssl=1 for backend Cloud SQL server."""
        proxysql_tf_path = REPO_ROOT / "terraform" / "proxysql.tf"
        assert proxysql_tf_path.exists(), f"proxysql.tf not found at {proxysql_tf_path}"

        content = proxysql_tf_path.read_text(encoding="utf-8")
        # Ensure use_ssl=1 is set in mysql_servers block
        assert re.search(r"use_ssl\s*=\s*1", content), (
            "terraform/proxysql.tf must configure 'use_ssl=1' for mysql_servers (Issue #572)"
        )
        # Ensure use_ssl=0 is NOT present in mysql_servers
        assert not re.search(r"use_ssl\s*=\s*0", content), (
            "terraform/proxysql.tf must not contain 'use_ssl=0' in mysql_servers (Issue #572)"
        )

    def test_requirements_contains_caching_sha2_dependencies(self):
        """Verify that requirements.txt has cryptography and mysqlclient for caching_sha2_password."""
        req_path = REPO_ROOT / "src" / "crawler" / "requirements.txt"
        assert req_path.exists(), f"requirements.txt not found at {req_path}"

        content = req_path.read_text(encoding="utf-8")
        assert re.search(r"^cryptography==", content, re.MULTILINE), (
            "requirements.txt must contain 'cryptography' for caching_sha2_password authentication"
        )
        assert re.search(r"^mysqlclient==", content, re.MULTILINE), (
            "requirements.txt must contain 'mysqlclient'"
        )
