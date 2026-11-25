import os
import sqlite3
import uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
DB_PATH = os.path.join(BASE_DIR, "employees.db")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                birth_date TEXT,
                office TEXT,
                department TEXT NOT NULL,
                city TEXT,
                position TEXT,
                phone TEXT,
                photo TEXT,
                username TEXT UNIQUE,
                password_hash TEXT
            )
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(employees)")}
        for name, definition in [
            ("username", "TEXT"),
            ("password_hash", "TEXT"),
            ("birth_date", "TEXT"),
            ("office", "TEXT"),
            ("city", "TEXT"),
            ("position", "TEXT"),
        ]:
            if name not in columns:
                db.execute(f"ALTER TABLE employees ADD COLUMN {name} {definition}")

        db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        admin_exists = db.execute("SELECT id FROM admins LIMIT 1").fetchone()
        if not admin_exists:
            db.execute(
                "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                ("admin", generate_password_hash("admin123"))
            )

@app.template_filter("ru_date")
def ru_date(value):
    if not value:
        return "—"
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return value

@app.template_filter("dept_hue")
def dept_hue(name):
    return (sum(ord(c) for c in (name or "")) * 37) % 360

@app.context_processor
def inject_globals():
    return {"today_mmdd": datetime.now().strftime("%m-%d")}

