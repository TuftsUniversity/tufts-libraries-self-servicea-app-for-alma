import os
import pandas as pd
import re
from flask import Blueprint, request, redirect, url_for, send_file, current_app
from werkzeug.utils import secure_filename


class ResourceMatch:
    def __init__(self, file_path, isbn_bool):
        self.file_path = file_path
        self.isbn_bool = isbn_bool

    def process(self):
        df = pd.read_excel(
            self.file_path,
            engine="openpyxl",
            sheet_name="Matches with Multiple Resources",
            dtype=str,
        )
        df = df.applymap(lambda x: str(x).replace('"', "") if isinstance(x, str) else x)

        if self.isbn_bool:
            df["ISBN"] = df["ISBN"].apply(lambda x: re.sub(r"\s+", r"; ", x))
            df["ISBN(13)"] = df["ISBN(13)"].apply(lambda x: re.sub(r"\s+", r"; ", x))

        rollup_columns = [
            "Collection",
            "Interface",
            "Portfolio ID",
            "Coverage",
            "Embargo",
            "Resource Scope",
            "Linked To CZ",
            "Open Access",
            "Access Type",
            "Is Active",
            "Link resolver usage (access)",
            "Link resolver usage (appearance)",
        ]

        if self.isbn_bool:
            rollup_columns.extend(["ISBN", "ISBN(13)", "ISBN(Matching Identifier)"])

        groupby_columns = [col for col in df.columns if col not in rollup_columns]
        df.fillna("", inplace=True)

        agg_dict = {
            col: lambda x: "; ".join(set(x.astype(str))) for col in rollup_columns
        }
        df_grouped = df.groupby(groupby_columns, as_index=False).agg(agg_dict)
        df_grouped = df_grouped[df.columns]

        df2 = pd.read_excel(
            self.file_path,
            engine="openpyxl",
            sheet_name="Matches with Single Resource",
            dtype=str,
        )
        df2 = df2.applymap(lambda x: x.replace('"', "") if isinstance(x, str) else x)

        df_combined = pd.concat([df_grouped, df2], ignore_index=True)
        DOWNLOAD_FOLDER = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "uploads"
        )
        output_path = os.path.join(DOWNLOAD_FOLDER, "Merged_Resources.xlsx")
        df_combined.to_excel(output_path, index=False)
        return output_path
