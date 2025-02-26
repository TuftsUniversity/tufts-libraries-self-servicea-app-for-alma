from flask import Blueprint, render_template

# Define the main blueprint
main_blueprint = Blueprint("main", __name__)

# Define the route for the main page
@main_blueprint.route("/")
def index():
    """
    Render the index.html template as the main page.
    """
    return render_template("index.html")

