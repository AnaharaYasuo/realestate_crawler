import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
import realestateSettings
realestateSettings.configure()
from django.db import connection

def run_cleansing():
    with connection.cursor() as cur:
        # 1. Update homes_investment_apartment where tatemonoMensekiStr has 専有 or バルコニー
        cur.execute(
            "UPDATE homes_investment_apartment "
            "SET propertyType = 'Mansion', tochiMenseki = NULL, tochiMensekiStr = '' "
            "WHERE propertyType = 'Apartment' "
            "  AND (tatemonoMensekiStr LIKE '%専有%' OR tatemonoMensekiStr LIKE '%バルコニー%');"
        )
        print("Updated homes_investment_apartment records to Mansion:", cur.rowcount)

        # 2. Update PropertyEvaluation for these updated records
        cur.execute(
            "UPDATE property_evaluation pe "
            "JOIN homes_investment_apartment h ON pe.property_id = h.id AND pe.company = 'homes' "
            "SET pe.property_type = 'mansion', pe.first_stage_predicted_price = NULL, "
            "    pe.second_stage_predicted_price = NULL, pe.is_first_stage_passed = 0 "
            "WHERE h.propertyType = 'Mansion' AND pe.property_type = 'investmentapartment';"
        )
        print("Updated property_evaluation records to mansion:", cur.rowcount)

        # 3. Mark needs_recrawl=1 for asking price <= 0 records in Sumifu
        for table, ptype in [('sumifu_mansion', 'mansion'), ('sumifu_kodate', 'kodate'), ('sumifu_tochi', 'tochi')]:
            cur.execute(
                f"UPDATE property_evaluation pe "
                f"JOIN {table} s ON pe.property_id = s.id AND pe.company = 'sumifu' AND pe.property_type = '{ptype}' "
                f"SET pe.needs_recrawl = 1, pe.data_quality_issue = 'invalid_price_zero' "
                f"WHERE s.price <= 0;"
            )
            print(f"Marked {table} 0 price as needs_recrawl:", cur.rowcount)

if __name__ == "__main__":
    run_cleansing()
