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
import io

# =====================================================================
# Class encapsulating all logic for processing concurrent loan checkouts.
# =====================================================================
class ConcurrentCheckouts:
    def __init__(self, file):
        self.file = file

    def process_file(self):

        cc = pd.read_excel(
            self.file,
            dtype={'MMS Id': 'str', 'Barcode': 'str', 'Permanent Call Number': 'str'},
            converters={'Loan Date': pd.to_datetime,
                        'Loan Time': pd.to_datetime,
                        'Return Date': pd.to_datetime,
                        'Return Time': pd.to_datetime},
            engine='openpyxl'
        )

        # In-memory output
        output_buffer = io.BytesIO()
        counts_buffer = io.BytesIO()

        output_excel_file = pd.ExcelWriter(output_buffer, engine='xlsxwriter')
        writerAll = pd.ExcelWriter(counts_buffer, engine='xlsxwriter')

        todays_date = datetime.now()
        current_time = datetime.now()

        cc['Return Date'] = cc['Return Date'].fillna(todays_date)
        cc['Return Time'] = cc['Return Time'].fillna(current_time)

        cc['Loan Date'] = cc['Loan Date'].apply(lambda x: x.strftime('%m-%d-%Y'))
        cc['Loan Time'] = cc['Loan Time'].apply(lambda x: x.strftime('%H:%M:%S'))
        cc['Return Date'] = cc['Return Date'].apply(lambda x: x.strftime('%m-%d-%Y'))
        cc['Return Time'] = cc['Return Time'].apply(lambda x: x.strftime('%H:%M:%S'))

        cc['Loan Datetime'] = pd.to_datetime(cc['Loan Date'] + ' ' + cc['Loan Time'])
        cc['Return Datetime'] = pd.to_datetime(cc['Return Date'] + ' ' + cc['Return Time'])

        cc = cc.sort_values(['MMS Id','Permanent Call Number', 'Barcode', 'Loan Datetime', 'Return Datetime'])

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

            title = cc.iloc[x]['Title']
            mms_id = cc.iloc[x]['MMS Id']
            call_number = cc.iloc[x]['Permanent Call Number']

            columns = [
                'Title', 'MMS Id', 'Permanent Call Number', 'Barcode',
                'Loan Datetime', 'Loan Date', 'Return Datetime', 'Return Date'
            ]
            a = pd.DataFrame(columns=columns)

            # ------------------------------------------------------------
            # Modern replacement for .append()
            # ------------------------------------------------------------
            a = pd.concat([
                a,
                pd.DataFrame([{
                    'Title': cc.iloc[x]['Title'],
                    'MMS Id': cc.iloc[x]['MMS Id'],
                    'Call Number': cc.iloc[x]['Permanent Call Number'],
                    'Barcode': cc.iloc[x]['Barcode'],
                    'Loan Datetime': cc.iloc[x]['Loan Datetime'],
                    'Loan Date': cc.iloc[x]['Loan Date'],
                    'Return Datetime': cc.iloc[x]['Return Datetime'],
                    'Return Date': cc.iloc[x]['Return Date']
                }])
            ], ignore_index=True)

            y += 1
            count += 1

            while (
                y < len(cc)
                and cc.iloc[y]['MMS Id'] == cc.iloc[y - 1]['MMS Id']
                and cc.iloc[y]['Permanent Call Number'] == cc.iloc[y - 1]['Permanent Call Number']
            ):
                # ------------------------------------------------------------
                # Modern replacement for .append()
                # ------------------------------------------------------------
                a = pd.concat([
                    a,
                    pd.DataFrame([{
                        'Title': cc.iloc[y]['Title'],
                        'MMS Id': cc.iloc[y]['MMS Id'],
                        'Call Number': cc.iloc[y]['Permanent Call Number'],
                        'Barcode': cc.iloc[y]['Barcode'],
                        'Loan Datetime': cc.iloc[y]['Loan Datetime'],
                        'Loan Date': cc.iloc[y]['Loan Date'],
                        'Return Datetime': cc.iloc[y]['Return Datetime'],
                        'Return Date': cc.iloc[y]['Return Date']
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
                firstLoanIndex = str(a.at[z, 'Loan Datetime'])
                barcode = str(a.iloc[z]['Barcode'])

                if firstLoanIndex in c:
                    firstLoanIndex += ":0" + str(z) + str(f)

                c.insert(loc=transactionWithinBarcodeCount, column=firstLoanIndex, value="")
                c.at[barcodeCount, firstLoanIndex] = "loan"
                transactionWithinBarcodeCount += 1
                fCount += 1

                firstReturnIndex = str(a.iloc[z]['Return Datetime'])
                if firstReturnIndex in c:
                    firstReturnIndex += ":0" + str(z) + str(f)

                c.insert(loc=transactionWithinBarcodeCount, column=firstReturnIndex, value="")
                c.at[barcodeCount, firstReturnIndex] = "return"
                transactionWithinBarcodeCount =+ 1
                transacationWithinBarcodeCountForCount += 1

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

            concurrentDates['Title'] = title
            concurrentDates['MMS Id'] = mms_id
            concurrentDates['Call Number'] = call_number

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
                    column = str(column) + '.' + str(volumeCount)
                    concurrentDates[column] = 1

            maxedOutDates['Title'] = title
            maxedOutDates['MMS Id'] = mms_id
            maxedOutDates['Call Number'] = call_number

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
                    column = str(column) + '.' + str(volumeCount)
                    maxedOutDates[column] = 1

            if concurrentCount > 0:
                dd = pd.concat([dd, pd.DataFrame([concurrentDates])], ignore_index=True)

            if maxedOutCount > 0:
                ee = pd.concat([ee, pd.DataFrame([maxedOutDates])], ignore_index=True)

            c.insert(loc=0, column='Title', value=title)
            c.insert(loc=1, column='Call Number', value=call_number)
            c.insert(loc=2, column='MMS Id', value=mms_id)
            c.insert(loc=3, column='Copy Count', value=barcodeCount)
            c.insert(loc=4, column='Loan Count', value=count)
            c.insert(loc=5, column="Concurrent Checkout Count", value=concurrentCount)
            c.insert(loc=6, column="All Copies in Use Count", value=maxedOutCount)

            c.to_excel(output_excel_file, sheet_name=str(mms_id), startrow=0, startcol=0, index=False)
            a.to_excel(output_excel_file, sheet_name="df A - " + str(mms_id), startrow=0, startcol=0, index=False)

            o = c.loc[:, [
                'Title', 'Call Number', 'MMS Id',
                'Copy Count', 'Loan Count',
                'Concurrent Checkout Count', 'All Copies in Use Count'
            ]].drop_duplicates()

            if volumeCount - 1 == 0:
                o.to_excel(writerAll, sheet_name='Counts', startrow=volumeCount - 1, startcol=0, index=False)
            else:
                o.to_excel(writerAll, sheet_name='Counts', startrow=volumeCount, startcol=0, header=False, index=False)

            x += count

        worksheet = writerAll.sheets['Counts']
        worksheet.set_column('A:G', 30)

        green_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
        deep_green_format = workbook.add_format({'bg_color': '#73c48b', 'font_color': '#006100'})

        worksheet.conditional_format(1, 5, volumeCount + 1, 5, {
            'type': 'cell', 'criteria': '>', 'value': 0, 'format': green_format
        })
        worksheet.conditional_format(1, 6, volumeCount + 1, 6, {
            'type': 'cell', 'criteria': '>', 'value': 0, 'format': deep_green_format
        })

        worksheet.freeze_panes(1, 0)

        writerAll.close()
        output_excel_file.close()

        counts_buffer.seek(0)
        output_buffer.seek(0)

        return output_buffer
