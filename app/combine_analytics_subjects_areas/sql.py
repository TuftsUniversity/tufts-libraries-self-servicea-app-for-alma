import os
import pandas as pd
import requests
import json
import re
from flask import current_app, send_file, request
from werkzeug.utils import secure_filename
import io
from io import BytesIO




class SQLProcessor:
    def __init__(self, sql_input_1, sql_input_2, join_type):
        self.sql_input_1 = sql_input_1
        self.sql_input_2 = sql_input_2
        self.join_type = join_type

    def process_sql(self):
        # Extract and rename fields from sql_input_1
        sql_1_fields = self.extract_fields(self.sql_input_1)
        sql_2_fields = self.extract_fields(self.sql_input_2)

        # Construct the combined SQL query
        combined_sql = f"SELECT \n"
        combined_sql += ",\n".join(sql_1_fields + sql_2_fields)
        combined_sql += "\nFROM (\n" + self.sql_input_1 + "\n) cr\n"
        combined_sql += f"{self.join_type.upper()} JOIN (\n" + self.sql_input_2 + "\n) physical_items\n"
        combined_sql += "ON cr.MMS_Id = physical_items.MMS_Id OR cr.OCLC = physical_items.Related_OCLC\n"

        return combined_sql

    def extract_fields(self, sql_input):
        # Extract fields and rename them
        fields = []
        for line in sql_input.splitlines():
            if "saw_" in line:
                field_name = line.split("saw_")[1].split(",")[0].strip()
                original_field = line.split('"')[1]
                new_field_name = original_field.replace(" ", "_").replace(".", "").replace("(", "").replace(")", "")
                fields.append(f"{original_field} AS {new_field_name}")
        return fields
