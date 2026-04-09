import pandas as pd
import numpy as np
from datetime import datetime
import io
import requests
import xml.etree.ElementTree as et
from typing import Optional

class ConcurrentCheckouts:
    def __init__(self, file):
        self.file = file
        self.sru_url = (
            "https://tufts.alma.exlibrisgroup.com/view/sru/01TUN_INST"
            "?version=1.2&operation=searchRetrieve&recordSchema=marcxml&query=alma.mms_id="
        )



    def _build_daily_unique_item_summary(self, cc: pd.DataFrame, total_items_available: Optional[int] = None) -> pd.DataFrame:
        if cc.empty:
            return pd.DataFrame(columns=["Date", "Unique Item Count", "Total Items Available"])

        day_item_pairs = set()

        if total_items_available is None:
            total_items_available = len(
                cc[["MMS Id", "Permanent Call Number"]].drop_duplicates()
            )

        for idx, row in cc.iterrows():
            loan_dt = row["Loan Datetime"]
            return_dt = row["Return Datetime"]

            if pd.isna(loan_dt) or pd.isna(return_dt):
                continue

            start_day = loan_dt.date()
            end_day = return_dt.date()

            if end_day < start_day:
                end_day = start_day

            barcode = str(row.get("Barcode", "")).strip()
            mms_id = str(row.get("MMS Id", "")).strip()
            item_key = f"{mms_id}|{barcode}" if barcode else f"{mms_id}|ROW{idx}"

            current_day = start_day
            while current_day <= end_day:
                day_item_pairs.add((current_day, item_key))
                current_day += pd.Timedelta(days=1)

        if not day_item_pairs:
            return pd.DataFrame(columns=["Date", "Unique Item Count", "Total Items Available"])

        unique_days = sorted({day for day, _ in day_item_pairs})
        counts = []
        for one_day in unique_days:
            item_count = len({item for day, item in day_item_pairs if day == one_day})
            counts.append({
                "Date": one_day,
                "Unique Item Count": item_count,
                "Total Items Available": int(total_items_available)
            })

        summary_df = pd.DataFrame(counts)
        summary_df = summary_df.sort_values("Date").reset_index(drop=True)

        full_range = pd.date_range(
            start=summary_df["Date"].min(),
            end=summary_df["Date"].max(),
            freq="D"
        )

        summary_df = (
            summary_df.set_index("Date")
            .reindex(full_range)
            .rename_axis("Date")
            .reset_index()
        )

        summary_df["Unique Item Count"] = summary_df["Unique Item Count"].fillna(0)
        summary_df["Total Items Available"] = int(total_items_available)
        summary_df["Date"] = pd.to_datetime(summary_df["Date"]).dt.date

        return summary_df

    def _get_total_item_count_from_sru(self, unique_mms_id_list) -> int:
        total_item_count = 0
        namespaces = {"ns1": "http://www.loc.gov/MARC21/slim"}

        for mms_id in unique_mms_id_list:
            sru_response = requests.get(f"{self.sru_url}{mms_id}", timeout=60)
            if sru_response.status_code != 200:
                raise RuntimeError(
                    f"Failed to retrieve SRU data for MMS ID {mms_id}. "
                    f"Status code: {sru_response.status_code}"
                )

            root = et.fromstring(sru_response.content.decode("utf-8"))
            holdings = root.findall(".//ns1:datafield[@tag='AVA']", namespaces)

            for holding in holdings:
                item_count = holding.find("ns1:subfield[@code='f']", namespaces)
                if item_count is not None and item_count.text:
                    try:
                        total_item_count += int(item_count.text)
                    except ValueError:
                        pass

        return total_item_count

    def process_file(self):
        cc = pd.read_excel(
            self.file,
            dtype={
                "MMS Id": "str",
                "Barcode": "str",
                "Permanent Call Number": "str"
            },
            converters={
                "Loan Date": pd.to_datetime,
                "Loan Time": pd.to_datetime,
                "Return Date": pd.to_datetime,
                "Return Time": pd.to_datetime
            },
            engine="openpyxl"
        )

        output_buffer = io.BytesIO()
        counts_buffer = io.BytesIO()

        output_excel_file = pd.ExcelWriter(output_buffer, engine="xlsxwriter")
        writerAll = pd.ExcelWriter(counts_buffer, engine="xlsxwriter")

        todays_date = datetime.now()
        current_time = datetime.now()

        cc["Return Date"] = cc["Return Date"].fillna(todays_date)
        cc["Return Time"] = cc["Return Time"].fillna(current_time)

        cc["Loan Date"] = cc["Loan Date"].apply(lambda x: x.strftime("%m-%d-%Y"))
        cc["Loan Time"] = cc["Loan Time"].apply(lambda x: x.strftime("%H:%M:%S"))
        cc["Return Date"] = cc["Return Date"].apply(lambda x: x.strftime("%m-%d-%Y"))
        cc["Return Time"] = cc["Return Time"].apply(lambda x: x.strftime("%H:%M:%S"))

        cc["Loan Datetime"] = pd.to_datetime(cc["Loan Date"] + " " + cc["Loan Time"])
        cc["Return Datetime"] = pd.to_datetime(cc["Return Date"] + " " + cc["Return Time"])

        cc = cc.sort_values(
            ["MMS Id", "Permanent Call Number", "Barcode", "Loan Datetime", "Return Datetime"]
        )

        unique_mms_id_list = cc["MMS Id"].dropna().astype(str).unique().tolist()
        total_item_count = self._get_total_item_count_from_sru(unique_mms_id_list)

        daily_summary_df = self._build_daily_unique_item_summary(
            cc,
            total_items_available=total_item_count
        )

        daily_summary_df.to_excel(
            output_excel_file,
            sheet_name="Daily Loan Graph",
            startrow=0,
            startcol=0,
            index=False
        )

        workbook_output = output_excel_file.book
        daily_sheet = output_excel_file.sheets["Daily Loan Graph"]

        header_format = workbook_output.add_format({
            "bold": True,
            "bg_color": "#D9EAF7",
            "border": 1
        })
        date_format = workbook_output.add_format({"num_format": "yyyy-mm-dd"})

        for col_num, value in enumerate(daily_summary_df.columns.values):
            daily_sheet.write(0, col_num, value, header_format)

        daily_sheet.set_column("A:A", 14, date_format)
        daily_sheet.set_column("B:C", 20)
        daily_sheet.freeze_panes(1, 0)
        daily_sheet.write("E1", "Rule", header_format)
        daily_sheet.write("E2", "Bars count each item at most once per calendar day.")
        daily_sheet.write("E3", f"Line = SRU total item count ({total_item_count}).")

        chart = workbook_output.add_chart({"type": "column"})
        line_chart = workbook_output.add_chart({"type": "line"})
        max_row = len(daily_summary_df)

        if max_row > 0:
            chart.add_series({
                "name": "Daily items on loan",
                "categories": ["Daily Loan Graph", 1, 0, max_row, 0],
                "values": ["Daily Loan Graph", 1, 1, max_row, 1],
                "fill": {"color": "#4F81BD"},
                "border": {"color": "#4F81BD"}
            })

            line_chart.add_series({
                "name": "Total items available",
                "categories": ["Daily Loan Graph", 1, 0, max_row, 0],
                "values": ["Daily Loan Graph", 1, 2, max_row, 2],
                "line": {"color": "#C0504D", "width": 2.25},
                "y2_axis": True
            })

            line_chart.set_y2_axis({
                "name": "Total items available",
                "min": 0,
                "max": max(total_item_count, int(daily_summary_df["Unique Item Count"].max())) + 5
            })

            chart.combine(line_chart)
            chart.set_title({"name": "Daily Loan Activity"})
            chart.set_x_axis({"name": "Date", "date_axis": True})
            chart.set_y_axis({"name": "Daily items on loan"})
            chart.set_size({"width": 1100, "height": 420})
            chart.set_legend({"position": "bottom"})
            daily_sheet.insert_chart("E5", chart)

        dd = pd.DataFrame()
        ee = pd.DataFrame()

        x = 0
        volumeCount = 0

        workbook = writerAll.book

        totalBarcodeCount = 0
        totalCount = 0
        totalTransactionCount = 0
        transacationWithinBarcodeCountForCount = 0

        while x < len(cc):
            volumeCount += 1
            y = x
            count = 0

            title = cc.iloc[x]["Title"]
            mms_id = cc.iloc[x]["MMS Id"]
            call_number = cc.iloc[x]["Permanent Call Number"]

            columns = [
                "Title", "MMS Id", "Permanent Call Number", "Barcode",
                "Loan Datetime", "Loan Date", "Return Datetime", "Return Date"
            ]
            a = pd.DataFrame(columns=columns)

            a = pd.concat([
                a,
                pd.DataFrame([{
                    "Title": cc.iloc[x]["Title"],
                    "MMS Id": cc.iloc[x]["MMS Id"],
                    "Call Number": cc.iloc[x]["Permanent Call Number"],
                    "Barcode": cc.iloc[x]["Barcode"],
                    "Loan Datetime": cc.iloc[x]["Loan Datetime"],
                    "Loan Date": cc.iloc[x]["Loan Date"],
                    "Return Datetime": cc.iloc[x]["Return Datetime"],
                    "Return Date": cc.iloc[x]["Return Date"]
                }])
            ], ignore_index=True)

            y += 1
            count += 1

            while (
                y < len(cc)
                and cc.iloc[y]["MMS Id"] == cc.iloc[y - 1]["MMS Id"]
                and cc.iloc[y]["Permanent Call Number"] == cc.iloc[y - 1]["Permanent Call Number"]
            ):
                a = pd.concat([
                    a,
                    pd.DataFrame([{
                        "Title": cc.iloc[y]["Title"],
                        "MMS Id": cc.iloc[y]["MMS Id"],
                        "Call Number": cc.iloc[y]["Permanent Call Number"],
                        "Barcode": cc.iloc[y]["Barcode"],
                        "Loan Datetime": cc.iloc[y]["Loan Datetime"],
                        "Loan Date": cc.iloc[y]["Loan Date"],
                        "Return Datetime": cc.iloc[y]["Return Datetime"],
                        "Return Date": cc.iloc[y]["Return Date"]
                    }])
                ], ignore_index=True)

                y += 1
                count += 1

            z = 0
            barcodeDict = {}
            barcodeCount = 0
            transactionWithinBarcodeCount = 0
            c = pd.DataFrame()

            while z < count:
                fCount = 0
                f = z + 1
                firstLoanIndex = str(a.at[z, "Loan Datetime"])
                barcode = str(a.iloc[z]["Barcode"])

                if firstLoanIndex in c:
                    firstLoanIndex += ":0" + str(z) + str(f)

                c.insert(loc=transactionWithinBarcodeCount, column=firstLoanIndex, value="")
                c.at[barcodeCount, firstLoanIndex] = "loan"
                transactionWithinBarcodeCount += 1
                fCount += 1

                firstReturnIndex = str(a.iloc[z]["Return Datetime"])
                if firstReturnIndex in c:
                    firstReturnIndex += ":0" + str(z) + str(f)

                c.insert(loc=transactionWithinBarcodeCount, column=firstReturnIndex, value="")
                c.at[barcodeCount, firstReturnIndex] = "return"
                transactionWithinBarcodeCount += 1
                transacationWithinBarcodeCountForCount += 1

                while f < count and a.iloc[z]["Barcode"] == a.iloc[f]["Barcode"]:
                    loanIndex = str(a.iloc[f]["Loan Datetime"])
                    if loanIndex in c:
                        loanIndex += ":0" + str(z) + str(f)

                    c.insert(loc=transactionWithinBarcodeCount, column=loanIndex, value="")
                    c.at[barcodeCount, loanIndex] = "loan"
                    transactionWithinBarcodeCount += 1

                    returnIndex = str(a.iloc[f]["Return Datetime"])
                    if returnIndex in c:
                        returnIndex += ":0" + str(z) + str(f)

                    c.insert(loc=transactionWithinBarcodeCount, column=returnIndex, value="")
                    c.at[barcodeCount, returnIndex] = "return"
                    transactionWithinBarcodeCount += 1
                    transacationWithinBarcodeCountForCount += 1

                    f += 1
                    fCount += 1

                z += fCount
                barcodeDict[barcodeCount] = barcode
                totalTransactionCount += transactionWithinBarcodeCount
                c = c.rename(index=barcodeDict)
                barcodeCount += 1
                totalBarcodeCount += 1

            totalCount += count

            c = c.reindex(sorted(c.columns), axis=1)
            columnCount = len(c.columns)

            if barcodeCount > 1:
                l = 0
                while l < barcodeCount:
                    m = 0
                    while m < columnCount:
                        d = 1
                        if c.iat[l, m] == "loan":
                            while (
                                m + d < columnCount
                                and c.iat[l, m + d] != "loan"
                                and c.iat[l, m + d] != "return"
                            ):
                                c.iat[l, m + d] = "on loan"
                                d += 1
                        m += d
                    l += 1

            concurrentDates = {}
            maxedOutDates = {}
            concurrentCount = 0
            maxedOutCount = 0
            concurrentLoanRunCounter = 0
            maxedOutLoanRunCounter = 0

            concurrentDates["Title"] = title
            concurrentDates["MMS Id"] = mms_id
            concurrentDates["Call Number"] = call_number

            for column in c.columns:
                if len(c[c[column] == "loan"]) + len(c[c[column] == "on loan"]) > 1 and barcodeCount > 1:
                    concurrentLoanRunCounter += 1
                elif (
                    concurrentLoanRunCounter > 0
                    and len(c[c[column] == "loan"]) + len(c[c[column] == "on loan"]) <= 1
                    and barcodeCount > 1
                ):
                    concurrentLoanRunCounter = 0
                    concurrentCount += 1
                    column = str(column) + "." + str(volumeCount)
                    concurrentDates[column] = 1

            maxedOutDates["Title"] = title
            maxedOutDates["MMS Id"] = mms_id
            maxedOutDates["Call Number"] = call_number

            for column in c.columns:
                if len(c[c[column] == "loan"]) + len(c[c[column] == "on loan"]) == barcodeCount and barcodeCount > 1:
                    maxedOutLoanRunCounter += 1
                elif (
                    maxedOutLoanRunCounter > 0
                    and len(c[c[column] == "loan"]) + len(c[c[column] == "on loan"]) < barcodeCount
                    and barcodeCount > 1
                ):
                    maxedOutLoanRunCounter = 0
                    maxedOutCount += 1
                    column = str(column) + "." + str(volumeCount)
                    maxedOutDates[column] = 1

            if concurrentCount > 0:
                dd = pd.concat([dd, pd.DataFrame([concurrentDates])], ignore_index=True)

            if maxedOutCount > 0:
                ee = pd.concat([ee, pd.DataFrame([maxedOutDates])], ignore_index=True)

            c.insert(loc=0, column="Title", value=title)
            c.insert(loc=1, column="Call Number", value=call_number)
            c.insert(loc=2, column="MMS Id", value=mms_id)
            c.insert(loc=3, column="Copy Count", value=barcodeCount)
            c.insert(loc=4, column="Loan Count", value=count)
            c.insert(loc=5, column="Concurrent Checkout Count", value=concurrentCount)
            c.insert(loc=6, column="All Copies in Use Count", value=maxedOutCount)

            c.to_excel(output_excel_file, sheet_name=str(mms_id), startrow=0, startcol=0, index=False)
            a.to_excel(output_excel_file, sheet_name="df A - " + str(mms_id), startrow=0, startcol=0, index=False)

            o = c.loc[:, [
                "Title", "Call Number", "MMS Id",
                "Copy Count", "Loan Count",
                "Concurrent Checkout Count", "All Copies in Use Count"
            ]].drop_duplicates()

            if volumeCount - 1 == 0:
                o.to_excel(writerAll, sheet_name="Counts", startrow=volumeCount - 1, startcol=0, index=False)
            else:
                o.to_excel(writerAll, sheet_name="Counts", startrow=volumeCount, startcol=0, header=False, index=False)

            x += count

        worksheet = writerAll.sheets["Counts"]
        worksheet.set_column("A:G", 30)

        green_format = workbook.add_format({"bg_color": "#C6EFCE", "font_color": "#006100"})
        deep_green_format = workbook.add_format({"bg_color": "#73c48b", "font_color": "#006100"})

        worksheet.conditional_format(1, 5, volumeCount + 1, 5, {
            "type": "cell", "criteria": ">", "value": 0, "format": green_format
        })
        worksheet.conditional_format(1, 6, volumeCount + 1, 6, {
            "type": "cell", "criteria": ">", "value": 0, "format": deep_green_format
        })

        worksheet.freeze_panes(1, 0)

        writerAll.close()
        output_excel_file.close()

        counts_buffer.seek(0)
        output_buffer.seek(0)

        return output_buffer
