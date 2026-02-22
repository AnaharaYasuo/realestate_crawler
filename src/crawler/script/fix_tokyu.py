from django.db import connection
from package.models.tokyu import TokyuMansion

def run():
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES LIKE 'tokyu_mansion'")
        exists = cursor.fetchone()
        if exists:
            print("Table tokyu_mansion already exists.")
            return

    print("Creating table tokyu_mansion...")
    with connection.schema_editor() as schema_editor:
        try:
            schema_editor.create_model(TokyuMansion)
            print("Table tokyu_mansion created successfully.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run()
