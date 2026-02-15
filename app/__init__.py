import sqlite3
from pathlib import Path

from flask import Flask, g, session
from config import Config


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            Config.DATABASE,
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    Path("instance").mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(Config.DATABASE)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'cliente',
            estado TEXT NOT NULL DEFAULT 'pendiente',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS dietas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            contenido TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS entrenamientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            contenido TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS medidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            peso REAL,
            altura REAL,
            cintura REAL,
            grasa REAL,
            fuente TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS progresos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nota TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()
    db.close()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.teardown_appcontext(close_db)

    init_db()

    # registrar rutas
    from .routes.clientes import clientes_bp
    app.register_blueprint(clientes_bp)

    app.get_db = get_db

    @app.before_request
    def load_logged_user():
        user_id = session.get("user_id")
        if user_id is None:
            g.user = None
            return

        db = get_db()
        g.user = db.execute(
            "SELECT id, nombre, email, role, estado FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    with app.app_context():
        db = get_db()
        admin_exists = db.execute(
            "SELECT id FROM users WHERE email = ?",
            ("admin@biy.local",),
        ).fetchone()
        if not admin_exists:
            from werkzeug.security import generate_password_hash

            db.execute(
                """
                INSERT INTO users (nombre, email, password_hash, role, estado)
                VALUES (?, ?, ?, 'admin', 'activo')
                """,
                ("Administrador", "admin@biy.local", generate_password_hash("admin123")),
            )
            db.commit()

    return app
