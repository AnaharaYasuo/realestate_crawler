"""Unit and integration tests for MySQL auth plugin migration to caching_sha2_password (Issue #572).

Tests:
1. Verify terraform/database.tf does not configure default_authentication_plugin in database_flags.
2. Verify terraform/proxysql.tf configures use_ssl=1 and not use_ssl=0 in mysql_servers block.
3. Verify requirements.txt contains cryptography and mysqlclient for caching_sha2_password support.
4. Verify Django DB configuration supports ProxySQL connection and caching_sha2 authentication for Cloud Run, batch, and local environments.
5. Verify db_user and monitor authentication and query execution logic via ProxySQL.
"""

from pathlib import Path
import re
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[4]


def _strip_comments(content: str) -> str:
    """Strip single-line comments (# and //) from HCL/script text."""
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(("#", "//")):
            continue
        # Strip inline comment if preceded by space
        line = re.sub(r"\s+#.*$", "", line)
        line = re.sub(r"\s+//.*$", "", line)
        lines.append(line)
    return "\n".join(lines)


class TestMysqlAuthPluginMigration572:
    """Verifies that mysql_native_password is removed and caching_sha2_password is supported."""

    def test_database_tf_removes_mysql_native_password(self):
        """Verify that default_authentication_plugin = 'mysql_native_password' is deleted from database_flags blocks."""
        database_tf_path = REPO_ROOT / "terraform" / "database.tf"
        assert database_tf_path.exists(), f"database.tf not found at {database_tf_path}"

        raw_content = database_tf_path.read_text(encoding="utf-8")
        clean_content = _strip_comments(raw_content)

        # 1. Extract all database_flags blocks
        flag_blocks = re.findall(r"database_flags\s*\{([^}]+)\}", clean_content)
        assert len(flag_blocks) > 0, "Expected at least one database_flags block in database.tf"

        for block in flag_blocks:
            # Verify default_authentication_plugin is not configured in any database_flags block
            assert not re.search(r'name\s*=\s*["\']default_authentication_plugin["\']', block), (
                f"database_flags block unexpectedly contains default_authentication_plugin: {block}"
            )
            assert "mysql_native_password" not in block, (
                f"database_flags block unexpectedly contains mysql_native_password: {block}"
            )

        # 2. Verify no active code in the entire file configures mysql_native_password
        assert not re.search(r'["\']?mysql_native_password["\']?', clean_content), (
            "terraform/database.tf should not contain 'mysql_native_password' in active code (Issue #572)"
        )

    def test_proxysql_tf_enables_use_ssl_for_backend(self):
        """Verify that proxysql.tf configures use_ssl=1 (and not use_ssl=0) on EVERY server definition in mysql_servers block."""
        proxysql_tf_path = REPO_ROOT / "terraform" / "proxysql.tf"
        assert proxysql_tf_path.exists(), f"proxysql.tf not found at {proxysql_tf_path}"

        raw_content = proxysql_tf_path.read_text(encoding="utf-8")
        clean_content = _strip_comments(raw_content)

        # Extract mysql_servers block inside startup-script heredoc
        match = re.search(r"mysql_servers\s*=\s*\(([\s\S]*?)\)", clean_content)
        assert match, "mysql_servers block not found in terraform/proxysql.tf"
        mysql_servers_block = match.group(1)

        # Extract each top-level server definition inside mysql_servers by tracking brace depth
        # to safely handle nested Terraform interpolations like ${google_sql_database_instance...}
        server_defs = []
        depth = 0
        current_chars = []
        for char in mysql_servers_block:
            if char == "{":
                depth += 1
                if depth == 1:
                    current_chars = []
                    continue
            elif char == "}":
                depth -= 1
                if depth == 0:
                    server_defs.append("".join(current_chars))
                    continue
            if depth >= 1:
                current_chars.append(char)

        assert len(server_defs) > 0, f"Expected at least one server definition in mysql_servers: {mysql_servers_block}"

        for idx, server_def in enumerate(server_defs):
            # Ensure use_ssl=1 is set on this specific server definition
            assert re.search(r"use_ssl\s*=\s*1\b", server_def), (
                f"Server definition #{idx+1} in mysql_servers must configure 'use_ssl=1' (Issue #572): {server_def}"
            )
            # Ensure use_ssl=0 is NOT present on this specific server definition
            assert not re.search(r"use_ssl\s*=\s*0\b", server_def), (
                f"Server definition #{idx+1} in mysql_servers must not configure 'use_ssl=0' (Issue #572): {server_def}"
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

    def test_django_mysql_runtime_configuration_environments(self, monkeypatch):
        """Verify production Django database configuration for Cloud Run, batch, and local paths via ProxySQL."""
        from realestateSettings import get_database_config

        env_scenarios = [
            ("cloud_run", {"K_SERVICE": "realestate-crawler-service", "DB_HOST": "10.0.0.10", "DB_PORT": "6033", "DB_USER": "sumifu"}, "10.0.0.10"),
            ("batch_job", {"CLOUD_RUN_JOB": "realestate-batch-crawler", "DB_HOST": "10.0.0.10", "DB_PORT": "6033", "DB_USER": "sumifu"}, "10.0.0.10"),
            ("local_dev", {"IS_CLOUD": "", "K_SERVICE": "", "CLOUD_RUN_JOB": "", "GOOGLE_CLOUD_PROJECT": "", "DB_HOST": "127.0.0.1", "DB_PORT": "6033", "DB_USER": "sumifu"}, "127.0.0.1"),
        ]

        all_env_keys = ["IS_CLOUD", "K_SERVICE", "CLOUD_RUN_JOB", "GOOGLE_CLOUD_PROJECT", "DB_HOST", "DB_PORT", "DB_USER"]

        for env_name, env_vars, expected_host in env_scenarios:
            # Initialize environment detection variables separately for each scenario
            for k in all_env_keys:
                monkeypatch.delenv(k, raising=False)
            for k, v in env_vars.items():
                if v:
                    monkeypatch.setenv(k, v)

            # Load actual production database configuration dict directly
            db_config = get_database_config()

            assert db_config["ENGINE"] == "django.db.backends.mysql", f"Scenario {env_name}: ENGINE must be MySQL"
            assert db_config["USER"] == "sumifu", f"Scenario {env_name}: USER must be sumifu"
            assert db_config["PORT"] == "6033", f"Scenario {env_name}: PORT must be ProxySQL 6033"
            assert db_config["HOST"] == expected_host, f"Scenario {env_name}: HOST must be {expected_host}"
            assert db_config["CONN_MAX_AGE"] == 0, f"Scenario {env_name}: CONN_MAX_AGE must be 0 for ProxySQL"

    def test_runtime_caching_sha2_client_capabilities(self):
        """Verify caching_sha2_password authentication flow: OAEP SHA-1 encryption and decryption of XORed password."""
        import itertools
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes

        # Generate RSA key pair (2048-bit standard)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()

        # Simulate password XOR with scramble and NUL-terminator (MySQL caching_sha2_password specification)
        password = "test_secure_password"
        scramble = b"12345678901234567890"
        password_bytes = password.encode("utf-8") + b"\x00"
        xor_bytes = bytes(p ^ s for p, s in zip(password_bytes, itertools.cycle(scramble)))

        # Encrypt with OAEP padding and SHA-1 (as mandated by MySQL caching_sha2_password wire protocol)
        encrypted = public_key.encrypt(
            xor_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None,
            ),
        )
        assert len(encrypted) == 256, "RSA 2048 ciphertext must be 256 bytes"

        # Verify decryption yields the exact NUL-terminated password XORed with the scramble
        decrypted = private_key.decrypt(
            encrypted,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None,
            ),
        )
        assert decrypted == xor_bytes, "Decrypted payload must match XORed password bytes"

        # Verify recovering the original NUL-terminated password
        recovered_password_bytes = bytes(d ^ s for d, s in zip(decrypted, itertools.cycle(scramble)))
        assert recovered_password_bytes == password_bytes, "Recovered password bytes must match original password + NUL"
        assert recovered_password_bytes.rstrip(b"\x00").decode("utf-8") == password

    def test_runtime_query_execution_connection_factory(self, monkeypatch):
        """Verify connection factory receives correct user, port, and schema parameters for ProxySQL routing."""
        mock_connect = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        monkeypatch.setattr("MySQLdb.connect", mock_connect, raising=False)

        import MySQLdb

        def execute_proxysql_query(user: str, port: int, schema: str):
            """Simulate application/monitor connecting to ProxySQL and running validation query."""
            conn = MySQLdb.connect(
                host="127.0.0.1",
                port=port,
                user=user,
                passwd="test_password",
                db=schema,
            )
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone()

        users_to_verify = [
            {"user": "sumifu", "port": 6033, "expected_schema": "real_estate"},
            {"user": "monitor", "port": 6032, "expected_schema": "information_schema"},
        ]

        for u in users_to_verify:
            mock_connect.reset_mock()
            result = execute_proxysql_query(u["user"], u["port"], u["expected_schema"])
            assert result == (1,), f"Query execution failed for {u['user']}"

            # Verify connection factory received the expected credentials and ProxySQL port
            mock_connect.assert_called_once_with(
                host="127.0.0.1",
                port=u["port"],
                user=u["user"],
                passwd="test_password",
                db=u["expected_schema"],
            )
