from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

clientes_bp = Blueprint(
    "clientes",
    __name__,
    template_folder="../templates"
)


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("clientes.login"))
        return view(**kwargs)

    return wrapped_view


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for("clientes.login"))
            if g.user["role"] != role:
                abort(403)
            return view(**kwargs)

        return wrapped_view

    return decorator


@clientes_bp.route("/")
def home():
    return render_template("index.html")


@clientes_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not nombre or not email or not password:
            flash("Completa todos los campos.", "error")
            return render_template("register.html")

        db = current_app.get_db()
        exists = db.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        if exists:
            flash("Ese correo ya esta registrado.", "error")
            return render_template("register.html")

        db.execute(
            """
            INSERT INTO users (nombre, email, password_hash, role, estado)
            VALUES (?, ?, ?, 'cliente', 'pendiente')
            """,
            (nombre, email, generate_password_hash(password)),
        )
        db.commit()
        flash("Usuario creado. Ahora inicia sesion.", "success")
        return redirect(url_for("clientes.login"))

    return render_template("register.html")


@clientes_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = current_app.get_db()
        user = db.execute(
            """
            SELECT id, nombre, email, password_hash, role, estado
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Credenciales invalidas.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        if user["role"] == "admin":
            return redirect(url_for("clientes.admin_panel"))
        return redirect(url_for("clientes.cliente_panel"))

    return render_template("login.html")


@clientes_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("clientes.home"))


@clientes_bp.get("/cliente/panel")
@role_required("cliente")
def cliente_panel():
    db = current_app.get_db()
    user_id = g.user["id"]
    dieta = db.execute(
        "SELECT contenido, updated_at FROM dietas WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    entrenamiento = db.execute(
        "SELECT contenido, updated_at FROM entrenamientos WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    medidas = db.execute(
        """
        SELECT peso, altura, cintura, grasa, fuente, fecha
        FROM medidas
        WHERE user_id = ?
        ORDER BY fecha DESC
        """,
        (user_id,),
    ).fetchall()
    progresos = db.execute(
        """
        SELECT nota, created_at
        FROM progresos
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    ).fetchall()
    return render_template(
        "cliente_panel.html",
        dieta=dieta,
        entrenamiento=entrenamiento,
        medidas=medidas,
        progresos=progresos,
    )


@clientes_bp.post("/cliente/pagar")
@role_required("cliente")
def cliente_pagar():
    db = current_app.get_db()
    db.execute(
        "UPDATE users SET estado = 'activo' WHERE id = ?",
        (g.user["id"],),
    )
    db.commit()
    flash("Pago registrado. Tu cuenta ahora esta activa.", "success")
    return redirect(url_for("clientes.cliente_panel"))


@clientes_bp.post("/cliente/medidas")
@role_required("cliente")
def cliente_subir_medidas():
    if g.user["estado"] != "activo":
        flash("Debes activar tu cuenta para registrar datos.", "error")
        return redirect(url_for("clientes.cliente_panel"))

    def to_float(value):
        val = (value or "").strip()
        return float(val) if val else None

    nota = request.form.get("nota", "").strip()
    if nota:
        db = current_app.get_db()
        db.execute(
            "INSERT INTO progresos (user_id, nota) VALUES (?, ?)",
            (g.user["id"], nota),
        )
        db.commit()
        flash("Progreso guardado.", "success")
        return redirect(url_for("clientes.cliente_panel"))

    db = current_app.get_db()
    db.execute(
        """
        INSERT INTO medidas (user_id, peso, altura, cintura, grasa, fuente)
        VALUES (?, ?, ?, ?, ?, 'cliente')
        """,
        (
            g.user["id"],
            to_float(request.form.get("peso")),
            to_float(request.form.get("altura")),
            to_float(request.form.get("cintura")),
            to_float(request.form.get("grasa")),
        ),
    )
    db.commit()
    flash("Medidas cargadas.", "success")
    return redirect(url_for("clientes.cliente_panel"))


