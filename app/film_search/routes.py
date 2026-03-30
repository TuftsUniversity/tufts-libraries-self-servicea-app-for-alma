import pandas as pd
from flask import Blueprint, render_template, request, send_file, redirect, url_for, flash, send_from_directory,current_app
from .search_swank import SwankSearch

from .search_criterion import SearchCriterion
from .search_selenium import SearchKanopy
film_search_blueprint = Blueprint(
    "film_search", __name__, url_prefix="/film_search"
)
from .scrapers.docuseek_scraper import DocuseekScraper
from .scrapers.newday_scraper import NewDayScraper
from .search_alexander import AlexanderScraper
from bs4 import BeautifulSoup
import requests
import io
from flask_cors import CORS, cross_origin
import os

@film_search_blueprint.route("/", methods=["GET"])
def index():
    is_component = request.args.get("is_component", "false").lower() == "true"
    return render_template("film_search.html", is_component=is_component)


# Serve component.js
@film_search_blueprint.route('/component.js')
@cross_origin()
def serve_component():

    component_path = os.path.join(current_app.root_path, 'film_search')
    return send_from_directory(component_path, 'component.js', mimetype='application/javascript')

# Serve component-template
@film_search_blueprint.route('/component-template')
@cross_origin()
def serve_component_template():


    return render_template("film_search.html", is_component=True)


@film_search_blueprint.route("/search_all", methods=["GET","POST"])
def search_all():

    title = (request.form.get("title") or "").strip()
    if not title:   
        flash("Please enter a film title.")
    
    swank_buffer, kanopy_buffer, criterion_buffer, docuseek_buffer, newday_buffer, alexander_buffer = None, None, None, None, None, None
    swank_df, kanopy_df, criterion_df, docuseek_df, newday_df, alexander_df = None, None, None, None, None, None    
    try:
        swank_processor = SwankSearch(film_title=title)
        swank_buffer, filename = swank_processor.process()
        swank_buffer.seek(0)
    except:
        swank_buffer = None
        flash("Error processing Swank search.  Continuing with other searches.")


    try:
        kanopy_processor = SearchKanopy(film_title=title)
        kanopy_buffer, kanopy_filename = kanopy_processor.process() 
        kanopy_buffer.seek(0)

    except:
        kanopy_buffer = None
        flash("Error processing Kanopy search.  Continuing with other searches.")

    try:

        criterion_processor = SearchCriterion(film_title=title)
        criterion_buffer, criterion_filename = criterion_processor.process()
        criterion_buffer.seek(0)
    except:
        criterion_buffer = None 
        flash("Error processing Criterion search.  Continuing with other searches.")

    try:
        docuseek_processor = DocuseekScraper(film_title=title, debug=True)
        docuseek_buffer, docuseek_filename = docuseek_processor.process()
        docuseek_buffer.seek(0)

    except:
        docuseek_buffer = None
        flash("Error processing Docuseek search.  Continuing with other searches.") 

    

    try:
        newday_processor = NewDayScraper(title=title, debug=True)
        newday_buffer, newday_filename = newday_processor.process()
        newday_buffer.seek(0)       
    except: 
        newday_buffer = None    
        flash("Error processing New Day search.  Continuing with other searches.")  

    # try:
    #     ambrose_processor = AmbroseScraper(title=title, debug=True)
    #     ambrose_buffer, ambrose_filename = ambrose_processor.process()
    #     ambrose_buffer.seek(0)  
    # except:
    #     flash("Error processing Ambrose search.  Continuing with other searches.")
        
    try:
        alexander_processor = AlexanderScraper(title=title, debug=True)
        alexander_buffer, alexander_filename = alexander_processor.process()
        alexander_buffer.seek(0)
    except:
        alexander_buffer = None 
        flash("Error processing Alexander search.  Continuing with other searches.")



    if swank_buffer:
        swank_df = pd.read_excel(swank_buffer)
    if kanopy_buffer:
        kanopy_df = pd.read_excel(kanopy_buffer)
    if criterion_buffer:
            
        criterion_df = pd.read_excel(criterion_buffer)
    if docuseek_buffer:
        docuseek_df = pd.read_excel(docuseek_buffer)
    if newday_buffer:
        newday_df = pd.read_excel(newday_buffer)
    #if ambrose_buffer:
        #ambrose_df = pd.read_excel(ambrose_buffer)
    if alexander_buffer:
        alexander_df = pd.read_excel(alexander_buffer)


    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        if swank_df is not None:
            swank_df.to_excel(writer, sheet_name='Swank', index=False)
        if kanopy_df is not None:
            kanopy_df.to_excel(writer, sheet_name='Kanopy', index=False)
        if criterion_df is not None:
            criterion_df.to_excel(writer, sheet_name='Criterion', index=False)
        if docuseek_df is not None:
            docuseek_df.to_excel(writer, sheet_name='Docuseek', index=False)
        if newday_df is not None:
            newday_df.to_excel(writer, sheet_name='New Day', index=False)
        if alexander_df is not None:
            alexander_df.to_excel(writer, sheet_name='Alexander', index=False)

    excel_buffer.seek(0)

    return send_file(
    excel_buffer,
    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    as_attachment=True,
    download_name="All_Film_Search_Results.xlsx",
)    



