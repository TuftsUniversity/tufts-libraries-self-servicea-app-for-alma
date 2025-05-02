import os
import pandas as pd
import re
from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    send_file,
    current_app,
    render_template,
)
from werkzeug.utils import secure_filename
import io
from io import BytesIO
import zipfile
import dotenv
import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
load_dotenv()
import json
import requests
import time
import pymarc as pym
import xml.etree.cElementTree as et


def zip_files(filenames):
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in filenames:
            data = open(filename, "rb").read()
            zf.writestr(os.path.basename(filename), data)
    memory_file.seek(0)
    return memory_file


class Bib2Holdings541:
    def __init__(self, file_stream):
        self.file_stream = file_stream
        
        self.sandbox_bib_api_key = os.getenv("sandbox_bib_api_key")
        self.analytics_api_key = os.getenv("analytics_api_key")
        self.analytics_url = os.getenv("analytics_url")
        self.bib_url = os.getenv("bib_url")
        self.headers = {'Content-Type': 'application/xml'}
        
        self.errorCount = 0
        # mismatchCount = 0
        self.successCount = 0

        self.count_file = io.BytesIO()

        self.output_file = io.BytesIO()
        self.output_file.write(
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><holdings>'.encode('utf-8'))

        self.error_file = io.BytesIO()

    def zip_files(filenames):
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename in filenames:
                data = open(filename, "rb").read()
                zf.writestr(os.path.basename(filename), data)
        memory_file.seek(0)
        return memory_file

    def process(self):
        mappings = self.getLocations()
        bibList = []
        bibListCounter = 0
        for line in self.file_stream:
            line = line.decode("utf-8").strip()
            
            line = line.replace("\r\n", "")
            bibList.append(line)

            
            bibListCounter += 1

        print("Number of bib records in input file: " + str(bibListCounter) + "\n")

        headers = {"Content-Type": "application/xml"}

        # count_file = open('Success and Error Counts.txt', 'w+')
        # output_file = open("Output/updated_holdings.xml", "w+")
        # output_file.write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><holdings>')
        # error_file = open("Output/records_with_errors.txt", "w+")
        fiveFortyOneCount = 0
        for mms_id in bibList:
            print("MMS ID: " + str(mms_id))

            bib_url = self.bib_url + str(mms_id) + "?apikey=" + self.sandbox_bib_api_key

            holdings_url = (
                self.bib_url
                + str(mms_id)
                + "/holdings?apikey="
                + self.sandbox_bib_api_key
            )

            print(bib_url + "\n")
            print("\n" + holdings_url + "\n")
            bib_record = requests.get(bib_url)
            bib_record_str = bib_record.content.decode("utf-8")
            print("\nBib record: " + bib_record.text + "\n")
            attached_holdings = requests.get(holdings_url)

            attached_holdings_str = attached_holdings.content.decode("utf-8")
            print("\nHoldings: " + attached_holdings_str + "\n")

            # Python 2

            # unicode_bib_record = unicode(attached_holdings_str)

            # Python 3

            unicode_bib_record = str(bib_record_str)
            if re.search("<errorsExist>true</errorsExist>", unicode_bib_record):
                self.error_file.write("MMS ID " + mms_id + " not in system\n".encode('utf-8'))
                self.errorCount += 1
                print("MMS ID " + mms_id + " not in system\n")
                continue

            holdings_count_match = re.search(
                r'holdings\stotal_record_count\="(\d+)"', attached_holdings_str
            )
            holdingsCount = int(holdings_count_match.group(1))

            if holdingsCount == 0:
                self.error_file.write("No holdings for MMS ID" + mms_id + "\n")
                print("No holdings for MMS ID" + mms_id + "\n")
                self.errorCount += 1
                continue

            # Python 2
            # unicode_attached_holdings = unicode(attached_holding_str)

            # Python 3

            unicode_attached_holdings = str(attached_holdings_str)

            # print(unicode_attached_holdings)
            # sys.exit()

            bib_record = pym.parse_xml_to_array(io.StringIO(unicode_bib_record))

            tree_orig = et.ElementTree(et.fromstring(attached_holdings_str))

            root_orig = tree_orig.getroot()

            # for element in root_orig.iter():
            #    print(element.text)
            #    sys.exit()
            holdings_xml_string = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><holdings>'
            )
            for attached_holding in root_orig.findall(".//holding"):
                print("\n\nHolding: " + str(et.tostring(attached_holding)) + "\n")

                holding_id = attached_holding.find("holding_id").text

                print("\nHolding ID: " + str(holding_id) + "\n")

                try:
                    holding_record = requests.get(
                        self.bib_url
                        + str(mms_id)
                        + "/holdings/"
                        + str(holding_id)
                        + "?apikey="
                        + self.sandbox_bib_api_key
                    )

                except:
                    print(
                        "Can't retrieve holding with MMS ID: "
                        + mms_id
                        + " and holding ID: "
                        + str(holding_id)
                        + "\n"
                    )
                    self.error_file.write(
                        "Can't retrieve holding with MMS ID: "
                        + mms_id
                        + " and holding ID: "
                        + str(holding_id)
                        + "\n".encode('utf-8'))
                    self.errorCount += 1
                    continue
                holding_string = holding_record.content.decode("utf-8")

                holding_string = holding_string.replace(
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', ""
                )

                holdings_xml_string += holding_string

            holdings_xml_string += "</holdings>"

            # Python 2
            # unicode_holdings_xml_string = unicode(holdings_xml_string, 'utf-8')

            # Python 3
            unicode_holdings_xml_string = holdings_xml_string

            b = 1

            tree = et.ElementTree(et.fromstring(unicode_holdings_xml_string))
            root = tree.getroot()

            countList = []
            for five_forty_one in bib_record[0].get_fields("541"):
                found541 = False
                fiveFortyOneCount += 1
                subfield_3 = five_forty_one["3"]
                # if not subfield_3 in all541:
                #     all541.append(subfield_3)
                print("\n\nRepeated 541 subfield 3: \n" + str(subfield_3) + "\n\n")
                print("\n\n541: \n" + str(five_forty_one) + "\n\n")

                try:
                    location_541_match = re.search(
                        r"^(.+Library|TISCH|HHSL|MUSIC|GINN|VET|Tisch|Ginn|Music|Vet|Hirsh|EUR)[ ]?(.+)?([ ]print)?[ ]+copy",
                        subfield_3,
                        re.IGNORECASE,
                    )
                    library_541 = location_541_match.group(1)
                    library_541 = library_541.encode("utf-8", "replace").decode()
                except:
                    print(
                        "Library or location in 541 for MMS ID: "
                        + str(mms_id)
                        + " and holding ID: "
                        + str(holding_id)
                        + " is not retrievable or is not an expected value\n"
                    )
                    self.error_file.write(
                        "Library or location in 541 for MMS ID: "
                        + str(mms_id)
                        + " is not retrievable or is not an expected value\n"
                    .encode('utf-8'))
                    errorCount += 1
                    continue

                print(
                    "\nLibrary: <boundary>"
                    + library_541
                    + "</boundary>"
                    + "Data type: "
                    + str(type(library_541))
                    + "\n"
                )

                location_541 = ""
                library = ""
                location = ""
                location_code = ""
                location_description = ""
                location_suffix = ""
                try:
                    location_541 = location_541_match.group(2)
                    location_541 = location_541.encode("utf-8", "replace")
                except:
                    location_541 = ""

                try:
                    location_541 = location_541.decode("utf-8")
                except:
                    pass

                if (
                    library_541 == "Tisch Library"
                    or str(library_541) == "TISCH"
                    or str(library_541) == "Tisch"
                ):
                    library = "TISCH"
                elif (
                    str(library_541) == "Ginn Library"
                    or str(library_541) == "GINN"
                    or str(library_541) == "Ginn"
                ):
                    library = "GINN"
                elif (
                    library_541 == "Lilly Music Library"
                    or str(library_541) == "MUSIC"
                    or str(library_541) == "Music"
                ):
                    library = "MUSIC"
                elif (
                    library_541 == "W. Van Alan Clark, Jr. Library"
                    or str(library_541) == "SMFA"
                ):
                    library = "SMFA"
                elif (
                    library_541 == "Webster Family Library"
                    or str(library_541) == "VET"
                    or str(library_541) == "Vet"
                ):
                    library = "VET"
                elif (
                    library_541 == "Hirsch Health Sciences Library"
                    or str(library_541) == "Hirsh Health Sciences Library"
                    or str(library_541) == "HHSL"
                    or str(library_541) == "Hirsh"
                ):
                    library = "HIRSH"
                elif library_541 == "EUR":
                    library = "Talloires"
                else:
                    print(
                        "Library in 541 for MMS ID: "
                        + str(mms_id)
                        + " is not retrievable or is not an expected value\n"
                    )
                    self.error_file.write(
                        "Library in 541 for MMS ID: "
                        + str(mms_id)
                        + " is not retrievable or is not an expected value\n"
                    .encode('utf-8'))
                    errorCount += 1
                    continue

                print("\nLibrary for 852 from 541: " + library + "\n")
                print("Location_541:               " + str(location_541) + "\n")

                for full_holding in root.findall("holding"):
                    print(
                        "\nHolding record " + str(b) + ": \n" + str(full_holding) + "\n"
                    )
                    b += 1
                    holding_id = full_holding.find("holding_id").text
                    c = 0
                    print("541: \n" + str(bib_record))

                    holding = pym.parse_xml_to_array(
                        io.StringIO(et.tostring(full_holding).decode("utf-8"))
                    )[0]

                    full_holding_string = et.tostring(full_holding)

                    foundLocation = False

                    library_locations = mappings[library]

                    for dict_location in library_locations:
                        if location_541.lower() in dict_location.lower():
                            location_description = dict_location
                            foundLocation = True
                            break

                    if str(location_541) != "" and foundLocation == True:
                        location_code = mappings[library][location_description]

                    elif (
                        str(location_541) == ""
                        and holding["852"]["b"] == library
                        and library not in countList
                    ):
                        location_code = holding["852"]["c"]
                        countList.append(library)
                        foundLocation == True
                    # elif holdingsCount > 1:
                    #     print("No location specified in 541, but more than one holding in record for " + str(mms_id) + "\n")
                    #     error_file.write("No location specified in 541, but more than one holding in record for " + str(mms_id) + "\n")
                    #     errorCount += 1
                    #     continue

                    # library_and_location = library + location_suffix

                    # print("Library and location: " + library_and_location + "\n\n")

                    if foundLocation == True:
                        print("Location code: " + location_code + "\n")
                        if holding["852"]["c"] == location_code:
                            found541 = True
                            success = self.update_holding(
                                holding,
                                holding_id,
                                full_holding_string,
                                five_forty_one,
                                mms_id,
                            )
                            # matched541.append(subfield_3)
                            if success == True:
                                self.successCount += 1
                            else:
                                print(
                                    "Couldn't write holding "
                                    + str(holding_id)
                                    + " for "
                                    + str(mms_id)
                                    + "to Alma via the API.\n"
                                )
                                self.error_file.write(
                                    "Couldn't write holding "
                                    + str(holding_id)
                                    + " for "
                                    + str(mms_id)
                                    + "to Alma via the API.\n"
                                .encode('utf-8'))
                                self.errorCount += 1
                                continue

                    else:
                        # print("Could not match location field from 541 to a location in Alma for " + str(mms_id) + ". This might be because there is no location in the 541, there's no matching library, or there's a typo in the 541 location.\n")
                        # error_file.write("Could not match location field from 541 to a location in Alma for " + str(mms_id) + ". This might be because there is no location in the 541, there's no matching library, or there's a typo in the 541 location.\n")
                        # mismatchCount += 1
                        continue

                if found541 == False:
                    print(
                        "The 541 for bib record "
                        + str(mms_id)
                        + " could not match to a holding location.\n"
                    )
                    self.error_file.write(
                        "The 541 for bib record "
                        + str(mms_id)
                        + " could not match to a holding location.\n"
                    .encode('utf-8'))
                    self.errorCount += 1

                # Python 2

                # holding = pym.parse_xml_to_array(io.StringIO(unicode(et.tostring(full_holding))))[0]

                # Python 3

        print("Number of 541s: " + str(fiveFortyOneCount) + "\n")
        self.count_file.write(
            ("Number of 541s: " + str(fiveFortyOneCount) + "\n").encode("utf-8")
        )

        print("Records successfully updated: " + str(self.successCount) + "\n")
        self.count_file.write(
            ("Records successfully updated: " + str(self.successCount) + "\n").encode("utf-8")
        )

        print("Records that couldn't be updated.  Check error file: " + str(self.errorCount) + "\n")
        self.count_file.write(
            ("Records that couldn't be updated.  Check error file: " + str(self.errorCount) + "\n").encode("utf-8")
        )

       
        # print("Matching errors between 541 and holdings. Check error file:           " + str(mismatchCount) + "\n")
        # count_file.write("atching errors between 541 and holdings. Check error file: " + str(mismatchCount) + "\n")

        self.count_file.seek(0)
        self.output_file.seek(0)
        self.error_file.seek(0)

        # Step 2: Create ZIP Archive in Memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("Count File.txt", self.count_file.getvalue())
            zip_file.writestr("Errors.txt", self.error_file.getvalue())
            zip_file.writestr("Output File.xml", self.output_file.getvalue())

        zip_buffer.seek(0)

        # Step 3: Return ZIP File for Download
        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name="rollup_files.zip",
        )

    def update_holding(self, 
        holding, holding_id, full_holding_string, five_forty_one, mms_id):
        holding.add_field(five_forty_one)
        print("Holding with new field: \n" + str(holding) + "\n\n\n")
        updated_holding = pym.record_to_xml(holding).decode("utf-8")

        full_holding_string = full_holding_string.decode("utf-8")

        full_updated_holding = re.sub(
            r"<record>(.+)</record>", updated_holding, full_holding_string
        )

        print("Updated XML Holding Record: \n" + full_updated_holding + "\n")

        full_updated_holding = full_updated_holding.replace(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', ""
        )

        # success = True

        # faulty_xml = "<holding></holding>"
        #
        # # full_holdings_xml = root.find('holding/holding_id=')
        #
        #
        response = requests.put(
            self.bib_url
            + str(mms_id)
            + "/holdings/"
            + str(holding_id)
            + "?apikey="
            + self.sandbox_bib_api_key,
            data=full_updated_holding,
            headers=self.headers,
        )
        #
        time.sleep(2)
        print(response.content)
        # #
        # #
        # # # response = requests.put("https://api-na.hosted.exlibrisgroup.com/almaws/v1/bibs/" + str(mms_id) + "/holdings/" + str(holding_id) + "?apikey=", data=full_updated_holding, headers=headers)
        # # #
        # # # print(response.content)
        if re.search("<errorsExist>true</errorsExist>", response.content.decode("utf-8")):
            print("Couldn't write back to Alma for MMS ID: " + mms_id + "\n")
            self.error_file.write(
                "Couldn't write back to Alma for MMS ID: " + mms_id + "\n"
            )
            success = False
        else:
            xml_chunk = (
                "<MMS_ID_" + mms_id + ">" + full_updated_holding + "</MMS_ID_" + mms_id + ">"
            )
            self.output_file.write(xml_chunk.encode("utf-8"))

            

            success = True

        # print(response.content)
        #
        # print(success)
        #
        # sys.exit()
        return success

    def getLocations(self):

        url = (
            self.analytics_url
            + self.analytics_api_key
        )
        limit = "&limit=1000"
        format = "&format=xml"
        path = "&path=%2Fshared%2FTufts+University%2FReports%2FCataloging%2FAdding+541+to+Holdings+Records%2FLocation+Name-Location+Code"

        report = requests.get(url + format + path + limit)

        # print("\nReport Content: \n" + report.content)

        # report_outfile = BytesIO()

        # # report_str = report.content.decode('utf-8')
        # report_outfile.write(str(report.content).encode('utf-8'))

        # # print("\n\nReport: \n" + report.content)

        # report_outfile.close()

        tree = et.ElementTree(et.fromstring(report.content))

        # print("\nTree: " + tree.text + "\n")

        root = tree.getroot()

        print("\nRoot: \n" + str(root.text) + "\n")

        reportDict = {}
        # for element in root.iter('{urn:schemas-microsoft-com:xml-analysis:rowset}Row'):
        # print("\n\nAll Elements: \n" + str(list(root.iter())))

        for element in root.iter():
            library = ""
            code = ""
            description = ""
            if re.match(r".*Row", element.tag):
                for sub_element in element.iter():
                    if re.match(r".*Column2", sub_element.tag):
                        code = sub_element.text
                    if re.match(r".*Column3", sub_element.tag):
                        description = sub_element.text
                    elif re.match(r".*Column1", sub_element.tag):
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
                print(
                    "Library: "
                    + str(i)
                    + "; Description: "
                    + str(j)
                    + "; Code: "
                    + str(reportDict[i][j])
                    + "\n"
                )
        return reportDict