@clientes_bp.get("/admin/panel")
@role_required("admin")
def admin_panel():
    db = current_app.get_db()
    clientes = db.execute(
        """
        SELECT id, nombre, email, estado, created_at
        FROM users
        WHERE role = 'cliente'
        ORDER BY created_at DESC
        """
    ).fetchall()
    return render_template("admin_panel.html", clientes=clientes)


@clientes_bp.post("/admin/clientes/crear")
@role_required("admin")
def admin_crear_cliente():
    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    estado = request.form.get("estado", "pendiente").strip().lower()
    if estado not in {"pendiente", "activo"}:
        estado = "pendiente"

    if not nombre or not email or not password:
        flash("Completa nombre, email y contrasena.", "error")
        return redirect(url_for("clientes.admin_panel"))

    db = current_app.get_db()
    exists = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if exists:
        flash("Ese correo ya existe.", "error")
        return redirect(url_for("clientes.admin_panel"))

    db.execute(
        """
        INSERT INTO users (nombre, email, password_hash, role, estado)
        VALUES (?, ?, ?, 'cliente', ?)
        """,
        (nombre, email, generate_password_hash(password), estado),
    )
    db.commit()
    flash("Cliente creado.", "success")
    return redirect(url_for("clientes.admin_panel"))


@clientes_bp.get("/admin/clientes/<int:cliente_id>")
@role_required("admin")
def admin_cliente_detalle(cliente_id):
    db = current_app.get_db()
    cliente = db.execute(
        """
        SELECT id, nombre, email, estado
        FROM users
        WHERE id = ? AND role = 'cliente'
        """,
        (cliente_id,),
    ).fetchone()
    if cliente is None:
        abort(404)

    dieta = db.execute(
        "SELECT contenido, updated_at FROM dietas WHERE user_id = ?",
        (cliente_id,),
    ).fetchone()
    entrenamiento = db.execute(
        "SELECT contenido, updated_at FROM entrenamientos WHERE user_id = ?",
        (cliente_id,),
    ).fetchone()
    medidas = db.execute(
        """
        SELECT peso, altura, cintura, grasa, fuente, fecha
        FROM medidas
        WHERE user_id = ?
        ORDER BY fecha DESC
        """,
        (cliente_id,),
    ).fetchall()
    progresos = db.execute(
        """
        SELECT nota, created_at
        FROM progresos
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (cliente_id,),
    ).fetchall()
    return render_template(
        "admin_cliente.html",
        cliente=cliente,
        dieta=dieta,
        entrenamiento=entrenamiento,
        medidas=medidas,
        progresos=progresos,
    )


@clientes_bp.post("/admin/clientes/<int:cliente_id>/actualizar")
@role_required("admin")
def admin_actualizar_cliente(cliente_id):
    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip().lower()
    estado = request.form.get("estado", "pendiente").strip().lower()
    if estado not in {"pendiente", "activo"}:
        estado = "pendiente"

    if not nombre or not email:
        flash("Nombre y email son obligatorios.", "error")
        return redirect(url_for("clientes.admin_cliente_detalle", cliente_id=cliente_id))

    db = current_app.get_db()
    cliente = db.execute(
        "SELECT id FROM users WHERE id = ? AND role = 'cliente'",
        (cliente_id,),
    ).fetchone()
    if cliente is None:
        abort(404)

    email_taken = db.execute(
        "SELECT id FROM users WHERE email = ? AND id != ?",
        (email, cliente_id),
    ).fetchone()
    if email_taken:
        flash("El email ya esta en uso por otro usuario.", "error")
        return redirect(url_for("clientes.admin_cliente_detalle", cliente_id=cliente_id))

    db.execute(
        """
        UPDATE users
        SET nombre = ?, email = ?, estado = ?
        WHERE id = ? AND role = 'cliente'
        """,
        (nombre, email, estado, cliente_id),
    )
    db.commit()
    flash("Cliente actualizado.", "success")
    return redirect(url_for("clientes.admin_cliente_detalle", cliente_id=cliente_id))


@clientes_bp.post("/admin/clientes/<int:cliente_id>/activar")
@role_required("admin")
def admin_activar_cliente(cliente_id):
    db = current_app.get_db()
    db.execute(
        "UPDATE users SET estado = 'activo' WHERE id = ? AND role = 'cliente'",
        (cliente_id,),
    )
    db.commit()
    flash("Cliente activado.", "success")
    return redirect(url_for("clientes.admin_cliente_detalle", cliente_id=cliente_id))


@clientes_bp.post("/admin/clientes/<int:cliente_id>/eliminar")
@role_required("admin")
def admin_eliminar_cliente(cliente_id):
    db = current_app.get_db()
    db.execute(
        "DELETE FROM users WHERE id = ? AND role = 'cliente'",
        (cliente_id,),
    )
    db.commit()
    flash("Cliente eliminado.", "success")
    return redirect(url_for("clientes.admin_panel"))


@clientes_bp.post("/admin/clientes/<int:cliente_id>/dieta")
@role_required("admin")
def admin_guardar_dieta(cliente_id):
    contenido = request.form.get("contenido", "").strip()
    if not contenido:
        flash("La dieta no puede estar vacia.", "error")
        return redirect(url_for("clientes.admin_cliente_detalle", cliente_id=cliente_id))

    db = current_app.get_db()
    db.execute(
        """
        INSERT INTO dietas (user_id, contenido, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            contenido = excluded.contenido,
            updated_at = CURRENT_TIMESTAMP
        """,
        (cliente_id, contenido),
    )
    db.commit()
    flash("Dieta guardada.", "success")
    return redirect(url_for("clientes.admin_cliente_detalle", cliente_id=cliente_id))


@clientes_bp.post("/admin/clientes/<int:cliente_id>/entrenamiento")
@role_required("admin")
def admin_guardar_entrenamiento(cliente_id):
    contenido = request.form.get("contenido", "").strip()
    if not contenido:
        flash("El entrenamiento no puede estar vacio.", "error")
        return redirect(url_for("clientes.admin_cliente_detalle", cliente_id=cliente_id))

    db = current_app.get_db()
    db.execute(
        """
        INSERT INTO entrenamientos (user_id, contenido, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET
            contenido = excluded.contenido,
            updated_at = CURRENT_TIMESTAMP
        """,
        (cliente_id, contenido),
    )
    db.commit()
    flash("Entrenamiento guardado.", "success")
    return redirect(url_for("clientes.admin_cliente_detalle", cliente_id=cliente_id))


@clientes_bp.post("/admin/clientes/<int:cliente_id>/medidas")
@role_required("admin")
def admin_subir_medidas(cliente_id):
    def to_float(value):
        val = (value or "").strip()
        return float(val) if val else None

    db = current_app.get_db()
    db.execute(
        """
        INSERT INTO medidas (user_id, peso, altura, cintura, grasa, fuente)
        VALUES (?, ?, ?, ?, ?, 'admin')
        """,
        (
            cliente_id,
            to_float(request.form.get("peso")),
            to_float(request.form.get("altura")),
            to_float(request.form.get("cintura")),
            to_float(request.form.get("grasa")),
        ),
    )
    db.commit()
    flash("Medidas del cliente guardadas.", "success")
    return redirect(url_for("clientes.admin_cliente_detalle", cliente_id=cliente_id))


@clientes_bp.post("/admin/clientes/<int:cliente_id>/progreso")
@role_required("admin")
def admin_guardar_progreso(cliente_id):
    nota = request.form.get("nota", "").strip()
    if nota:
        db = current_app.get_db()
        db.execute(
            "INSERT INTO progresos (user_id, nota) VALUES (?, ?)",
            (cliente_id, nota),
        )
        db.commit()
        flash("Progreso registrado.", "success")
    return redirect(url_for("clientes.admin_cliente_detalle", cliente_id=cliente_id))