def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("У вас недостаточно прав для этого действия.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_photo(file):
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        raise ValueError("Поддерживаются PNG, JPG, JPEG, GIF и WEBP.")
    ext = secure_filename(file.filename).rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return f"uploads/{filename}"

def remove_photo(photo_path):
    if photo_path:
        path = os.path.join(BASE_DIR, "static", photo_path)
        if os.path.isfile(path):
            os.remove(path)

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db() as db:
            admin = db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
            employee = db.execute("SELECT * FROM employees WHERE username = ?", (username,)).fetchone()

        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session.update(user_id=admin["id"], username=admin["username"], role="admin")
            return redirect(url_for("dashboard"))

        if employee and employee["password_hash"] and check_password_hash(employee["password_hash"], password):
            session.clear()
            session.update(user_id=employee["id"], username=employee["username"],
                           role="employee", employee_id=employee["id"])
            return redirect(url_for("dashboard"))

        flash("Неверный логин или пароль.", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required()
def dashboard():
    with get_db() as db:
        my_rows = []
        if session["role"] == "employee":
            my_rows = db.execute(
                "SELECT * FROM employees WHERE id = ?", (session["employee_id"],)
            ).fetchall()
        all_employees = db.execute(
            "SELECT * FROM employees ORDER BY full_name COLLATE NOCASE"
        ).fetchall()

    departments = sorted({row["department"] for row in all_employees}, key=str.lower)
    counts = {}
    for row in all_employees:
        counts[row["department"]] = counts.get(row["department"], 0) + 1
    department_stats = [{"name": name, "count": counts[name]} for name in departments]

    current_employee = my_rows[0] if my_rows else None
    return render_template(
        "index.html",
        employees=all_employees,
        departments=departments,
        department_stats=department_stats,
        role=session["role"],
        username=session["username"],
        current_employee=current_employee,
    )

@app.route("/department/<path:name>")
@login_required()
def department_view(name):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM employees WHERE department = ? ORDER BY full_name COLLATE NOCASE",
            (name,),
        ).fetchall()
    if not rows:
        flash("Отдел не найден или в нём пока нет сотрудников.", "error")
        return redirect(url_for("dashboard"))
    return render_template(
        "department.html",
        department=name,
        employees=rows,
        role=session["role"],
        username=session["username"],
    )

@app.route("/employees", methods=["POST"])
@login_required("admin")
def add_employee():
    full_name  = request.form.get("full_name", "").strip()
    birth_date = request.form.get("birth_date", "").strip()
    office     = request.form.get("office", "").strip()
    department = request.form.get("department", "").strip()
    position   = request.form.get("position", "").strip()
    city       = request.form.get("city", "").strip()
    phone      = request.form.get("phone", "").strip()
    username   = request.form.get("username", "").strip()
    password   = request.form.get("password", "")

    if not all([full_name, birth_date, office, department, position,
                city, phone, username, password]):
        flash("Заполните все поля: ФИО, дата рождения, офис, отдел, должность, "
              "город, телефон, логин, пароль.", "error")
        return redirect(url_for("dashboard") + "#add-form")
    if len(password) < 8:
        flash("Пароль сотрудника должен содержать не менее 8 символов.", "error")
        return redirect(url_for("dashboard") + "#add-form")

    try:
        photo_path = save_photo(request.files.get("photo"))
        with get_db() as db:
            db.execute("""
                INSERT INTO employees
                    (full_name, birth_date, office, department, position, city,
                     phone, photo, username, password_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (full_name, birth_date, office, department, position, city,
                  phone, photo_path, username, generate_password_hash(password)))
        flash("Сотрудник и его аккаунт успешно добавлены.", "success")
    except sqlite3.IntegrityError:
        flash("Такой логин уже существует. Выберите другой.", "error")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("dashboard") + "#add-form")

@app.route("/employees/<int:employee_id>/edit", methods=["POST"])
@login_required("admin")
def edit_employee(employee_id):
    full_name  = request.form.get("full_name", "").strip()
    birth_date = request.form.get("birth_date", "").strip()
    office     = request.form.get("office", "").strip()
    department = request.form.get("department", "").strip()
    position   = request.form.get("position", "").strip()
    city       = request.form.get("city", "").strip()
    phone      = request.form.get("phone", "").strip()
    username   = request.form.get("username", "").strip()
    password   = request.form.get("password", "")

    if not all([full_name, birth_date, office, department, position,
                city, phone, username]):
        flash("Заполните ФИО, дату рождения, офис, отдел, должность, "
              "город, телефон и логин.", "error")
        return redirect(url_for("dashboard"))

    try:
        with get_db() as db:
            employee = db.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
            if not employee:
                flash("Сотрудник не найден.", "error")
                return redirect(url_for("dashboard"))
            photo_path = employee["photo"]
            new_photo = save_photo(request.files.get("photo"))
            if new_photo:
                remove_photo(photo_path)
                photo_path = new_photo
            if password and len(password) < 8:
                flash("Новый пароль должен содержать не менее 8 символов.", "error")
                return redirect(url_for("dashboard"))
            if password:
                db.execute("""UPDATE employees SET
                                full_name=?, birth_date=?, office=?, department=?,
                                position=?, city=?, phone=?, photo=?, username=?, password_hash=?
                              WHERE id=?""",
                           (full_name, birth_date, office, department, position, city,
                            phone, photo_path, username, generate_password_hash(password), employee_id))
            else:
                db.execute("""UPDATE employees SET
                                full_name=?, birth_date=?, office=?, department=?,
                                position=?, city=?, phone=?, photo=?, username=?
                              WHERE id=?""",
                           (full_name, birth_date, office, department, position, city,
                            phone, photo_path, username, employee_id))
        flash("Данные сотрудника обновлены.", "success")
    except sqlite3.IntegrityError:
        flash("Такой логин уже используется.", "error")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("dashboard"))

@app.route("/employees/<int:employee_id>/delete", methods=["POST"])
@login_required("admin")
def delete_employee(employee_id):
    with get_db() as db:
        employee = db.execute("SELECT photo FROM employees WHERE id = ?", (employee_id,)).fetchone()
        if employee:
            db.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
            remove_photo(employee["photo"])
    flash("Сотрудник удалён.", "success")
    return redirect(url_for("dashboard"))

@app.errorhandler(413)
def too_large(_error):
    flash("Файл слишком большой. Максимальный размер — 5 МБ.", "error")
    return redirect(url_for("dashboard"))

init_db()

if __name__ == "__main__":
    app.run(debug=True)