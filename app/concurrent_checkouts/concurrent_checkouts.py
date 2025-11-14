# =====================================================================
# Imports: Provides pandas for data processing, numpy for misc numerics,
# datetime for timestamps, OS for filesystem work, and Excel libraries
# (xlsxwriter/openpyxl) for reading/writing Excel output.
# =====================================================================
import pandas as pd
import numpy as np
from datetime import datetime
import os
import xlsxwriter
import openpyxl


# =====================================================================
# Class encapsulating all logic for processing concurrent loan checkouts.
# output_dir allows caller to control where output Excel files go.
# Creates directory automatically, which is useful for production workflows.
# =====================================================================
class ConcurrentCheckouts:
    def __init__(self, output_dir: str = "./Output"):
        """
        Initialize a ConcurrentCheckouts processor.

        Args:
            output_dir (str): Directory where output Excel files will be written.
        """
        self.output_dir = output_dir
        if not os.path.isdir(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)


    # =====================================================================
    # Main method: Reads Excel, normalizes Loan/Return date/times, sorts,
    # groups by title/MMS/Call number, computes concurrency, then writes:
    #   - Detailed sheets per MMS ID
    #   - Summary counts sheet
    #
    # NOTE: Huge function — could be split for readability.
    # =====================================================================
    def process_file(self, filename: str):

        # -------------------------------------------------------------
        # Ensure output directory exists. (Redundant with __init__, but harmless.)
        # -------------------------------------------------------------
        oDir = "./Output"
        if not os.path.isdir(oDir) or not os.path.exists(oDir):
            os.makedirs(oDir)

        # -------------------------------------------------------------
        # Load Excel into dataframe.
        # dtype ensures certain IDs remain strings (prevent leading zero loss).
        # converters parse date/time columns correctly.
        # openpyxl engine required for .xlsx.
        # -------------------------------------------------------------
        cc = pd.read_excel(
            filename,
            dtype={'MMS Id': 'str', 'Barcode': 'str', 'Permanent Call Number': 'str'},
            converters={'Loan Date': pd.to_datetime,
                        'Loan Time': pd.to_datetime,
                        'Return Date': pd.to_datetime,
                        'Return Time': pd.to_datetime},
            engine='openpyxl'
        )

        # -------------------------------------------------------------
        # Replace missing return dates/times with NOW.
        # This effectively treats unreturned items as still on loan.
        # -------------------------------------------------------------
        todays_date = datetime.now()
        current_time = datetime.now()

        cc['Return Date'] = cc['Return Date'].fillna(todays_date)
        cc['Return Time'] = cc['Return Time'].fillna(current_time)

        # -------------------------------------------------------------
        # Convert timestamp columns into clean strings for concatenation.
        # NOTE: This destroys timezone info and makes everything naive.
        # -------------------------------------------------------------
        cc['Loan Date'] = cc['Loan Date'].apply(lambda x: x.strftime('%m-%d-%Y'))
        cc['Loan Time'] = cc['Loan Time'].apply(lambda x: x.strftime('%H:%M:%S'))
        cc['Return Date'] = cc['Return Date'].apply(lambda x: x.strftime('%m-%d-%Y'))
        cc['Return Time'] = cc['Return Time'].apply(lambda x: x.strftime('%H:%M:%S'))

        # -------------------------------------------------------------
        # Recombine back into true datetime objects.
        # These are the actual orderable timestamps.
        # -------------------------------------------------------------
        cc['Loan Datetime'] = pd.to_datetime(cc['Loan Date'] + ' ' + cc['Loan Time'])
        cc['Return Datetime'] = pd.to_datetime(cc['Return Date'] + ' ' + cc['Return Time'])

        # -------------------------------------------------------------
        # Sort loans across multiple fields.
        # Ensures grouping loops work correctly.
        # -------------------------------------------------------------
        cc = cc.sort_values(['MMS Id', 'Permanent Call Number', 'Barcode',
                             'Loan Datetime', 'Return Datetime'])

        # -------------------------------------------------------------
        # dd = dataframe of concurrent loan events
        # ee = dataframe of "maxed out" (all copies in use) events
        # -------------------------------------------------------------
        dd = pd.DataFrame()
        ee = pd.DataFrame()

        # -------------------------------------------------------------
        # Prepare writer objects.
        # One file holds detailed sheets, one holds summary counts.
        # -------------------------------------------------------------
        output_excel_file = pd.ExcelWriter(oDir + '/Output Dataframes.xlsx', engine='xlsxwriter')
        writerAll = pd.ExcelWriter(oDir + '/Counts.xlsx', engine='xlsxwriter')

        # -------------------------------------------------------------
        # Initialize counters.
        # Many could be local, but left intact as per original code.
        # -------------------------------------------------------------
        x = 0
        volumeCount = 0
        totalBarcodeCount = 0
        totalCount = 0
        totalTransactionCount = 0
        transacationWithinBarcodeCountForCount = 0

        workbook = writerAll.book

        # =====================================================================
        # OUTER LOOP: iterate through sorted dataframe by MMS/Call number.
        # Each loop processes a group of rows representing one resource/set.
        # =====================================================================
        while x < len(cc):
            volumeCount += 1
            y = x
            count = 0

            # Extract metadata for this block
            title = cc.iloc[x]['Title']
            mms_id = cc.iloc[x]['MMS Id']
            call_number = cc.iloc[x]['Permanent Call Number']
            barcode = cc.iloc[x]['Barcode']

            # Prepare container for per-item loans within group
            columns = [
                'Title', 'MMS Id', 'Permanent Call Number', 'Barcode',
                'Loan Datetime', 'Loan Date', 'Return Datetime', 'Return Date'
            ]
            a = pd.DataFrame(columns=columns)

            # First row for this item
            a = pd.concat([
                a,
                pd.DataFrame({
                    'Title': cc.iloc[x]['Title'],
                    'MMS Id': cc.iloc[x]['MMS Id'],
                    'Call Number': cc.iloc[x]['Permanent Call Number'],
                    'Barcode': cc.iloc[x]['Barcode'],
                    'Loan Datetime': cc.iloc[x]['Loan Datetime'],
                    'Loan Date': cc.iloc[x]['Loan Date'],
                    'Return Datetime': cc.iloc[x]['Return Datetime'],
                    'Return Date': cc.iloc[x]['Return Date']
                }, index=[0])
            ])

            y += 1
            count += 1

            # -------------------------------------------------------------
            # INNER GROUP SCAN: Collect all rows belonging to same MMS + call number
            # -------------------------------------------------------------
            while (y < len(cc)
                   and cc.iloc[y]['MMS Id'] == cc.iloc[y - 1]['MMS Id']
                   and cc.iloc[y]['Permanent Call Number'] == cc.iloc[y - 1]['Permanent Call Number']):
                a = pd.concat([
                    a,
                    pd.DataFrame({
                        'Title': cc.iloc[y]['Title'],
                        'MMS Id': cc.iloc[y]['MMS Id'],
                        'Call Number': cc.iloc[y]['Permanent Call Number'],
                        'Barcode': cc.iloc[y]['Barcode'],
                        'Loan Datetime': cc.iloc[y]['Loan Datetime'],
                        'Loan Date': cc.iloc[y]['Loan Date'],
                        'Return Datetime': cc.iloc[y]['Return Datetime'],
                        'Return Date': cc.iloc[y]['Return Date']
                    }, index=[0])
                ])
                y += 1
                count += 1

            # =====================================================================
            # Build concurrency table `c`: columns = timestamps, rows = barcodes.
            # Each cell = "loan" or "return" marking event boundaries.
            # =====================================================================
            z = 0
            barcodeDict = {}
            barcodeCount = 0
            transactionWithinBarcodeCount = 0
            c = pd.DataFrame()

            # -------------------------------------------------------------
            # Loop through each row in this block (each transaction)
            # -------------------------------------------------------------
            while z < count:
                fCount = 0
                f = z + 1
                a = a.reset_index(drop=True)
                firstLoanIndex = str(a.at[z, 'Loan Datetime'])
                barcode = str(a.iloc[z]['Barcode'])

                # Avoid duplicate column names by appending suffixes
                if firstLoanIndex in c:
                    firstLoanIndex += ":0" + str(z) + str(f)

                # Insert loan column for this barcode
                c.insert(loc=transactionWithinBarcodeCount, column=firstLoanIndex, value="")
                c.at[barcodeCount, firstLoanIndex] = "loan"
                transactionWithinBarcodeCount += 1
                fCount += 1

                # Now insert return column
                firstReturnIndex = str(a.iloc[z]['Return Datetime'])
                if firstReturnIndex in c:
                    firstReturnIndex += ":0" + str(z) + str(f)

                c.insert(loc=transactionWithinBarcodeCount, column=firstReturnIndex, value="")
                c.at[barcodeCount, firstReturnIndex] = "return"
                transactionWithinBarcodeCount =+ 1   # NOTE: BUG? Probably meant += 1
                transacationWithinBarcodeCountForCount += 1

                # ---------------------------------------------------------
                # Collect additional loans from same barcode
                # ---------------------------------------------------------
                while f < count and a.iloc[z]["Barcode"] == a.iloc[f]["Barcode"]:
                    loanIndex = str(a.iloc[f]['Loan Datetime'])
                    if loanIndex in c:
                        loanIndex += ":0" + str(z) + str(f)

                    c.insert(loc=transactionWithinBarcodeCount, column=loanIndex, value="")
                    c.at[barcodeCount, loanIndex] = "loan"
                    transactionWithinBarcodeCount += 1

                    returnIndex = str(a.iloc[f]['Return Datetime'])
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

            # =====================================================================
            # Fill all "in-between" times for each barcode so that
            # consecutive columns show continuous "loan" status.
            # =====================================================================
            if barcodeCount > 1:
                l = 0
                while l < barcodeCount:
                    m = 0
                    while m < len(c.columns):
                        d = 1
                        if c.iat[l, m] == "loan":
                            while (m + d < len(c.columns)
                                   and c.iat[l, m + d] not in ("loan", "return")):
                                c.iat[l, m + d] = "loan"
                                d += 1
                        m += d
                    l += 1

            # =====================================================================
            # Detect concurrent loan periods (2+ barcodes loaned at same time)
            # =====================================================================
            concurrentDates = {}
            maxedOutDates = {}

            concurrentCount = 0
            maxedOutCount = 0
            concurrentLoanRunCounter = 0
            maxedOutLoanRunCounter = 0

            # Metadata for summary rows
            concurrentDates['Title'] = title
            concurrentDates['MMS Id'] = mms_id
            concurrentDates['Call Number'] = call_number

            # -------------------------------------------------------------
            # Check each timestamp column for >1 simultaneous loans
            # -------------------------------------------------------------
            for column in c.columns:
                if len(c[c[column] == "loan"]) + len(c[c[column] == "on loan"]) > 1 and barcodeCount > 1:
                    concurrentLoanRunCounter += 1
                elif concurrentLoanRunCounter > 0 and \
                     len(c[c[column] == "loan"]) + len(c[c[column] == "on loan"]) <= 1:
                    concurrentLoanRunCounter = 0
                    concurrentCount += 1
                    concurrentDates[str(column) + '.' + str(volumeCount)] = 1

            # =====================================================================
            # Detect maxed-out periods (all copies in use simultaneously)
            # =====================================================================
            maxedOutDates['Title'] = title
            maxedOutDates['MMS Id'] = mms_id
            maxedOutDates['Call Number'] = call_number

            for column in c.columns:
                if len(c[c[column] == "loan"]) + len(c[c[column] == "on loan"]) == barcodeCount and barcodeCount > 1:
                    maxedOutLoanRunCounter += 1
                elif maxedOutLoanRunCounter > 0 and \
                     len(c[c[column] == "loan"]) + len(c[c[column] == "on loan"]) < barcodeCount:
                    maxedOutLoanRunCounter = 0
                    maxedOutCount += 1
                    maxedOutDates[str(column) + '.' + str(volumeCount)] = 1

            # Add to summary dataframes
            if concurrentCount > 0:
                dd = pd.concat([dd, pd.DataFrame(concurrentDates, index=[0])])

            if maxedOutCount > 0:
                ee = ee.append(maxedOutDates, ignore_index=True)

            # =====================================================================
            # Prepare per-MMS sheet: add metadata columns, write to Excel.
            # =====================================================================
            c.insert(loc=0, column='Title', value=title)
            c.insert(loc=1, column='Call Number', value=call_number)
            c.insert(loc=2, column='MMS Id', value=mms_id)
            c.insert(loc=3, column='Barcode', value=barcode)
            c.insert(loc=4, column='Copy Count', value=barcodeCount)
            c.insert(loc=5, column='Loan Count', value=count)
            c.insert(loc=6, column="Concurrent Checkout Count", value=concurrentCount)
            c.insert(loc=7, column="All Copies in Use Count", value=maxedOutCount)

            c.to_excel(output_excel_file, sheet_name=str(mms_id),
                       startrow=0, startcol=0, index=False)

            a.to_excel(output_excel_file, sheet_name="df A - " + str(mms_id),
                       startrow=0, startcol=0, index=False)

            # =====================================================================
            # Extract short summary row for "Counts.xlsx"
            # =====================================================================
            o = c.loc[:, [
                'Title', 'Call Number', 'Barcode', 'MMS Id',
                'Copy Count', 'Loan Count',
                'Concurrent Checkout Count', 'All Copies in Use Count'
            ]]
            o = o.drop_duplicates()

            if volumeCount - 1 == 0:
                o.to_excel(writerAll, sheet_name='Counts',
                           startrow=volumeCount - 1, startcol=0, index=False)
            else:
                o.to_excel(writerAll, sheet_name='Counts',
                           startrow=volumeCount, startcol=0, header=False, index=False)

            # Advance outer loop
            x += count

        # =====================================================================
        # Excel Formatting for Counts.xlsx summary
        # =====================================================================
        worksheet = writerAll.sheets['Counts']
        worksheet.set_column('A:A', 30)
        worksheet.set_column('B:B', 30)
        worksheet.set_column('C:C', 30)
        worksheet.set_column('D:D', 15)
        worksheet.set_column('E:E', 15)
        worksheet.set_column('F:F', 30)
        worksheet.set_column('G:G', 30)

        # Conditional formatting for highlighting non-zero counts
        green_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
        deep_green_format = workbook.add_format({'bg_color': '#73c48b', 'font_color': '#006100'})

        worksheet.conditional_format(1, 5, volumeCount + 1, 5, {
            'type': 'cell', 'criteria': '>', 'value': 0, 'format': green_format
        })
        worksheet.conditional_format(1, 6, volumeCount + 1, 6, {
            'type': 'cell', 'criteria': '>', 'value': 0, 'format': deep_green_format
        })

        worksheet.freeze_panes(1, 0)

        # =====================================================================
        # Finalize and return file writers
        # =====================================================================
        writerAll.close()
        output_excel_file.close()

        return output_excel_file
