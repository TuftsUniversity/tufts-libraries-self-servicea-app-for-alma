import os
import pandas as pd
import requests
import json
import re
from flask import current_app
from werkzeug.utils import secure_filename

barnes_and_noble_blueprint = Blueprint("barnes_and_noble_blueprint", __name__)


class OverlapAnalysis:
    def __init__(self, file_path):
        self.file_path = file_path

    def process(self):
        # Load the Excel file
        df_input = pd.read_excel(self.file_path, dtype=str, engine="openpyxl")
        df_input["course_code"] = ""
        df_input["section"] = ""
        df_input["course_name"] = ""
        df_input["processing_department"] = ""
        df = df_input.copy()

        for column in df.columns:
            df[column] = df[column].astype(str)
            df[column] = df[column].apply(lambda x: x.replace('"', ""))

        # Process each row
        for index, row in df.iterrows():
            semester = row["Term"]
            if "F" in semester:
                semester = semester.replace("F", "Fa")
            elif "W" in semester:
                semester = semester.replace("W", "Sp")

            course = row["Course"]
            section = row["Sec"]

            # Construct request URL
            request_url = (
                "https://api-na.hosted.exlibrisgroup.com/almaws/v1/courses?"
                + "apikey="
                + secrets_local.prod_courses_api_key
                + "&q=name~"
                + semester
                + "*"
                + row["Dept"]
                + "*"
                + row["Course"]
                + "*"
                + row["Sec"]
                + "&format=json"
            )

            response = requests.get(request_url).json()

            if int(response["total_record_count"]) > 1:
                for course in response["course"]:
                    course_name = course["name"]
                    result = bool(
                        re.match(
                            rf"^{semester}-[0\s]*{row['Dept']}\s*-[0\s]*{row['Course']}\s*-[0\s]*{row['Sec']}.+",
                            course_name,
                        )
                    )
                    if result:
                        correct_course = course
                        break
            else:
                correct_course = response.get("course", [{}])[0]

            df.loc[index, "course_code"] = correct_course.get(
                "code", "Error finding course"
            )
            df.loc[index, "section"] = correct_course.get(
                "section", "Error finding course"
            )
            df.loc[index, "course_name"] = correct_course.get(
                "name", "Error finding course"
            )
            df.loc[index, "processing_department"] = correct_course.get(
                "processing_department", {}
            ).get("desc", "Error finding processing department")

        output_path = os.path.join(
            current_app.config["DOWNLOAD_FOLDER"], "Updated_Barnes_and_Noble.xlsx"
        )
        df.to_excel(output_path, index=False)
        return output_path
