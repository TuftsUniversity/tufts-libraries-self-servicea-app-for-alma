import re

class SQLProcessor:
    def __init__(self, sql_input_1, sql_input_2, join_type, join_field_left=None, join_field_right=None):
        self.sql_input_1 = sql_input_1
        self.sql_input_2 = sql_input_2
        self.join_type = join_type
        self.left_alias = self.get_table_alias(sql_input_1)
        self.right_alias = self.get_table_alias(sql_input_2)
        self.join_field_left = join_field_left or f'{self.left_alias}.MMS_Id'
        self.join_field_right = join_field_right or f'{self.right_alias}.MMS_Id'

    def get_table_alias(self, sql_input):
        match = re.search(r'FROM\s+"([^"]+)"', sql_input, re.IGNORECASE)
        if not match:
            return "unknown_alias"
        table_name = match.group(1)
        return re.sub(r'[^a-z0-9_]', '', table_name.lower().replace(" ", "_"))

    def extract_fields(self, sql_input, table_alias):
        """
        Extracts aliased fields from OBIEE-style SELECTs using 's_X' pattern
        and constructs table_alias.FieldAlias for top-level SELECT.
        """
        fields = []
        in_select = False

        for line in sql_input.splitlines():
            stripped = line.strip()

            if stripped.upper().startswith("SELECT"):
                in_select = True
                continue
            if in_select and stripped.upper().startswith("FROM"):
                break

            # Match: optional schema + "Dim"."Field" s_X
            match = re.match(r'(?:\"[^\"]+\"\.)?(\"[^\"]+\"\.\"[^\"]+\")\s+s_\d+', stripped)
            if match:
                dim_field = match.group(1)  # e.g. "Physical Item Details"."Barcode"
                field_name = dim_field.split('.')[-1].strip('"')
                clean_name = re.sub(r'[^A-Za-z0-9_]', '', field_name.replace(" ", "_"))
                fields.append(f'{table_alias}.{clean_name}')

        return fields

    def process_sql(self):
        try:
            # Step 1: Normalize aliases in SQL inputs
            self.sql_input_1 = self.update_aliases(self.sql_input_1)
            self.sql_input_2 = self.update_aliases(self.sql_input_2)

            # Step 2: Extract top-level SELECT fields with aliased form
            left_fields = self.extract_fields(self.sql_input_1, self.left_alias)
            right_fields = self.extract_fields(self.sql_input_2, self.right_alias)

            select_fields = left_fields + right_fields

            # if not select_fields:
            #     return "-- ERROR: No fields extracted from input SQL."

            select_clause = "SELECT\n   " + ",\n   ".join(select_fields)

            # Step 3: Join body
            joined_sql = f"""
    {select_clause}
    FROM (
    {self.sql_input_1}
    ) {self.left_alias}
    {self.join_type.upper()} JOIN (
    {self.sql_input_2}
    ) {self.right_alias}
    ON {self.join_field_left} = {self.join_field_right}
    """.strip()

            # Step 4: Remove malformed "SELECT\nFROM (" if somehow present
            if re.search(r"SELECT\s*FROM\s*\(", joined_sql, flags=re.IGNORECASE):
                joined_sql = re.sub(r'^SELECT\s*FROM\s*\(', '', joined_sql, flags=re.IGNORECASE | re.MULTILINE)

                joined_sql = joined_sql.strip()
                #return "-- ERROR: Malformed SELECT clause. No fields extracted."

            return joined_sql

        except Exception as e:
            return f"-- ERROR processing SQL: {str(e)}"



    def update_aliases(self, sql_input):
        """
        Updates internal field aliases (e.g., s_1) with clean aliases like MMS_Id based on field names.
        """
        updated_lines = []
        in_select = False

        for line in sql_input.splitlines():
            stripped = line.strip()

            # Skip s_0 line
            if re.match(r'^0\s+s_0,?$', stripped):
                continue
            if stripped.upper().startswith("SELECT"):
                in_select = True
                updated_lines.append(line)
                print(line)
                continue
            if in_select and stripped.upper().startswith("FROM"):
                in_select = False
                updated_lines.append(line)
                print(line)
                continue
            
            match = re.match(r'^(.*?)(\"[^\"]+\"\.\"[^\"]+\")\s+s_\d+(.*)$', line)
            if match:
                print("match")
                prefix, field, suffix = match.groups()
                print("prefix, match, suffix")
                print(prefix + ", "  + suffix)
                field_name = field.split('.')[-1].strip('"')
                print(field_name)
                clean_alias = re.sub(r'[^A-Za-z0-9_]', '', field_name.replace(" ", "_"))
                updated_line = f'{prefix}{field} {clean_alias}{suffix}'
                print("updated line match")
                print(updated_line)
                updated_lines.append(updated_line)
            else:
                print("line no match")
                print(line)
                updated_lines.append(line)
        print("updated lines")

        print(updated_lines)
        return '\n'.join(updated_lines)