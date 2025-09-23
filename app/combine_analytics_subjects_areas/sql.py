import re

class SQLProcessor:
    def __init__(self, sql_input_1, sql_input_2, join_type, join_field_left=None, join_field_right=None):
        self.sql_input_1 = sql_input_1
        self.sql_input_2 = sql_input_2
        self.join_type = join_type
        self.left_alias = self.get_table_alias(sql_input_1)
        self.right_alias = self.get_table_alias(sql_input_2)

        # Always normalize join fields to use table aliases
        self.join_field_left = self.normalize_join_field(join_field_left or 'MMS_Id', self.left_alias)
        self.join_field_right = self.normalize_join_field(join_field_right or 'MMS_Id', self.right_alias)

    def get_table_alias(self, sql_input):
        match = re.search(r'FROM\s+"([^"]+)"', sql_input, re.IGNORECASE)
        if not match:
            return "unknown_alias"
        table_name = match.group(1)
        return re.sub(r'[^a-z0-9_]', '', table_name.lower().replace(" ", "_"))

    def normalize_join_field(self, raw, tbl_alias):
        """
        Coerce a user-supplied join field (possibly like `"Bibliographic Details"."MMS Id"`)
        into "<tbl_alias>.<Clean_Field_Name>".
        """
        if raw is None:
            return f'{tbl_alias}.MMS_Id'

        # Already looks like alias.field
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$', raw):
            return raw

        # If it's a quoted OBIEE-style ref, take the last quoted token as the field
        m = re.search(r'"[^"]+"\."([^"]+)"', raw)
        if m:
            field_name = m.group(1)
        else:
            # Fall back to the raw token and clean it
            field_name = raw

        clean_field = re.sub(r'[^A-Za-z0-9_]', '', field_name.replace(' ', '_'))
        return f'{tbl_alias}.{clean_field}'

    def extract_fields(self, sql_input, table_alias):
        """
        Extracts aliased fields from the inner SELECT. Handles both OBIEE saw_N
        and already-cleaned SQL identifiers.
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

            # Match:  "Dim"."Field" <alias>   where <alias> is either saw_\d+ or a normal identifier
            m = re.match(
                r'^(?:"[^"]+"\.)?("[^"]+"."[^"]+")\s+([A-Za-z_][A-Za-z0-9_]*|saw_\d+)\b,?',
                stripped
            )
            if not m:
                continue

            dim_field, alias_token = m.groups()
            # If alias is still OBIEE style, derive a clean name from the quoted field
            if alias_token.startswith("saw_"):
                field_name = dim_field.split('.')[-1].strip('"')
                clean_name = re.sub(r'[^A-Za-z0-9_]', '', field_name.replace(" ", "_"))
            else:
                clean_name = alias_token

            fields.append(f'{table_alias}.{clean_name}')

        return fields

    def update_aliases(self, sql_input):
        """
        Rewrite inner SELECT alias tokens from saw_<n> to readable aliases
        based on the quoted column's final identifier.
        """
        updated_lines = []
        in_select = False

        for line in sql_input.splitlines():
            stripped = line.strip()

            if stripped.upper().startswith("SELECT"):
                in_select = True
                updated_lines.append(line)
                continue
            if in_select and stripped.upper().startswith("FROM"):
                in_select = False
                updated_lines.append(line)
                continue

            # Example line:
            #   "Bibliographic Details"."MMS Id" saw_1,
            # Capture prefix + "X"."Y" + alias + optional comma/suffix
            m = re.match(r'^(.*?)(\"[^\"]+\"\.\"[^\"]+\")\s+saw_\d+(\s*,?\s*)$', line)
            if m:
                prefix, field, suffix = m.groups()
                field_name = field.split('.')[-1].strip('"')
                clean_alias = re.sub(r'[^A-Za-z0-9_]', '', field_name.replace(" ", "_"))
                updated_lines.append(f'{prefix}{field} {clean_alias}{suffix}')
            else:
                # Leave function expressions (e.g., MAX(RCOUNT(6)) saw_12) as-is,
                # or add a similar rule if you want to rename those too.
                updated_lines.append(line)

        return '\n'.join(updated_lines)

    def process_sql(self):
        # Normalize inner aliases in each input
        self.sql_input_1 = self.update_aliases(self.sql_input_1)
        self.sql_input_2 = self.update_aliases(self.sql_input_2)

        # Build the top-level SELECT list using table-alias.field
        left_fields = self.extract_fields(self.sql_input_1, self.left_alias)
        right_fields = self.extract_fields(self.sql_input_2, self.right_alias)
        select_fields = left_fields + right_fields

        select_clause = "SELECT\n   " + ",\n   ".join(select_fields) if select_fields else "SELECT"

        # Assemble final SQL with table aliases and normalized join fields
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

        return joined_sql
