from flask import Blueprint, render_template

clientes_bp = Blueprint(
    "clientes",
    __name__,
    template_folder="../templates"
)

@clientes_bp.route("/")
def home():
    return render_template("index.html")
