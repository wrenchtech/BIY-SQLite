from flask import Flask
from config import Config

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # registrar rutas
    from .routes.clientes import clientes_bp
    app.register_blueprint(clientes_bp)

    return app
