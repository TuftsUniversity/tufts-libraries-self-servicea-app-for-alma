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
import os
from .sql import SQLProcessor

sql_blueprint = Blueprint("sql", __name__)
print("✅ SQL Blueprint loaded")



@sql_blueprint.route("/", methods=["GET"])
def index():
    return render_template("sql_processor.html")

@sql_blueprint.route("/process_sql", methods=["POST"])
def process_sql():
    sql_input_1 = request.form.get("sql_input_1")
    sql_input_2 = request.form.get("sql_input_2")
    join_type = request.form.get("join_type")
    join_field_left = request.form.get("join_field_left", "").strip()
    join_field_right = request.form.get("join_field_right", "").strip()

    sql_processor = SQLProcessor(
        sql_input_1, sql_input_2, join_type,
        join_field_left=join_field_left,
        join_field_right=join_field_right
    )



    if not sql_input_1 or not sql_input_2:
        return redirect(url_for("sql.index"))

    #sql_processor = SQLProcessor(sql_input_1, sql_input_2, join_type, join_field)
    output_sql = sql_processor.process_sql()

    return render_template("sql_processor.html", output_sql=output_sql)

