import os
import pandas as pd
import re
from flask import Blueprint, request, redirect, url_for, send_file, current_app, render_template
from werkzeug.utils import secure_filename
import io
from io import BytesIO
import zipfile
import dotenv
import os
from dotenv import load_dotenv
import json
import requests
import time
import pymarc as pym

def zip_files(filenames):
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in filenames:
            data = open(filename, 'rb').read()
            zf.writestr(os.path.basename(filename), data)
    memory_file.seek(0)
    return memory_file

class Bib2Holdings541:
    def __init__(self, file_path):
        self.file_path = file_path
 
        load_dotenv()

        self.sandbox_bib_api_key = json.loads(os.getenv("sandbox_bib_api_key"))
        self.analytics_api_key = json.loads(os.getenv("analytics_api_key"))

    def process(self):
        df = pd.read_excel(
            self.file_path,
            engine="openpyxl",
            dtype=str,
        )



    def update_holding(holding, holding_id, full_holding_string, five_forty_one, mms_id):
        holding.add_field(five_forty_one)
        print("Holding with new field: \n" + str(holding) + "\n\n\n" )
        updated_holding = pym.record_to_xml(holding).decode('utf-8')


        full_holding_string = full_holding_string.decode('utf-8')

        full_updated_holding = re.sub(r'<record>(.+)</record>', updated_holding, full_holding_string)

        print("Updated XML Holding Record: \n" + full_updated_holding + "\n")

        full_updated_holding = full_updated_holding.replace('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '')

        #success = True



        # faulty_xml = "<holding></holding>"
        #
        # # full_holdings_xml = root.find('holding/holding_id=')
        #
        #
        response = requests.put("https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/" + str(mms_id) + "/holdings/" + str(holding_id) + "?apikey=" + secrets_local.bib_api_key, data=full_updated_holding, headers=headers)
        #
        time.sleep(2)
        print(response.content)
        # #
        # #
        # # # response = requests.put("https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/" + str(mms_id) + "/holdings/" + str(holding_id) + "?apikey=", data=full_updated_holding, headers=headers)
        # # #
        # # # print(response.content)
        if re.search('<errorsExist>true</errorsExist>', response.content):
            print("Couldn't write back to Alma for MMS ID: " + mms_id + "\n")
            error_file.write("Couldn't write back to Alma for MMS ID: " + mms_id + "\n")
            success = False
        else:
            output_file.write("<MMS_ID_" + mms_id + ">" + full_updated_holding + "</MMS_ID_" + mms_id + ">")

            success = True

        # print(response.content)
        #
        # print(success)
        #
        # sys.exit()
        return success

    def getLocations():
        url = "https://api-na.hosted.exlibrisgroup.com/almaws/v1/analytics/reports?apikey=" + secrets_local.analytics_api_key
        limit = "&limit=1000"
        format = "&format=xml"
        path = "&path=%2Fshared%2FTufts+University%2FReports%2FCataloging%2FAdding+541+to+Holdings+Records%2FLocation+Name-Location+Code"

        report = requests.get(url + format + path + limit)

        #print("\nReport Content: \n" + report.content)

        report_outfile = open('Output/list of codes and locations.xml', "w+")

        # report_str = report.content.decode('utf-8')
        report_outfile.write(str(report.content))

        # print("\n\nReport: \n" + report.content)

        report_outfile.close()

        tree = et.ElementTree(et.fromstring(report.content))

        # print("\nTree: " + tree.text + "\n")

        root = tree.getroot()

        print("\nRoot: \n" + str(root.text) + "\n")



        reportDict = {}
        #for element in root.iter('{urn:schemas-microsoft-com:xml-analysis:rowset}Row'):
        # print("\n\nAll Elements: \n" + str(list(root.iter())))

        for element in root.iter():
            library = ""
            code = ""
            description = ""
            if re.match(r'.*Row', element.tag):
                for sub_element in element.iter():
                    if re.match(r'.*Column2', sub_element.tag):
                        code = sub_element.text
                    if re.match(r'.*Column3', sub_element.tag):
                        description = sub_element.text
                    elif re.match(r'.*Column1', sub_element.tag):
                        library = sub_element.text


            if library in reportDict:
                reportDict[library][description] = code
            else:
                reportDict[library] = {}
                reportDict[library][description] = code



        # for c in reportDict:
        # 	c = c.decode('ascii')
        # 	for d in reportDict[c]:
        # 		reportDict[c][d] = reportDict[c][d].decode('ascii')
        for i in reportDict:
            for j in reportDict[i]:
                print("Library: " + str(i) + "; Description: " + str(j)  + "; Code: " + str(reportDict[i][j]) +  "\n")
        return reportDict



        # faulty_xml = "<holding></holding>"
        #
        # # full_holdings_xml = root.find('holding/holding_id=')
        #
        #
        response = requests.put("https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/" + str(mms_id) + "/holdings/" + str(holding_id) + "?apikey=" + secrets_local.bib_api_key, data=full_updated_holding, headers=headers)
        #
        time.sleep(2)
        print(response.content)
        # #
        # #
        # # # response = requests.put("https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/" + str(mms_id) + "/holdings/" + str(holding_id) + "?apikey=", data=full_updated_holding, headers=headers)
        # # #
        # # # print(response.content)
        if re.search('<errorsExist>true</errorsExist>', response.content):
            print("Couldn't write back to Alma for MMS ID: " + mms_id + "\n")
            error_file.write("Couldn't write back to Alma for MMS ID: " + mms_id + "\n")
            success = False
        else:
            output_file.write("<MMS_ID_" + mms_id + ">" + full_updated_holding + "</MMS_ID_" + mms_id + ">")

            success = True

        # print(response.content)
        #
        # print(success)
        #
        # sys.exit()
        return success





        # df = df.applymap(lambda x: str(x).replace('"', "") if isinstance(x, str) else x)

        # df = df.applymap(lambda x: str(x).replace('"', '') if isinstance(x, str) else x)

        # print(f"DataFrame shape before grouping: {df.shape}")
        # print(df.head())  # Display first few rows

        # df['ISSN'] = df['ISSN'].apply(lambda x: re.sub(r'\s+', r'; ', x))

        # df = df['ISSN'].str.split(';').explode().reset_index(drop=True)


        # if self.isbn_bool:
        #     df['ISBN'] = df['ISBN'].apply(lambda x: re.sub(r'\s+', r'; ', x))

        #     df['ISBN(13)'] = df['ISBN(13)'].apply(lambda x: re.sub(r'\s+', r'; ', x))

        # rollup_columns = []

        # if self.isbn_bool:
        #     rollup_columns = ["Collection", "Interface", "Portfolio ID", "Coverage", "Embargo", "Resource Scope","Linked To CZ", "Open Access", "Access Type", "Is Active", "ISBN", "ISBN(13)","ISBN(Matching Identifier)"]


        #     rollup_columns_sum = ["Link resolver usage (access)", "Link resolver usage (appearance)"]

        # else:

        #     rollup_columns = ["Collection", "Interface", "Portfolio ID", "Coverage", "Embargo", "Resource Scope", "Linked To CZ", "Open Access", "Access Type", "Is Active"]


        #     rollup_columns_sum = ["Link resolver usage (access)", "Link resolver usage (appearance)"]
        # df[rollup_columns_sum] = df[rollup_columns_sum].fillna(0)
        # df[rollup_columns_sum] = df[rollup_columns_sum].astype(int)


        # groupby_columns = []
        # for column in df.columns:
        #     if column not in rollup_columns and column not in rollup_columns_sum:
        #         groupby_columns.append(column)

        # print(groupby_columns)

        # print(rollup_columns)

        # print(rollup_columns_sum)
        # df.fillna("", inplace=True)
        # print(f"Actual DataFrame columns: {df.columns.tolist()}")

        # # Create aggregation dictionary dynamically
        # agg_dict = {col: lambda x: "; ".join(set(x.astype(str))) for col in rollup_columns}

        # sum_dict = {
        #     col: lambda x: x.astype(int).sum() for col in rollup_columns_sum
        # }
        # print(agg_dict)

        # print(sum_dict)

        # # Merge both aggregation strategies
        # agg_dict.update(sum_dict)
        # # Apply groupby and aggregation
        # df_grouped = df.groupby(groupby_columns, as_index=False).agg(agg_dict)
        # df_grouped = df_grouped[df.columns]
        # print(df_grouped)


        
        # df2 = pd.read_excel(
        #     self.file_path,
        #     engine="openpyxl",
        #     sheet_name="Matches with Single Resource",
        #     dtype=str,
        # )
        # df[rollup_columns_sum] = df[rollup_columns_sum].fillna(0)
        # df[rollup_columns_sum] = df[rollup_columns_sum].astype(int)

        # isbn_columns = ["ISBN", "ISBN(13)", "ISBN(Matching Identifier)"]



        # single_match_groupby_columns = groupby_columns + rollup_columns + rollup_columns_sum

        # if self.isbn_bool:
        #     isbn_dict = {col: lambda x: "; ".join(set(x.astype(str))) for col in isbn_columns}
        #     df2_grouped = df2.groupby(single_match_groupby_columns, as_index=False).agg(isbn_dict)
        #     df2_grouped = df2_grouped[df2.columns]

        #     df2 = df2_grouped


        # # Remove double quotes from all values in the DataFrame
        # df2 = df2.applymap(lambda x: x.replace('"', '') if isinstance(x, str) else x)

        # # Append df2 to df
        # df_combined = pd.concat([df_grouped, df2], ignore_index=True)




        # no_match_df = pd.read_excel(
        #     self.file_path,
        #     engine="openpyxl",
        #     sheet_name="No Matches or No Resources",
        #     dtype=str,
        # )
        # no_match_df = no_match_df.applymap(lambda x: str(x).replace('"', '') if isinstance(x, str) else x)


        # try:
        #     no_match_df = no_match_df.rename(columns={"MMS Id": "MMS ID"})



        # except:
        #     no_match_df = no_match_df

        # print(no_match_df)

        # no_match_df = no_match_df.fillna("")
        # if self.isbn_bool:
        #     no_match_group_by_columns = []
        #     for column in no_match_df.columns:
        #         if column != "ISBN(Matching Identifier)":
        #             no_match_group_by_columns.append(column)
        #     print(no_match_group_by_columns)
        #     isbn_dict_2 = {col: lambda x: "; ".join(set(x.astype(str))) for col in ['ISBN(Matching Identifier)']}

        #     no_match_df["ISBN(Matching Identifier)"] = no_match_df["ISBN(Matching Identifier)"].fillna("")
        #     no_match_df["ISBN(Matching Identifier)"] = no_match_df["ISBN(Matching Identifier)"].astype(str)

        #     print(isbn_dict_2)

        #     # Debug print: Check columns
        #     print("Available columns in no_match_df:", no_match_df.columns.tolist())
        #     print("Grouping by columns:", no_match_group_by_columns)

        #     # Ensure grouping columns exist
        #     no_match_group_by_columns = [col for col in no_match_group_by_columns if col in no_match_df.columns]
        #     print("Updated grouping columns:", no_match_group_by_columns)

        #     # Ensure ISBN(Matching Identifier) is not empty
        #     no_match_df = no_match_df[no_match_df["ISBN(Matching Identifier)"].notna() & (no_match_df["ISBN(Matching Identifier)"] != "")]
        #     if no_match_df.empty:
        #         print("⚠️ Warning: no_match_df is empty after removing empty ISBN(Matching Identifier). Skipping grouping.")
        #     else:
        #         no_match_df["ISBN(Matching Identifier)"] = no_match_df["ISBN(Matching Identifier)"].astype(str)
        #         no_match_df_grouped = no_match_df.groupby(no_match_group_by_columns, as_index=False).agg(isbn_dict_2)

        #         print("After grouping:", no_match_df_grouped)

        #         no_match_df = no_match_df_grouped
        #     # no_match_df_grouped = no_match_df.groupby(no_match_group_by_columns, as_index=False).agg(isbn_dict_2)
        #     #
        #     # print("just after grouping")
        #     #
        #     # print(no_match_df_grouped)
        #     # no_match_df_grouped = no_match_df_grouped[no_match_df.columns]
        #     #
        #     # print("after matching columns")
        #     # print(no_match_df_grouped)
        #     #
        #     #
        #     # no_match_df_grouped = no_match_df_grouped[no_match_df.columns]
        #     #
        #     # print(no_match_df_grouped)
        #     # no_match_df = no_match_df_grouped
        #     #
        #     # print(no_match_df)
        # df_combined = pd.concat([df_grouped, df2], ignore_index=True)
        #   # Write the combined dataframe to an in-memory Excel file
        # output_combined = io.BytesIO()
        # df_combined.to_excel(output_combined, index=False)
        # output_combined.seek(0)


        # output_no_match = io.BytesIO()

        # no_match_df.to_excel(output_no_match, index=False)

        # output_no_match.seek(0)

        # # Step 2: Create ZIP Archive in Memory
        # zip_buffer = io.BytesIO()
        # with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        #     zip_file.writestr("Merged Single and Multiple Resources with Rolled up Multiple Resources.xlsx", output_combined.getvalue())
        #     zip_file.writestr("No Match.xlsx", output_no_match.getvalue())

        # zip_buffer.seek(0)

        # # Step 3: Return ZIP File for Download
        # return send_file(zip_buffer, 
        #                 mimetype="application/zip", 
        #                 as_attachment=True, 
        #                 download_name="rollup_files.zip")
