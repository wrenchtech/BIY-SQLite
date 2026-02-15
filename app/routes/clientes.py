from flask import Blueprint, current_app, redirect, render_template, request, url_for

clientes_bp = Blueprint(
    "clientes",
    __name__,
    template_folder="../templates"
)


@clientes_bp.route("/")
def home():
    db = current_app.get_db()
    clientes = db.execute(
        "SELECT id, nombre, telefono, email, created_at FROM clientes ORDER BY id DESC"
    ).fetchall()
    return render_template("index.html", clientes=clientes, cliente_editar=None)


@clientes_bp.post("/clientes/crear")
def crear_cliente():
    nombre = request.form.get("nombre", "").strip()
    telefono = request.form.get("telefono", "").strip()
    email = request.form.get("email", "").strip()

    if nombre and telefono:
        db = current_app.get_db()
        db.execute(
            "INSERT INTO clientes (nombre, telefono, email) VALUES (?, ?, ?)",
            (nombre, telefono, email or None),
        )
        db.commit()

    return redirect(url_for("clientes.home"))


@clientes_bp.get("/clientes/<int:cliente_id>/editar")
def editar_cliente_form(cliente_id):
    db = current_app.get_db()
    cliente_editar = db.execute(
        "SELECT id, nombre, telefono, email, created_at FROM clientes WHERE id = ?",
        (cliente_id,),
    ).fetchone()
    clientes = db.execute(
        "SELECT id, nombre, telefono, email, created_at FROM clientes ORDER BY id DESC"
    ).fetchall()
    return render_template(
        "index.html",
        clientes=clientes,
        cliente_editar=cliente_editar,
    )


@clientes_bp.post("/clientes/<int:cliente_id>/actualizar")
def actualizar_cliente(cliente_id):
    nombre = request.form.get("nombre", "").strip()
    telefono = request.form.get("telefono", "").strip()
    email = request.form.get("email", "").strip()

    if nombre and telefono:
        db = current_app.get_db()
        db.execute(
            """
            UPDATE clientes
            SET nombre = ?, telefono = ?, email = ?
            WHERE id = ?
            """,
            (nombre, telefono, email or None, cliente_id),
        )
        db.commit()

    return redirect(url_for("clientes.home"))


@clientes_bp.post("/clientes/<int:cliente_id>/eliminar")
def eliminar_cliente(cliente_id):
    db = current_app.get_db()
    db.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
    db.commit()
    return redirect(url_for("clientes.home"))
