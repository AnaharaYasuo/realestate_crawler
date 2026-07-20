import os

def main():
    cron_env_path = "/app/.cron_env"
    with open(cron_env_path, "w", encoding="utf-8") as f:
        for k, v in os.environ.items():
            # escape double quotes and backslashes in values
            escaped_v = v.replace("\\", "\\\\").replace("\"", "\\\"")
            f.write(f'export {k}="{escaped_v}"\n')

if __name__ == "__main__":
    main()
