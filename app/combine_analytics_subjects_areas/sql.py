import re

class SQLProcessor:
    """
    Join two OBIEE-exported SQL blocks by:
      - Rewriting OBIEE aliases (s_#, saw_#) to clean names derived from the column label
      - Removing constant columns like `0 s_0,`
      - Rewriting positional ORDER BY (e.g., ORDER BY 14) to alias-based ORDER BY
      - Emitting an outer SELECT that references subquery aliases as unquoted identifiers:
            left_alias.Title, right_alias.External_Identifier
    """

    def __init__(self, sql_input_1, sql_input_2, join_type, join_field_left=None, join_field_right=None):
        self.sql_input_1 = sql_input_1
        self.sql_input_2 = sql_input_2
        self.join_type = (join_type or "INNER").upper()

        self.left_alias = self._get_table_alias(sql_input_1)   # e.g., "Fulfillment" -> "fulfillment"
        self.right_alias = self._get_table_alias(sql_input_2)  # e.g., 'Borrowing Requests (Resource Sharing)' -> 'borrowing_requests_resource_sharing'

        # Normalize user-supplied join fields to <alias>.<CleanField>
        self.join_field_left = self._normalize_join_field(join_field_left or 'MMS_Id', self.left_alias)
        self.join_field_right = self._normalize_join_field(join_field_right or 'MMS_Id', self.right_alias)

    # ---------- helpers for aliasing / parsing ----------

    def _get_table_alias(self, sql_input: str) -> str:
        m = re.search(r'FROM\s+"([^"]+)"', sql_input, re.IGNORECASE)
        if not m:
            return "unknown_alias"
        subject_area = m.group(1)
        return re.sub(r'[^a-z0-9_]', '', subject_area.lower().replace(" ", "_"))

    def _clean_alias_from_field_expr(self, quoted_expr: str) -> str:
        """
        Given a quoted OBIEE expression like:
            "Fulfillment"."Borrower Details"."First Name"
        return a clean identifier based on the final label:
            First_Name
        """
        parts = re.findall(r'"([^"]+)"', quoted_expr)
        last = parts[-1] if parts else quoted_expr
        return re.sub(r'[^A-Za-z0-9_]', '', last.replace(" ", "_"))

    def _normalize_join_field(self, raw: str, tbl_alias: str) -> str:
        """
        Convert user-supplied field into <tbl_alias>.<CleanField>.
        Accepts:
          - alias.field
          - "X"."Y" or "X"."Y"."Z"
          - plain field name
        """
        if not raw:
            return f'{tbl_alias}.MMS_Id'

        # already alias.field
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$', raw):
            return raw

        # quoted OBIEE expression => clean final token
        if '"' in raw:
            clean = self._clean_alias_from_field_expr(raw)
            return f'{tbl_alias}.{clean}'

        # plain name
        clean = re.sub(r'[^A-Za-z0-9_]', '', raw.replace(" ", "_"))
        return f'{tbl_alias}.{clean}'

    # ---------- inner SELECT rewriting ----------

    def _rewrite_inner_select(self, sql_input: str) -> str:
        """
        Inside the SELECT ... FROM block:
          - Drop constant columns like `0 s_0,`
          - Rewrite `"X"."Y"[."Z"] s_#` or `saw_#` to clean aliases
          - Leave already-clean aliases intact
        """
        lines = sql_input.splitlines()
        out = []
        in_select = False

        alias_token_pat = r'(?:s_\d+|saw_\d+)'
        const_col_pat = re.compile(r'^\s*\d+\s+' + alias_token_pat + r'\s*,?\s*$', re.IGNORECASE)
        rewrite_pat = re.compile(r'^(?P<prefix>\s*)(?P<expr>"[^"]+"(?:\."[^"]+")+)\s+' + alias_token_pat + r'(?P<suffix>\s*,?\s*)$')

        for raw in lines:
            line = raw.rstrip('\n')
            stripped = line.strip()

            if stripped.upper().startswith("SELECT"):
                in_select = True
                out.append(line)
                continue
            if in_select and stripped.upper().startswith("FROM"):
                in_select = False
                out.append(line)
                continue

            if in_select:
                # drop constant columns e.g. `0 s_0,`
                if const_col_pat.match(stripped):
                    continue

                # rewrite s_#/saw_# to clean alias from the quoted expr
                m = rewrite_pat.match(line)
                if m:
                    expr = m.group('expr')
                    clean = self._clean_alias_from_field_expr(expr)
                    out.append(f'{m.group("prefix")}{expr} {clean}{m.group("suffix")}')
                    continue

            out.append(line)

        return "\n".join(out)

    def _extract_select_items(self, sql_input):
        """
        Return ordered list of (expr, alias) from inner SELECT, e.g.:
        ("\"Due Date\".\"Due Date\"", "Due_Date")
        """
        items = []
        in_select = False
        pat = re.compile(r'^\s*("([^"]+)"(?:\."[^"]+")+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*,?\s*$')

        for raw in sql_input.splitlines():
            s = raw.strip()
            if s.upper().startswith("SELECT"):
                in_select = True
                continue
            if in_select and s.upper().startswith("FROM"):
                break
            m = pat.match(s)
            if m:
                expr = m.group(1)      # the full quoted expr
                alias = m.group(3)     # the clean alias
                items.append((expr, alias))
        return items

    def _extract_alias_list(self, sql_input: str):
        """
        Return ordered list of aliases from inner SELECT.
        Matches lines of the form:   "<quoted expr>" <alias>[,]
        """
        aliases = []
        in_select = False
        m_alias = re.compile(r'^\s*"[^"]+"(?:\."[^"]+")+\s+([A-Za-z_][A-Za-z0-9_]*)\s*,?\s*$')

        for raw in sql_input.splitlines():
            stripped = raw.strip()
            if stripped.upper().startswith("SELECT"):
                in_select = True
                continue
            if in_select and stripped.upper().startswith("FROM"):
                break

            m = m_alias.match(stripped)
            if m:
                aliases.append(m.group(1))

        return aliases

    def _strip_inner_order_by(self, sql_input):
        # Remove entire ORDER BY lines inside a subquery
        return re.sub(r'(?im)^\s*ORDER\s+BY\b.*$', '', sql_input)

    def _rewrite_order_by(self, sql_input, select_items, offset):
        """
        Rewrite ORDER BY <pos> to ORDER BY <quoted expr>, with offset for removed constants.
        Drops a term if it can't be mapped.
        """
        def transform_line(line):
            m = re.match(r'(\s*ORDER\s+BY\s+)(.*)$', line, flags=re.IGNORECASE)
            if not m:
                return line
            head, tail = m.groups()
            parts = [p.strip() for p in tail.split(',')]
            new_parts = []
            for p in parts:
                mnum = re.match(r'(\d+)\b(.*)', p)
                if mnum:
                    n = int(mnum.group(1))
                    n_adj = n - offset
                    if 1 <= n_adj <= len(select_items):
                        expr, _alias = select_items[n_adj - 1]
                        new_parts.append(expr + mnum.group(2))
                    # else drop unmappable positional term
                else:
                    # keep already-alias/expr forms as-is
                    new_parts.append(p)
            return head + ', '.join(new_parts) if new_parts else ''

        lines = sql_input.splitlines()
        return "\n".join(
            transform_line(l) if re.search(r'^\s*ORDER\s+BY\b', l, flags=re.IGNORECASE) else l
            for l in lines
        )


    def _count_constants_in_select(self, sql_input):
        """Count constant columns like:  0 s_0,  1 s_7,  etc., inside the SELECT...FROM."""
        alias_token_pat = r'(?:s_\d+|saw_\d+)'
        const_col_pat = re.compile(r'^\s*\d+\s+' + alias_token_pat + r'\s*,?\s*$', re.IGNORECASE)

        in_select = False
        count = 0
        for raw in sql_input.splitlines():
            stripped = raw.strip()
            if stripped.upper().startswith("SELECT"):
                in_select = True
                continue
            if in_select and stripped.upper().startswith("FROM"):
                break
            if in_select and const_col_pat.match(stripped):
                count += 1
        return count

    # ---------- outer SELECT assembly ----------

    def _outer_select_fields(self, table_alias: str, aliases):
        # IMPORTANT: OBIEE expects these as unquoted identifiers
        return [f"{table_alias}.{a}" for a in aliases]

    def process_sql(self):
        # COUNT constants first if you still use that elsewhere (optional)
        # left_offset = self._count_constants_in_select(self.sql_input_1)
        # right_offset = self._count_constants_in_select(self.sql_input_2)

        # 1) Normalize inner SELECTs (rewrite s_#/saw_# ? clean aliases; drop constants)
        left_sql = self._rewrite_inner_select(self.sql_input_1)
        right_sql = self._rewrite_inner_select(self.sql_input_2)

        # 2) Strip inner ORDER BY completely (avoids “Nonexistent column” in subqueries)
        left_sql = self._strip_inner_order_by(left_sql)
        right_sql = self._strip_inner_order_by(right_sql)

        # 3) Build alias lists (from the cleaned inner SELECTs)
        left_aliases = self._extract_alias_list(left_sql)
        right_aliases = self._extract_alias_list(right_sql)

        # 4) Outer SELECT uses unquoted subquery aliases
        select_fields = [f"{self.left_alias}.{a}" for a in left_aliases] + \
                        [f"{self.right_alias}.{a}" for a in right_aliases]
        select_clause = "SELECT\n   " + ",\n   ".join(select_fields)

        # 5) Final JOIN
        final_sql = f"""{select_clause}
    FROM (
    {left_sql}
    ) {self.left_alias}
    {self.join_type} JOIN (
    {right_sql}
    ) {self.right_alias}
    ON {self.join_field_left} = {self.join_field_right}"""
        return final_sql

