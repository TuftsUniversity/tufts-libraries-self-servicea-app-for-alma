from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    send_file,
    current_app,
    render_template,
    send_from_directory
)
from werkzeug.utils import secure_filename
import os
from .sql import SQLProcessor
from flask_cors import CORS, cross_origin


sql_blueprint = Blueprint("sql", __name__)
print("✅ SQL Blueprint loaded")


# Serve component.js
@sql_blueprint.route('/component.js')
@cross_origin()
def serve_component():

    component_path = os.path.join(os.path.dirname(__file__))  # correct package directory
    return send_from_directory(component_path, 'component.js', mimetype='application/javascript')
# Serve component-template
@sql_blueprint.route('/component-template')
@cross_origin()
def serve_component_template():


    return render_template("sql_processor.html", is_component=True)


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


