from flask import Flask
from app.routes.basic_routes import viewer_bp
from app.routes.graph_routes import graph_bp
from app.routes.export_routes import export_bp
from app.routes.dipole_routes import dipole_bp
from app.routes.comparison_routes import comparison_bp
from app.routes.misc_routes import misc_bp
from app.routes.dipole_family_routes import dipole_family_routes

def create_app():
    app = Flask(__name__)
    
    # Registrar todos los blueprints
    app.register_blueprint(viewer_bp)
    app.register_blueprint(graph_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(dipole_bp)
    app.register_blueprint(comparison_bp)
    app.register_blueprint(misc_bp)
    app.register_blueprint(dipole_family_routes)
    return app
