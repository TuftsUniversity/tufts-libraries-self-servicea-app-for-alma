#!/usr/bin/env python3
import pandas as pd
import json
import re
import requests
import sys
from tkinter.filedialog import askopenfilename


input = input(
    "Does this file include records for which you want to roll up ISBNs?  This may be because you've separated them previously:\n\t 1 - Yes\n\t 2 - No\n"
)

if input == "1" or input == "yes" or input == "Yes" or input == "y":
    isbn_bool = True

if input == "2" or input == "no" or input == "No" or input == "n":
    isbn_bool = False
# Ensure the output directory exists

filepath = askopenfilename(
    title="Pick multiple workbook with multiple resource sheet in it"
)


df = pd.read_excel(
    filepath, engine="openpyxl", sheet_name="Matches with Multiple Resources", dtype=str
)

df = df.applymap(lambda x: str(x).replace('"', "") if isinstance(x, str) else x)

print(f"DataFrame shape before grouping: {df.shape}")
print(df.head())  # Display first few rows


if isbn_bool:
    df["ISBN"] = df["ISBN"].apply(lambda x: re.sub(r"\s+", r"; ", x))

    df["ISBN(13)"] = df["ISBN(13)"].apply(lambda x: re.sub(r"\s+", r"; ", x))

rollup_columns = []

if isbn_bool:
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
        "ISBN",
        "ISBN(13)",
        "ISBN(Matching Identifier)",
    ]

else:
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

groupby_columns = []
for column in df.columns:
    if column not in rollup_columns:
        groupby_columns.append(column)

print(groupby_columns)

print(rollup_columns)
df.fillna("", inplace=True)
print(f"Actual DataFrame columns: {df.columns.tolist()}")
missing_columns = [col for col in rollup_columns if col not in df.columns]
print(f"Missing rollup columns: {missing_columns}")
# Create aggregation dictionary dynamically
agg_dict = {col: lambda x: "; ".join(set(x.astype(str))) for col in rollup_columns}

print(agg_dict)


# Apply groupby and aggregation
df_grouped = df.groupby(groupby_columns, as_index=False).agg(agg_dict)
df_grouped = df_grouped[df.columns]
print(df_grouped)


df2 = pd.read_excel(
    filepath, engine="openpyxl", sheet_name="Matches with Single Resource", dtype=str
)


# Remove double quotes from all values in the DataFrame
df2 = df2.applymap(lambda x: x.replace('"', "") if isinstance(x, str) else x)

# Append df2 to df
df_combined = pd.concat([df_grouped, df2], ignore_index=True)


df_combined.to_excel(
    "Merged Single and Multiple Resources with Rolled up Multiple Resources.xlsx",
    index=False,
)
