from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, seed_db


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-key"

    seed_db()

    def get_current_user():
        user_id = session.get("user_id")
        if not user_id:
            return None

        conn = get_db()
        try:
            user = conn.execute(
                "SELECT id, name, email FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return dict(user) if user else None
        finally:
            conn.close()

    @app.route("/")
    def landing():
        return render_template("landing.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not name or not email or not password:
                return render_template("register.html", error="Please fill in all fields."), 400

            if len(password) < 8:
                return render_template("register.html", error="Password must be at least 8 characters long."), 400

            conn = get_db()
            try:
                existing = conn.execute(
                    "SELECT id FROM users WHERE email = ?",
                    (email,),
                ).fetchone()
                if existing:
                    return render_template("register.html", error="An account with that email already exists."), 409

                conn.execute(
                    "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
                conn.commit()
                user = conn.execute(
                    "SELECT id FROM users WHERE email = ?",
                    (email,),
                ).fetchone()
                session["user_id"] = user["id"]
            finally:
                conn.close()

            return redirect(url_for("profile"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            conn = get_db()
            try:
                user = conn.execute(
                    "SELECT id, name, email, password FROM users WHERE email = ?",
                    (email,),
                ).fetchone()
            finally:
                conn.close()

            if not user or not check_password_hash(user["password"], password):
                return render_template("login.html", error="Invalid email or password."), 401

            session["user_id"] = user["id"]
            return redirect(url_for("profile"))

        return render_template("login.html")

    @app.route("/logout", methods=["GET", "POST"])
    def logout():
        session.clear()
        return redirect(url_for("landing"))

    @app.route("/profile")
    def profile():
        user = get_current_user()
        if user is None:
            return redirect(url_for("login"))

        conn = get_db()
        try:
            total_spend = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE user_id = ?",
                (user["id"],),
            ).fetchone()["total"]
            recent_expenses = conn.execute(
                """
                SELECT id, title, category, amount, description, expense_date
                FROM expenses
                WHERE user_id = ?
                ORDER BY expense_date DESC, id DESC
                LIMIT 5
                """,
                (user["id"],),
            ).fetchall()
        finally:
            conn.close()

        return render_template("profile.html", user=user, total_spend=total_spend, recent_expenses=recent_expenses)

    @app.route("/expenses/add", methods=["GET", "POST"])
    def add_expense():
        user = get_current_user()
        if user is None:
            return redirect(url_for("login"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            category = request.form.get("category", "").strip()
            amount = request.form.get("amount", "").strip()
            description = request.form.get("description", "").strip()
            expense_date = request.form.get("expense_date") or datetime.utcnow().date().isoformat()

            if not title or not category or not amount:
                return render_template(
                    "expense_form.html",
                    user=user,
                    expense=None,
                    mode="Add",
                    error="Title, category, and amount are required.",
                ), 400

            try:
                amount_value = float(amount)
            except ValueError:
                return render_template(
                    "expense_form.html",
                    user=user,
                    expense=None,
                    mode="Add",
                    error="Amount must be a valid number.",
                ), 400

            if amount_value <= 0:
                return render_template(
                    "expense_form.html",
                    user=user,
                    expense=None,
                    mode="Add",
                    error="Amount must be greater than zero.",
                ), 400

            conn = get_db()
            try:
                conn.execute(
                    """
                    INSERT INTO expenses (user_id, title, category, amount, description, expense_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user["id"], title, category, amount_value, description, expense_date),
                )
                conn.commit()
            finally:
                conn.close()

            return redirect(url_for("profile"))

        return render_template("expense_form.html", user=user, expense=None, mode="Add")

    @app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
    def edit_expense(id):
        user = get_current_user()
        if user is None:
            return redirect(url_for("login"))

        conn = get_db()
        try:
            expense = conn.execute(
                "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
                (id, user["id"]),
            ).fetchone()
        finally:
            conn.close()

        if expense is None:
            return redirect(url_for("profile"))

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            category = request.form.get("category", "").strip()
            amount = request.form.get("amount", "").strip()
            description = request.form.get("description", "").strip()
            expense_date = request.form.get("expense_date") or expense["expense_date"]

            if not title or not category or not amount:
                return render_template(
                    "expense_form.html",
                    user=user,
                    expense=dict(expense),
                    mode="Edit",
                    error="Title, category, and amount are required.",
                ), 400

            try:
                amount_value = float(amount)
            except ValueError:
                return render_template(
                    "expense_form.html",
                    user=user,
                    expense=dict(expense),
                    mode="Edit",
                    error="Amount must be a valid number.",
                ), 400

            if amount_value <= 0:
                return render_template(
                    "expense_form.html",
                    user=user,
                    expense=dict(expense),
                    mode="Edit",
                    error="Amount must be greater than zero.",
                ), 400

            conn = get_db()
            try:
                conn.execute(
                    """
                    UPDATE expenses
                    SET title = ?, category = ?, amount = ?, description = ?, expense_date = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (title, category, amount_value, description, expense_date, id, user["id"]),
                )
                conn.commit()
            finally:
                conn.close()

            return redirect(url_for("profile"))

        return render_template("expense_form.html", user=user, expense=dict(expense), mode="Edit")

    @app.route("/expenses/<int:id>/delete", methods=["GET", "POST"])
    def delete_expense(id):
        user = get_current_user()
        if user is None:
            return redirect(url_for("login"))

        conn = get_db()
        try:
            expense = conn.execute(
                "SELECT id FROM expenses WHERE id = ? AND user_id = ?",
                (id, user["id"]),
            ).fetchone()
            if expense:
                conn.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (id, user["id"]))
                conn.commit()
        finally:
            conn.close()

        return redirect(url_for("profile"))

    return app


app = create_app()


if __name__ == "__main__":
    seed_db()
    app.run(debug=True, port=5001)