@film_search_blueprint.route("/run_search_swank", methods=["POST"])
def run_search_swank():
    """Run Swank search and return Excel."""
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Please enter a film title.")
        return redirect(url_for("film_search.index"))

    
    try:
        swank_processor = SwankSearch(film_title=title)
        swank_buffer, filename = swank_processor.process()
        swank_buffer.seek(0)
    except:
        flash("Error processing Swank search.  Continuing with other searches.")


    return send_file(
        swank_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )

@film_search_blueprint.route("/kanopy_search", methods=["POST"])    
def run_kanopy_search():    
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Please enter a film title.")
        return redirect(url_for("film_search.index"))

    processor = SearchKanopy(film_title=title)
    excel_buffer, filename = processor.process()
    excel_buffer.seek(0)

    return send_file(
        excel_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )       
@film_search_blueprint.route("/criterion_search", methods=["POST"])
def run_criterion_search():
    """Run Criterion search and return its own Excel."""
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Please enter a film title.")
        return redirect(url_for("film_search.index"))

    processor = SearchCriterion(film_title=title)
    excel_buffer, filename = processor.process()
    excel_buffer.seek(0)

    return send_file(
        excel_buffer,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


# @film_search_blueprint.route("/kanopy_search", methods=["POST"])
# def run_kanopy_search():
#     """Run Kanopy search and return Excel."""
#     title = (request.form.get("title") or "").strip()
#     if not title:
#         flash("Please enter a film title.")
#         return redirect(url_for("film_search.index"))

#     processor = SearchKanopy(film_title=title)
#     excel_buffer, filename = processor.process()
#     excel_buffer.seek(0)

#     return send_file(
#         excel_buffer,
#         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#         as_attachment=True,
#         download_name=filename,
#     )
# # app/film_search/routes.py




@film_search_blueprint.route("/run_docuseek_search", methods=["POST"])
def run_docuseek_search():
    title = request.form.get("title")

    if not title:
        return {"error": "Docuseek requires a title"}, 400

    scraper = DocuseekScraper(film_title=title, debug=True)
    excel_buffer, filename = scraper.process()

    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )



@film_search_blueprint.route("/run_newday_search", methods=["POST"])
def run_newday_search():
    title = request.form.get("title")

    if not title:
        return {"error": "Title required"}, 400

    scraper = NewDayScraper(title=title, debug=True)
    excel_buffer, filename = scraper.process()

    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

from app.film_search.scrapers.ambrose_scraper import AmbroseScraper


@film_search_blueprint.route("/run_ambrose_search", methods=["POST"])
def run_ambrose_search():
    title = request.form.get("title")

    if not title:
        return {"error": "Title required"}, 400

    scraper = AmbroseScraper(title=title, debug=True)
    excel_buffer, filename = scraper.process()

    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

@film_search_blueprint.route("/run_alexander_search", methods=["POST"])
def run_alexander_search():
    title = request.form.get("title")

    if not title:
        return {"error": "Title required"}, 400

    scraper = AlexanderScraper(title=title, debug=True)
    excel_buffer, filename = scraper.process()

    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    
