from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_mail import Mail, Message
import random
from dotenv import load_dotenv
import os
from sqlalchemy import or_, extract, func
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Asset, Admin, Manager, Employee, AssetAssignment, AssetHistory, DailyWork, SalaryRequest
from datetime import datetime, date, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DB_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")

mail = Mail(app)
db.init_app(app)

with app.app_context():
    db.create_all()

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/", methods=["GET", "POST"])
def home():
    return render_template("landing.html")

# Home (Login/Register Page)
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        try:
            username = request.form["username"].strip()
            password = request.form["password"]
            role = request.form["role"]

            existing_user = User.query.filter_by(
                username=username
            ).first()

            if username == "" or password == "":
                flash("Please enter username and password.", "warning")
                return redirect(url_for("register"))

            if existing_user:
                flash("Username already exists.", "warning")
                return redirect(url_for("register"))

            if len(password) < 8:
                flash("Password must be at least 8 characters.", "danger")
                return redirect(url_for("register"))
            
            if role == "admin":
                is_approved = True
                if User.query.filter_by(role="admin").first():
                    flash("An admin account already exists. Only one admin is allowed.", "danger")
                    return redirect(url_for("register"))
            else:
                is_approved = False

            new_user = User(
                username=username,
                password=generate_password_hash(password),
                role=role,
                is_approved=is_approved)

            db.session.add(new_user)
            db.session.flush()

            # Employee registration
            if role == "employee":
                manager_id = request.form.get("manager_id")
                if not manager_id:
                    flash("Please select your manager.", "warning")
                    db.session.rollback()
                    return redirect(url_for("register"))

                employee = Employee(
                    user_id=new_user.id,
                    manager_id=int(manager_id))
                db.session.add(employee)

                flash(
                    "Registration successful. Wait for manager approval.",
                    "success")

            elif role == "manager":
                flash(
                    "Registration successful. Wait for admin approval.",
                    "success")

            elif role == "admin":
                flash(
                    "Registration successful. Wait for admin approval.",
                    "success")
            db.session.commit()

            return redirect(url_for("login"))

        except Exception as e:
            db.session.rollback()
            print("Register Error:", e)
            flash(
                "Something went wrong while registering.",
                "danger")
            return redirect(url_for("register"))

    # GET Request
    # GET Request
    managers = Manager.query.join(User).filter(
        User.role == "manager",
        User.is_approved == True
    ).all()

    admin_exists = User.query.filter_by(role="admin").first() is not None

    return render_template(
        "register.html",
        managers=managers,
        admin_exists=admin_exists)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        try:
            username = request.form["username"].strip()
            password = request.form["password"]

            user = User.query.filter_by(
                username=username
            ).first()

            if user and check_password_hash(user.password, password):
                if user.role == "admin":
                    pass
                elif not user.is_approved:
                    if user.role == "employee":
                        flash(
                            "Your account is waiting for manager approval.",
                            "warning"
                        )
                    elif user.role == "manager":
                        flash(
                            "Your account is waiting for admin approval.",
                            "warning"
                        )
                    return redirect(url_for("login"))

                session["username"] = user.username
                session["role"] = user.role

                if user.role == "admin":
                    return redirect(url_for("admin_dashboard"))

                elif user.role == "manager":
                    return redirect(url_for("manager_dashboard"))

                elif user.role == "employee":
                    # employee = Employee.query.filter_by(
                    #     user_id=user.id
                    # ).first()

                    # # First Login → Complete Profile
                    # if (
                    #     not employee.employee_name or
                    #     not employee.employee_code or
                    #     not employee.email or
                    #     not employee.phone_number):
                    #     return redirect(url_for("complete_profile"))
                    return redirect(url_for("employee_dashboard"))
            flash("Invalid username or password.", "danger")

        except Exception as e:
            print("Login Error:", e)
            flash(
                "Something went wrong while logging in.",
                "danger")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":

        try:
            email = request.form["email"].strip()
            manager = Manager.query.filter_by(email=email).first()

            if not manager:
                flash("Email not found.", "danger")
                return redirect(url_for("forgot_password"))

            user = User.query.get(manager.user_id)

            if not user:
                flash("User account not found.", "danger")
                return redirect(url_for("forgot_password"))

            otp = str(random.randint(100000, 999999))

            session["reset_otp"] = otp
            session["reset_user_id"] = user.id
            session["otp_expiry"] = (
                datetime.now() + timedelta(minutes=5)
            ).strftime("%Y-%m-%d %H:%M:%S")

            msg = Message(
                "Password Reset OTP",
                sender=app.config["MAIL_USERNAME"],
                recipients=[email])

            msg.body = f"""
                Hello {manager.manager_name},

                Your OTP for password reset is:

                {otp}

                This OTP is valid for 5 minutes.

                If you did not request this, please ignore this email.

                Sonal Impex ATS
                """

            mail.send(msg)
            flash("OTP sent to your registered email.", "success")
            return redirect(url_for("verify_otp"))

        except Exception as e:
            print("Forgot Password Error:", e)
            flash("Unable to send OTP. Please try again later.", "danger")
            return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")

@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":

        try:
            entered_otp = request.form["otp"].strip()

            if "reset_otp" not in session:
                flash("OTP session expired.", "danger")
                return redirect(url_for("forgot_password"))

            expiry = datetime.strptime(
                session["otp_expiry"],
                "%Y-%m-%d %H:%M:%S")

            if datetime.now() > expiry:
                session.clear()
                flash("OTP expired. Please request a new OTP.", "danger")
                return redirect(url_for("forgot_password"))

            if entered_otp == session["reset_otp"]:
                session["otp_verified"] = True
                flash("OTP verified successfully.", "success")
                return redirect(url_for("reset_password"))

            flash("Invalid OTP.", "danger")

        except Exception as e:
            print("Verify OTP Error:", e)
            flash("Something went wrong while verifying OTP. Please try again.", "danger")
            return redirect(url_for("forgot_password"))

    return render_template("verify_otp.html")

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if "otp_verified" not in session:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":

        try:
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]

            if password != confirm_password:
                flash("Passwords do not match.", "danger")
                return redirect(url_for("reset_password"))

            if len(password) < 8:
                flash("Password must be at least 8 characters.", "danger")
                return redirect(url_for("reset_password"))

            user = User.query.get(session["reset_user_id"])

            if not user:
                flash("User not found.", "danger")
                return redirect(url_for("forgot_password"))

            user.password = generate_password_hash(password)

            db.session.commit()

            session.pop("reset_otp", None)
            session.pop("reset_user_id", None)
            session.pop("otp_verified", None)
            session.pop("otp_expiry", None)

            flash("Password changed successfully.", "success")

            return redirect(url_for("login"))

        except Exception as e:
            db.session.rollback()
            print("Reset Password Error:", e)
            flash("Something went wrong while resetting your password. Please try again.", "danger")
            return redirect(url_for("reset_password"))

    return render_template("reset_password.html")
    
@app.route("/admin")
def admin_dashboard():
    if "username" not in session:
        return redirect(url_for("login"))

    if session.get("role", "").lower() != "admin":
        return redirect(url_for("login"))

    try:
        recent_assignments = AssetAssignment.query.order_by(
            AssetAssignment.id.desc()
        ).limit(5).all()

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        admin = Admin.query.filter_by(
            user_id=user.id
        ).first()

        if not admin:
            return redirect(url_for("complete_profile"))

        return render_template(
            "admin_dashboard.html",
            recent_assignments=recent_assignments
        )

    except Exception as e:
        print("Admin Dashboard Error:", e)
        flash(
            "Unable to load dashboard. Please try again.",
            "danger"
        )
        return redirect(url_for("login"))
    
@app.route("/admin_profile")
def admin_profile():
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        manager = Manager.query.filter_by(
            user_id=user.id).first()

        return render_template(
            "admin_profile.html",
            user=user,
            manager=manager)

    except Exception as e:
        print("Admin Profile Error:", e)
        flash("Unable to load profile. Please try again.", "danger")
        return redirect(url_for("admin_dashboard"))
    
@app.route("/user")
def manager_dashboard():

    if "username" not in session:
        return redirect(url_for("login"))

    try:

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if not manager:
            flash("Please complete your profile first.", "warning")
            return redirect(url_for("complete_profile"))

        return render_template(
            "manager_dashboard.html",
            manager=manager
        )

    except Exception as e:

        print("User Dashboard Error:", e)

        flash("Unable to load dashboard.", "danger")

        return redirect(url_for("login"))
    
@app.route("/pending_managers")
def pending_managers():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        users = User.query.filter_by(
            role="manager",
            is_approved=False
        ).all()

        return render_template(
            "pending_managers.html",
            users=users)

    except Exception as e:
        print("Pending Users Error:", e)
        flash("Unable to load pending users. Please try again.", "danger")
        return redirect(url_for("admin_dashboard"))
    
@app.route("/approve_user/<int:id>")
def approve_user(id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        user = User.query.get_or_404(id)
        user.is_approved = True
        db.session.commit()
        flash("User approved successfully.", "success")

        return redirect(url_for("pending_managers"))

    except Exception as e:
        db.session.rollback()
        print("Approve User Error:", e)
        flash("Unable to approve user. Please try again.", "danger")
        return redirect(url_for("pending_managers"))
    
@app.route("/delete_user/<int:id>")
def delete_user(id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        user = User.query.get_or_404(id)

        db.session.delete(user)
        db.session.commit()
        flash("User rejected successfully.", "success")

        return redirect(url_for("pending_managers"))

    except Exception as e:
        db.session.rollback()
        print("Delete User Error:", e)
        flash("Unable to reject user. Please try again.", "danger")
        return redirect(url_for("pending_managers"))
    
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/add_asset", methods=["GET", "POST"])
def add_asset():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        try:
            kapan_number = request.form["kapan_number"].strip().upper()
            total_quantity = int(request.form["total_quantity"])

            if total_quantity <= 0:
                flash("Quantity must be greater than 0.", "danger")
                return redirect(url_for("add_asset"))

            existing_asset = Asset.query.filter_by(
                kapan_number=kapan_number
            ).first()

            if existing_asset:
                flash("Kapan Number already exists.", "warning")
                return redirect(url_for("add_asset"))

            asset = Asset(
                kapan_number=kapan_number,
                total_quantity=total_quantity,
                available_quantity=total_quantity,)

            db.session.add(asset)
            db.session.commit()

            flash("Kapan added successfully.", "success")
            return redirect(url_for("view_assets"))

        except ValueError:
            flash("Please enter a valid quantity.", "danger")
            return redirect(url_for("add_asset"))

        except Exception as e:
            db.session.rollback()
            print("Add Asset Error:", e)
            flash("Unable to add Kapan. Please try again.", "danger")
            return redirect(url_for("add_asset"))

    return render_template("add_asset.html")

@app.route("/view_assets")
def view_assets():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        search = request.args.get("search", "").strip()
        query = Asset.query.filter_by(is_active=True)

        if search:
            query = query.filter(
                Asset.kapan_number.ilike(f"%{search}%"))

        page = request.args.get("page", 1, type=int)

        assets = query.order_by(Asset.id.desc()).paginate(
            page=page,
            per_page=10,
            error_out=False)

        return render_template(
            "view_assets.html",
            assets=assets)

    except Exception as e:
        print("View Assets Error:", e)
        flash("Unable to load Kapan list. Please try again.", "danger")
        return redirect(url_for("admin_dashboard"))
    
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_asset(id):
    if "username" not in session:
        return redirect(url_for("login"))
    
    try:
        asset = Asset.query.get_or_404(id)

        if request.method == "POST":

            kapan_number = request.form["kapan_number"].strip().upper()
            total_quantity = int(request.form["total_quantity"])

            assigned_quantity = asset.total_quantity - asset.available_quantity

            if total_quantity < assigned_quantity:
                flash(
                    f"Total Quantity cannot be less than Assigned Quantity ({assigned_quantity}).",
                    "danger")
                return redirect(url_for("edit_asset", id=id))

            asset.kapan_number = kapan_number
            asset.total_quantity = total_quantity
            asset.available_quantity = total_quantity - assigned_quantity

            db.session.commit()

            flash("Kapan updated successfully.", "success")
            return redirect(url_for("view_assets"))

        return render_template("edit_asset.html", asset=asset)

    except ValueError:
        flash("Please enter a valid quantity.", "danger")
        return redirect(url_for("edit_asset", id=id))

    except Exception as e:
        db.session.rollback()
        print("Edit Asset Error:", e)
        flash("Unable to update Kapan. Please try again.", "danger")
        return redirect(url_for("view_assets"))
    
@app.route("/deactivate/<int:id>")
def deactivate_asset(id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        asset = Asset.query.get_or_404(id)
        asset.is_active = False
        db.session.commit()
        flash("Asset deactivated successfully.", "success")
        return redirect(url_for("view_assets"))

    except Exception as e:
        db.session.rollback()
        print("Deactivate Asset Error:", e)
        flash("Unable to deactivate asset. Please try again.", "danger")
        return redirect(url_for("view_assets"))

@app.route("/inactive_assets")
def inactive_assets():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        page = request.args.get("page", 1, type=int)

        assets = Asset.query.filter_by(
            is_active=False
        ).paginate(
            page=page,
            per_page=10,
            error_out=False)

        return render_template(
            "inactive_assets.html",
            assets=assets)

    except Exception as e:
        print("Inactive Assets Error:", e)
        flash("Unable to load inactive assets. Please try again.", "danger")
        return redirect(url_for("admin_dashboard"))
    
@app.route("/reactivate/<int:id>")
def reactivate_asset(id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        asset = Asset.query.get_or_404(id)
        asset.is_active = True
        db.session.commit()
        flash("Asset reactivated successfully.", "success")
        return redirect(url_for("inactive_assets"))

    except Exception as e:
        db.session.rollback()
        print("Reactivate Asset Error:", e)
        flash("Unable to reactivate asset. Please try again.", "danger")
        return redirect(url_for("inactive_assets"))
    
@app.route("/manage_manager")
def manage_manager():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        return render_template("manage_manager.html")

    except Exception as e:
        print("Manage Manager Error:", e)
        flash("Unable to load the page. Please try again.", "danger")
        return redirect(url_for("admin_dashboard"))
    
@app.route("/add_manager", methods=["GET", "POST"])
def add_manager():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    if request.method == "POST":

        try:
            username = request.form["username"].strip()
            password = request.form["password"]

            if username == "" or password == "":
                flash("Username and Password are required.", "warning")
                return redirect(url_for("add_manager"))

            if len(password) < 8:
                flash("Password must be at least 8 characters.", "danger")
                return redirect(url_for("add_manager"))

            if User.query.filter_by(username=username).first():
                flash("Username already exists.", "warning")
                return redirect(url_for("add_manager"))

            user = User(
                username=username,
                password=generate_password_hash(password),
                role="manager",
                is_approved=True)

            db.session.add(user)
            db.session.commit()

            flash("Manager added successfully.", "success")
            return redirect(url_for("view_managers"))

        except Exception as e:
            db.session.rollback()
            print("Add Manager Error:", e)
            flash("Unable to add manager. Please try again.", "danger")
            return redirect(url_for("add_manager"))

    return render_template("add_manager.html")

@app.route("/view_managers")
def view_managers():
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        page = request.args.get("page", 1, type=int)
        search = request.args.get("search", "").strip()

        query = Manager.query.join(User).filter(
            User.role != "admin")

        if search:
            query = query.filter(
                or_(
                    Manager.manager_name.ilike(f"%{search}%"),
                    Manager.manager_code.ilike(f"%{search}%"),
                    Manager.email.ilike(f"%{search}%"),
                    Manager.phone_number.ilike(f"%{search}%")
                ))
        managers = query.order_by(Manager.id.desc()).paginate(
            page=page,
            per_page=10,
            error_out=False)
        
        return render_template(
            "view_managers.html",
            managers=managers,
            search=search,)

    except Exception as e:
        print("View Managers Error:", e)
        flash("Unable to load manager list. Please try again.", "danger")
        return redirect(url_for("admin_dashboard"))
    
@app.route("/edit_manager/<int:id>", methods=["GET", "POST"])
def edit_manager(id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        manager = Manager.query.get_or_404(id)

        if request.method == "POST":
            manager.manager_name = request.form["manager_name"].strip()
            manager.manager_code = request.form["manager_code"].strip()
            manager.email = request.form["email"].strip()

            db.session.commit()
            flash("Manager data updated successfully.", "success")
            return redirect(url_for("view_managers"))

        return render_template(
            "edit_manager.html",
            manager=manager)

    except Exception as e:
        db.session.rollback()
        print("Edit Manager Error:", e)
        flash("Unable to update manager details. Please try again.", "danger")
        return redirect(url_for("view_managers"))
    
@app.route("/delete_manager/<int:id>")
def delete_manager(id):
    if "role" not in session or session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        manager = Manager.query.get_or_404(id)

        db.session.delete(manager)
        db.session.commit()

        flash("Manager deleted successfully.", "success")

    except Exception as e:
        db.session.rollback()
        print("Delete Manager Error:", e)
        error = str(e).lower()

        if "foreign key" in error or "constraint" in error:
            flash(
                "Manager cannot be deleted because related assignment or history records exist.",
                "danger")
        else:
            flash(
                "Unable to delete manager. Please try again.",
                "danger")

    return redirect(url_for("view_managers"))

@app.route("/assign_asset", methods=["GET", "POST"])
def assign_asset():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        assets = Asset.query.filter(
            Asset.is_active == True,
            Asset.available_quantity > 0
        ).all()

        managers = Manager.query.all()

        if request.method == "POST":

            asset_id = int(request.form["asset_id"])
            manager_id = int(request.form["manager_id"])
            assigned_quantity = int(request.form["assigned_quantity"])

            assign_date = datetime.strptime(
                request.form["assign_date"],
                "%Y-%m-%d"
            ).date()

            asset = Asset.query.get_or_404(asset_id)
            manager = Manager.query.get(manager_id)

            if not manager:
                flash("Selected manager not found.", "danger")
                return redirect(url_for("assign_asset"))
            
            if assigned_quantity <= 0:
                flash("Quantity must be greater than 0.", "danger")
                return redirect(url_for("assign_asset"))

            if assigned_quantity > asset.available_quantity:
                flash(
                    f"Only {asset.available_quantity} quantity is available.",
                    "danger")
                return redirect(url_for("assign_asset"))

            assignment = AssetAssignment(
                asset_id=asset_id,
                manager_id=manager_id,
                assigned_quantity=assigned_quantity,
                returned_quantity=0,
                assign_date=assign_date,
                status="Assigned",
                current_holder=True)

            history = AssetHistory(
                asset_id=asset_id,
                from_manager_id=None,
                to_manager_id=manager_id,
                quantity=assigned_quantity,
                action="Assigned",
                action_date=assign_date,
                reason="Assigned by Admin",
                action_by=session["username"])

            asset.available_quantity -= assigned_quantity

            db.session.add(assignment)
            db.session.add(history)

            db.session.commit()
            flash("Kapan assigned successfully.", "success")
            return redirect(url_for("assignment_history"))

        return render_template(
            "assign_asset.html",
            assets=assets,
            managers=managers)

    except ValueError:
        flash("Please enter valid data.", "danger")
        return redirect(url_for("assign_asset"))

    except Exception as e:
        db.session.rollback()
        print("Assign Asset Error:", e)
        flash("Unable to assign Kapan. Please try again.", "danger")
        return redirect(url_for("assign_asset"))

@app.route("/assignment_history")
def assignment_history():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        search = request.args.get("search", "").strip()
        status = request.args.get("status", "")
        from_date = request.args.get("from_date", "")
        to_date = request.args.get("to_date", "")

        query = AssetAssignment.query.join(Asset).join(Manager)

        if search:
            query = query.filter(
                (Asset.kapan_number.ilike(f"%{search}%")) |
                (Manager.manager_name.ilike(f"%{search}%")) |
                (Manager.manager_code.ilike(f"%{search}%")))

        if status:
            query = query.filter(
                AssetAssignment.status == status)

        if from_date:
            from_date = datetime.strptime(
                from_date,
                "%Y-%m-%d"
            ).date()
            query = query.filter(
                AssetAssignment.assign_date >= from_date)

        if to_date:
            to_date = datetime.strptime(
                to_date,
                "%Y-%m-%d"
            ).date()
            query = query.filter(
                AssetAssignment.assign_date <= to_date)

        if from_date and to_date and from_date > to_date:
            flash(
                "To Date must be greater than From Date.",
                "danger")
            return redirect(url_for("assignment_history"))

        page = request.args.get("page", 1, type=int)

        assignments = query.order_by(
            AssetAssignment.id.desc()
        ).paginate(
            page=page,
            per_page=10,
            error_out=False)

        return render_template(
            "assignment_history.html",
            assignments=assignments)

    except ValueError:
        flash(
            "Please enter a valid date.",
            "danger")
        return redirect(url_for("assignment_history"))

    except Exception as e:
        print("Assignment History Error:", e)
        flash(
            "Unable to load assignment history. Please try again.",
            "danger")

        return redirect(url_for("admin_dashboard"))
    
@app.route("/export_excel")
def export_excel():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        search = request.args.get("search", "")
        status = request.args.get("status", "")
        from_date = request.args.get("from_date", "")
        to_date = request.args.get("to_date", "")

        query = AssetAssignment.query.join(Asset).join(Manager)

        if search:
            query = query.filter(
                (Asset.kapan_number.ilike(f"%{search}%")) |
                (Manager.manager_name.ilike(f"%{search}%")) |
                (Manager.manager_code.ilike(f"%{search}%")))

        if status:
            query = query.filter(AssetAssignment.status == status)

        if from_date:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
            query = query.filter(
                AssetAssignment.assign_date >= from_date)

        if to_date:
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
            query = query.filter(
                AssetAssignment.assign_date <= to_date)

        assignments = query.order_by(
            AssetAssignment.assign_date.desc()
        ).all()

        wb = Workbook()
        ws = wb.active
        ws.title = "Assignment History"

        headers = [
            "S.No",
            "Kapan Number",
            "Manager Name",
            "Assigned Qty",
            "Returned Qty",
            "Remaining Qty",
            "Assign Date",
            "Return Date",
            "Status"
        ]

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col)
            cell.value = header
            cell.font = Font(bold=True)

        row = 2
        for i, assignment in enumerate(assignments, start=1):
            ws.cell(row=row, column=1).value = i
            ws.cell(row=row, column=2).value = assignment.asset.kapan_number
            ws.cell(row=row, column=3).value = assignment.manager.manager_name
            ws.cell(row=row, column=4).value = assignment.assigned_quantity
            ws.cell(row=row, column=5).value = assignment.returned_quantity
            ws.cell(row=row, column=6).value = (
                assignment.assigned_quantity -
                assignment.returned_quantity)
            ws.cell(row=row, column=7).value = str(assignment.assign_date)
            ws.cell(row=row, column=8).value = (
                str(assignment.return_date)
                if assignment.return_date else "-")
            ws.cell(row=row, column=9).value = assignment.status

            row += 1

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return send_file(
            output,
            download_name="Assignment_History.xlsx",
            as_attachment=True,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except ValueError: 
        flash("Invalid date format.", "danger")
        return redirect(url_for("assignment_history"))

    except Exception as e:  
        print("Export Excel Error:", e)
        flash(
            "Unable to export Excel file. Please try again.",
            "danger")
        return redirect(url_for("assignment_history"))
        
@app.route("/export_pdf")
def export_pdf():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        search = request.args.get("search", "")
        status = request.args.get("status", "")
        from_date = request.args.get("from_date", "")
        to_date = request.args.get("to_date", "")

        query = AssetAssignment.query.join(Asset).join(Manager)

        if search:
            query = query.filter(
                (Asset.kapan_number.ilike(f"%{search}%")) |
                (Manager.manager_name.ilike(f"%{search}%")) |
                (Manager.manager_code.ilike(f"%{search}%")))

        if status:
            query = query.filter(
                AssetAssignment.status == status)

        if from_date:
            from_date = datetime.strptime(
                from_date,
                "%Y-%m-%d"
            ).date()
            query = query.filter(
                AssetAssignment.assign_date >= from_date)

        if to_date:
            to_date = datetime.strptime(
                to_date,
                "%Y-%m-%d"
            ).date()
            query = query.filter(
                AssetAssignment.assign_date <= to_date)

        assignments = query.order_by(
            AssetAssignment.assign_date.desc()
        ).all()

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer)
        elements = []
        style = getSampleStyleSheet()["Heading1"]
        style.alignment = TA_CENTER

        elements.append(
            Paragraph(
                "Diamond Kapan Tracking System",
                style))

        elements.append(
            Paragraph(
                "Assignment History Report",
                style))

        data = [[
            "S.No",
            "Kapan No",
            "Manager",
            "Assigned",
            "Returned",
            "Remaining",
            "Assign Date",
            "Return Date",
            "Status"
        ]]

        for i, assignment in enumerate(assignments, start=1):
            data.append([
                i,
                assignment.asset.kapan_number,
                assignment.manager.manager_name,
                assignment.assigned_quantity,
                assignment.returned_quantity,
                assignment.assigned_quantity -
                assignment.returned_quantity,
                str(assignment.assign_date),
                str(assignment.return_date)
                if assignment.return_date else "-",
                assignment.status
            ])

        table = Table(data)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ]))

        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name="Assignment_History.pdf",
            mimetype="application/pdf")

    except ValueError:
        flash("Invalid date format.", "danger")
        return redirect(url_for("assignment_history"))

    except Exception as e:
        print("Export PDF Error:", e)
        flash(
            "Unable to export PDF file. Please try again.",
            "danger")
        return redirect(url_for("assignment_history"))
    
@app.route("/current_holdings")
def current_holdings():
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        search = request.args.get("search", "").strip()

        query = AssetAssignment.query.join(Asset).join(Manager).filter(
            AssetAssignment.assigned_quantity >
            AssetAssignment.returned_quantity)

        if search:
            query = query.filter(
                (Asset.kapan_number.ilike(f"%{search}%")) |
                (Manager.manager_name.ilike(f"%{search}%")) |
                (Manager.manager_code.ilike(f"%{search}%")))

        page = request.args.get("page", 1, type=int)

        holdings = query.order_by(
            AssetAssignment.id.desc()
        ).paginate(
            page=page,
            per_page=10,
            error_out=False)

        return render_template(
            "current_holdings.html",
            holdings=holdings,
            search=search)

    except Exception as e:
        print("Current Holdings Error:", e)
        flash(
            "Unable to load current holdings. Please try again.",
            "danger")
        return redirect(url_for("admin_dashboard"))
        
@app.route("/transfer_history")
def transfer_history():
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "admin":
        return redirect(url_for("login"))

    try:
        search = request.args.get("search", "").strip()
        from_date = request.args.get("from_date", "")
        to_date = request.args.get("to_date", "")

        query = AssetHistory.query.filter_by(
            action="Transferred"
        ).join(Asset)

        if search:
            query = query.filter(
                Asset.kapan_number.ilike(f"%{search}%"))

        if from_date:
            from_date = datetime.strptime(
                from_date,
                "%Y-%m-%d"
            ).date()
            query = query.filter(
                AssetHistory.action_date >= from_date)

        if to_date:
            to_date = datetime.strptime(
                to_date,
                "%Y-%m-%d"
            ).date()
            query = query.filter(
                AssetHistory.action_date <= to_date)

        if from_date and to_date and from_date > to_date:
            flash(
                "To Date must be greater than or equal to From Date.",
                "danger")
            return redirect(url_for("transfer_history"))

        page = request.args.get("page", 1, type=int)

        transfers = query.order_by(
            AssetHistory.id.desc()
        ).paginate(
            page=page,
            per_page=10,
            error_out=False)

        return render_template(
            "transfer_history.html",
            transfers=transfers)

    except ValueError:
        flash(
            "Please enter a valid date.",
            "danger")
        return redirect(url_for("transfer_history"))

    except Exception as e:
        print("Transfer History Error:", e)
        flash(
            "Unable to load transfer history. Please try again.",
            "danger")
        return redirect(url_for("admin_dashboard"))
    
@app.route("/admin_managers")
def admin_managers():

    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "admin":
        return redirect(url_for("login"))

    try:

        managers = Manager.query.order_by(
            Manager.manager_name.asc()
        ).all()

        return render_template(
            "admin_managers.html",
            managers=managers
        )

    except Exception as e:

        print("Admin Managers Error:", e)

        flash(
            "Unable to load managers.",
            "danger"
        )

        return redirect(
            url_for("admin_dashboard")
        )
        
@app.route("/admin_manager_employees/<int:manager_id>")
def admin_manager_employees(manager_id):

    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "admin":
        return redirect(url_for("login"))

    try:

        manager = Manager.query.get_or_404(manager_id)

        employees = Employee.query.join(
            User,
            Employee.user_id == User.id
        ).filter(
            Employee.manager_id == manager.id,
            User.role == "employee"
        ).order_by(
            Employee.employee_name.asc()
        ).all()

        return render_template(
            "admin_manager_employees.html",
            manager=manager,
            employees=employees
        )

    except Exception as e:

        print("Admin Manager Employees Error:", e)

        flash(
            "Unable to load employees.",
            "danger"
        )

        return redirect(
            url_for("admin_managers")
        )

# ------------------------------manager page creation---------------------------------

@app.route("/my_assets")
def my_assets():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if not manager:
            flash(
                "Please complete your profile first.",
                "warning")
            return redirect(url_for("complete_profile"))

        assignments = AssetAssignment.query.join(Asset).filter(
            AssetAssignment.manager_id == manager.id,
            AssetAssignment.assigned_quantity > AssetAssignment.returned_quantity,
            Asset.is_active == True
        ).order_by(
            AssetAssignment.id.desc()
        ).all()

        return render_template(
            "my_assets.html",
            assignments=assignments,
            manager=manager)

    except Exception as e:
        print("My Assets Error:", e)
        flash(
            "Unable to load your assets. Please try again.",
            "danger")
        return redirect(url_for("manager_dashboard"))

@app.route("/complete_profile", methods=["GET", "POST"])
def complete_profile():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        # =========================
        # EMPLOYEE PROFILE
        # =========================
        if user.role.lower() == "employee":

            employee = Employee.query.filter_by(
                user_id=user.id
            ).first()

            if not employee:
                flash("Employee not found.", "danger")
                return redirect(url_for("login"))

            if (
                employee.employee_name and
                employee.employee_code and
                employee.email and
                employee.phone_number
            ):
                flash("Profile already completed.", "warning")
                return redirect(url_for("employee_dashboard"))

            if request.method == "POST":

                employee_name = request.form["employee_name"].strip()
                employee_code = request.form["employee_code"].strip().upper()
                email = request.form["email"].strip()
                phone_number = request.form["phone_number"].strip()

                if Employee.query.filter(
                    Employee.employee_code == employee_code,
                    Employee.id != employee.id
                ).first():

                    flash("Employee Code already exists.", "danger")
                    return redirect(url_for("complete_profile"))

                if Employee.query.filter(
                    Employee.email == email,
                    Employee.id != employee.id
                ).first():

                    flash("Email already exists.", "danger")
                    return redirect(url_for("complete_profile"))

                if not phone_number.isdigit() or len(phone_number) != 10:

                    flash(
                        "Phone number must be exactly 10 digits.",
                        "danger"
                    )

                    return redirect(url_for("complete_profile"))

                employee.employee_name = employee_name
                employee.employee_code = employee_code
                employee.email = email
                employee.phone_number = phone_number

                db.session.commit()

                flash(
                    "Employee profile completed successfully.",
                    "success"
                )

                return redirect(
                    url_for("employee_dashboard")
                )

            return render_template(
                "complete_profile.html",
                role="employee"
            )

        # =========================
        # MANAGER PROFILE
        # =========================
        elif user.role.lower() == "manager":

            manager = Manager.query.filter_by(
                user_id=user.id
            ).first()

            if manager:
                flash(
                    "Profile already completed.",
                    "warning"
                )

                return redirect(
                    url_for("manager_dashboard")
                )

            if request.method == "POST":

                manager_name = request.form["manager_name"].strip()
                manager_code = request.form["manager_code"].strip().upper()
                email = request.form["email"].strip()
                phone_number = request.form["phone_number"].strip()

                if Manager.query.filter_by(
                    manager_code=manager_code
                ).first():

                    flash(
                        "Manager Code already exists.",
                        "danger"
                    )

                    return redirect(
                        url_for("complete_profile")
                    )

                if Manager.query.filter_by(
                    email=email
                ).first():

                    flash(
                        "Email already exists.",
                        "danger"
                    )

                    return redirect(
                        url_for("complete_profile")
                    )

                if not phone_number.isdigit() or len(phone_number) != 10:

                    flash(
                        "Phone number must be exactly 10 digits.",
                        "danger"
                    )

                    return redirect(
                        url_for("complete_profile")
                    )

                manager = Manager(
                    user_id=user.id,
                    manager_name=manager_name,
                    manager_code=manager_code,
                    email=email,
                    phone_number=phone_number
                )

                db.session.add(manager)
                db.session.commit()

                flash(
                    "Manager profile completed successfully.",
                    "success"
                )

                return redirect(
                    url_for("manager_dashboard")
                )

            return render_template(
                "complete_profile.html",
                role="manager"
            )

        # =========================
        # ADMIN PROFILE
        # =========================
        elif user.role.lower() == "admin":

            admin = Admin.query.filter_by(
                user_id=user.id
            ).first()

            if admin:
                flash(
                    "Profile already completed.",
                    "warning"
                )

                return redirect(
                    url_for("admin_dashboard")
                )

            if request.method == "POST":

                admin_name = request.form["admin_name"].strip()
                admin_code = request.form["admin_code"].strip().upper()
                email = request.form["email"].strip()
                phone_number = request.form["phone_number"].strip()

                if Admin.query.filter_by(
                    admin_code=admin_code
                ).first():

                    flash(
                        "Admin Code already exists.",
                        "danger"
                    )

                    return redirect(
                        url_for("complete_profile")
                    )

                if Admin.query.filter_by(
                    email=email
                ).first():

                    flash(
                        "Email already exists.",
                        "danger"
                    )

                    return redirect(
                        url_for("complete_profile")
                    )

                if not phone_number.isdigit() or len(phone_number) != 10:

                    flash(
                        "Phone number must be exactly 10 digits.",
                        "danger"
                    )

                    return redirect(
                        url_for("complete_profile")
                    )

                admin = Admin(
                    user_id=user.id,
                    admin_name=admin_name,
                    admin_code=admin_code,
                    email=email,
                    phone_number=phone_number
                )

                db.session.add(admin)
                db.session.commit()

                flash(
                    "Admin profile completed successfully.",
                    "success"
                )

                return redirect(
                    url_for("admin_dashboard")
                )

            return render_template(
                "complete_profile.html",
                role="admin"
            )

        # =========================
        # INVALID ROLE
        # =========================
        else:

            flash(
                "Invalid user role.",
                "danger"
            )

            return redirect(
                url_for("login")
            )

    except Exception as e:

        db.session.rollback()

        print(
            "Complete Profile Error:",
            e
        )

        flash(
            "Unable to complete profile. Please try again.",
            "danger"
        )

        if session.get("role") == "employee":
            return redirect(
                url_for("employee_dashboard")
            )

        elif session.get("role") == "manager":
            return redirect(
                url_for("manager_dashboard")
            )

        elif session.get("role") == "admin":
            return redirect(
                url_for("admin_dashboard")
            )

        return redirect(
            url_for("login")
        )
        
    
@app.route("/transfer_asset/<int:id>", methods=["GET", "POST"])
def transfer_asset(id):
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if not manager:
            flash("Please complete your profile first.", "warning")
            return redirect(url_for("complete_profile"))

        assignment = AssetAssignment.query.get_or_404(id)

        if assignment.manager_id != manager.id:
            flash(
                "You cannot transfer another user's quantity.",
                "danger" )
            return redirect(url_for("my_assets"))

        remaining_qty = (
            assignment.assigned_quantity -
            assignment.returned_quantity)

        if remaining_qty <= 0:
            flash(
                "No quantity available for transfer.",
                "warning")
            return redirect(url_for("my_assets"))

        managers = (
            Manager.query
            .join(User, Manager.user_id == User.id)
            .filter(
                Manager.id != manager.id,
                User.role == "manager")
            .all())

        if request.method == "POST":
            new_manager_id = int(request.form["manager_id"])
            transfer_qty = int(request.form["quantity"])
            reason = request.form["reason"].strip()

            if transfer_qty <= 0:
                flash(
                    "Quantity must be greater than zero.",
                    "danger")
                return redirect(url_for("transfer_asset", id=id))

            if transfer_qty > remaining_qty:
                flash(
                    f"Only {remaining_qty} quantity is available.",
                    "danger")
                return redirect(url_for("transfer_asset", id=id))

            if new_manager_id == manager.id:
                flash(
                    "You cannot transfer quantity to yourself.",
                    "danger")
                return redirect(url_for("transfer_asset", id=id))

            new_manager = Manager.query.get(new_manager_id)

            if not new_manager:
                flash(
                    "Selected manager not found.",
                    "danger")
                return redirect(url_for("transfer_asset", id=id))

            assignment.returned_quantity += transfer_qty

            if assignment.assigned_quantity == assignment.returned_quantity:
                assignment.current_holder = False
                assignment.status = "Transferred"
                assignment.return_date = date.today()

            new_assignment = AssetAssignment(
                asset_id=assignment.asset_id,
                manager_id=new_manager_id,
                assigned_quantity=transfer_qty,
                returned_quantity=0,
                assign_date=date.today(),
                status="Assigned",
                current_holder=True)

            db.session.add(new_assignment)

            history = AssetHistory(
                asset_id=assignment.asset_id,
                from_manager_id=manager.id,
                to_manager_id=new_manager_id,
                quantity=transfer_qty,
                action="Transferred",
                action_date=date.today(),
                reason=reason,
                action_by=session["username"])

            db.session.add(history)
            db.session.commit()

            flash(
                "Quantity transferred successfully.",
                "success")
            return redirect(url_for("my_assets"))

        return render_template(
            "transfer_asset.html",
            assignment=assignment,
            remaining_qty=remaining_qty,
            managers=managers)

    except ValueError:
        flash(
            "Please enter a valid quantity.",
            "danger")
        return redirect(url_for("transfer_asset", id=id))

    except Exception as e:
        db.session.rollback()
        print("Transfer Asset Error:", e)

        flash(
            "Unable to transfer quantity. Please try again.",
            "danger")

        return redirect(url_for("my_assets"))
    
@app.route("/return_to_admin/<int:assignment_id>", methods=["GET", "POST"])
def return_to_admin(assignment_id):
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        assignment = AssetAssignment.query.get_or_404(assignment_id)

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if not manager:
            flash("Please complete your profile first.", "warning")
            return redirect(url_for("complete_profile"))

        if assignment.manager_id != manager.id:
            flash(
                "You cannot return another user's quantity.",
                "danger")
            return redirect(url_for("my_assets"))

        remaining_qty = (
            assignment.assigned_quantity -
            assignment.returned_quantity)

        if remaining_qty <= 0:
            flash(
                "No quantity available to return.",
                "warning")
            return redirect(url_for("my_assets"))

        if request.method == "POST":
            return_qty = int(request.form["quantity"])

            if return_qty <= 0:
                flash(
                    "Quantity must be greater than zero.",
                    "danger")
                return redirect(
                    url_for(
                        "return_to_admin",
                        assignment_id=assignment.id) )

            if return_qty > remaining_qty:
                flash(
                    f"Only {remaining_qty} quantity available.",
                    "danger")
                return redirect(
                    url_for(
                        "return_to_admin",
                        assignment_id=assignment.id))

            assignment.returned_quantity += return_qty

            if assignment.returned_quantity == assignment.assigned_quantity:
                assignment.current_holder = False
                assignment.status = "Returned"
                assignment.return_date = date.today()

            asset = Asset.query.get(assignment.asset_id)

            if not asset:
                flash("Asset not found.", "danger")
                return redirect(url_for("my_assets"))

            asset.available_quantity += return_qty

            history = AssetHistory(
                asset_id=assignment.asset_id,
                from_manager_id=manager.id,
                to_manager_id=None,
                quantity=return_qty,
                action="Returned",
                action_date=date.today(),
                reason="Returned To Admin",
                action_by=session["username"])

            db.session.add(history)
            db.session.commit()

            flash(
                "Quantity returned successfully.",
                "success")
            return redirect(url_for("my_assets"))

        return render_template(
            "return_to_admin.html",
            assignment=assignment,
            remaining_qty=remaining_qty)

    except ValueError:
        flash(
            "Please enter a valid quantity.",
            "danger")
        return redirect(
            url_for(
                "return_to_admin",
                assignment_id=assignment_id))

    except Exception as e:
        db.session.rollback()
        print("Return To Admin Error:", e)
        flash(
            "Unable to return quantity. Please try again.",
            "danger")
        return redirect(url_for("my_assets"))
    
@app.route("/my_history")
def my_history():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if not manager:
            flash(
                "Please complete your profile first.",
                "warning"
            )
            return redirect(url_for("complete_profile"))

        page = request.args.get("page", 1, type=int)
        search = request.args.get("search", "", type=str).strip()

        history_query = AssetHistory.query.filter(
            (AssetHistory.from_manager_id == manager.id) |
            (AssetHistory.to_manager_id == manager.id)
        )

        if search:
            search_text = f"%{search}%"

            history_query = history_query.filter(
                or_(
                    AssetHistory.reason.ilike(search_text),

                    AssetHistory.asset.has(
                        Asset.kapan_number.ilike(search_text)
                    ),

                    AssetHistory.from_manager.has(
                        Manager.manager_name.ilike(search_text)
                    ),

                    AssetHistory.to_manager.has(
                        Manager.manager_name.ilike(search_text)
                    )
                )
            )

        history = history_query.order_by(
            AssetHistory.id.desc()
        ).paginate(
            page=page,
            per_page=10,
            error_out=False
        )

        return render_template(
            "my_history.html",
            history=history,
            search=search
        )

    except Exception as e:
        print("My History Error:", e)
        flash(
            "Unable to load your history. Please try again.",
            "danger"
        )
        return redirect(url_for("manager_dashboard"))
        
@app.route("/my_profile")
def my_profile():

    if "username" not in session:
        return redirect(url_for("login"))

    try:

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        # Admin / Manager
        if user.role.lower() in ["admin", "manager"]:

            manager = Manager.query.filter_by(
                user_id=user.id
            ).first()

            if not manager:
                flash(
                    "Please complete your profile first.",
                    "warning"
                )
                return redirect(url_for("complete_profile"))

            return render_template(
                "my_profile.html",
                user=user,
                profile=manager,
                role="manager"
            )

        # Employee
        elif user.role.lower() == "employee":

            employee = Employee.query.filter_by(
                user_id=user.id
            ).first()

            if not employee:
                flash(
                    "Please complete your profile first.",
                    "warning"
                )
                return redirect(url_for("complete_employee_profile"))

            manager = Manager.query.get(employee.manager_id)

            return render_template(
                "my_profile.html",
                user=user,
                profile=employee,
                manager=manager,
                role="employee"
            )

    except Exception as e:

        print("My Profile Error:", e)

        flash(
            "Unable to load your profile.",
            "danger"
        )

        if session["role"] == "employee":
            return redirect(url_for("employee_dashboard"))

        return redirect(url_for("manager_dashboard"))
        
@app.route("/update_profile", methods=["GET", "POST"])
def update_profile():

    if "username" not in session:
        return redirect(url_for("login"))

    try:

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        # ==========================================
        # Employee
        # ==========================================

        if user.role.lower() == "employee":

            employee = Employee.query.filter_by(
                user_id=user.id
            ).first()

            if not employee:
                flash(
                    "Please complete your profile first.",
                    "warning"
                )
                return redirect(url_for("complete_profile"))

            if request.method == "POST":

                employee.employee_name = request.form["employee_name"].strip()

                email = request.form["email"].strip()
                phone = request.form["phone_number"].strip()

                existing_email = Employee.query.filter(
                    Employee.email == email,
                    Employee.id != employee.id
                ).first()

                if existing_email:
                    flash(
                        "Email already exists.",
                        "danger"
                    )
                    return redirect(url_for("update_profile"))

                if not phone.isdigit() or len(phone) != 10:
                    flash(
                        "Phone number must be exactly 10 digits.",
                        "danger"
                    )
                    return redirect(url_for("update_profile"))

                employee.email = email
                employee.phone_number = phone

                db.session.commit()

                flash(
                    "Profile updated successfully.",
                    "success"
                )

                return redirect(url_for("my_profile"))

            return render_template(
                "update_profile.html",
                profile=employee,
                user=user,
                role="employee",
                manager=db.session.get(Manager, employee.manager_id)
            )

        # ==========================================
        # Admin / Manager
        # ==========================================

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if not manager:
            flash(
                "Please complete your profile first.",
                "warning"
            )
            return redirect(url_for("complete_profile"))

        if request.method == "POST":

            manager.manager_name = request.form["manager_name"].strip()

            email = request.form["email"].strip()
            phone = request.form["phone_number"].strip()

            existing_email = Manager.query.filter(
                Manager.email == email,
                Manager.id != manager.id
            ).first()

            if existing_email:
                flash(
                    "Email already exists.",
                    "danger"
                )
                return redirect(url_for("update_profile"))

            if not phone.isdigit() or len(phone) != 10:
                flash(
                    "Phone number must be exactly 10 digits.",
                    "danger"
                )
                return redirect(url_for("update_profile"))

            manager.email = email
            manager.phone_number = phone

            db.session.commit()

            flash(
                "Profile updated successfully.",
                "success"
            )

            if user.role.lower() == "admin":
                return redirect(url_for("admin_profile"))

            else:
                return redirect(url_for("my_profile"))

        return render_template(
            "update_profile.html",
            profile=manager,
            user=user,
            role="manager"
        )

    except Exception as e:

        db.session.rollback()

        print("Update Profile Error:", e)

        flash(
            "Unable to update profile.",
            "danger"
        )

        return redirect(url_for("my_profile"))
    
@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        if request.method == "POST":
            current_password = request.form["current_password"]
            new_password = request.form["new_password"]
            confirm_password = request.form["confirm_password"]

            if not check_password_hash(
                user.password,
                current_password):
                flash(
                    "Current password is incorrect.",
                    "danger")
                return redirect(url_for("change_password"))

            if new_password != confirm_password:
                flash(
                    "New password and Confirm password do not match.",
                    "danger")
                return redirect(url_for("change_password"))

            if check_password_hash(
                user.password,
                new_password):
                flash(
                    "New password cannot be the same as the current password.",
                    "warning")
                return redirect(url_for("change_password"))

            if len(new_password) < 8:
                flash(
                    "Password must be at least 8 characters long.",
                    "danger")
                return redirect(url_for("change_password"))
            user.password = generate_password_hash(new_password)
            db.session.commit()

            flash(
                "Password changed successfully.",
                "success")

            if user.role.lower() == "admin":
                return redirect(url_for("admin_profile"))
            else:
                return redirect(url_for("manager_dashboard"))

        return render_template("change_password.html")

    except Exception as e:
        db.session.rollback()
        print("Change Password Error:", e)
        flash(
            "Unable to change password. Please try again.",
            "danger")
        return redirect(url_for("change_password"))

@app.route("/employee_management")
def employee_management():

    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        return render_template("employee_management.html")

    except Exception as e:

        print("Employee Management Error:", e)

        flash(
            "Unable to load Employee Management page.",
            "danger"
        )

        return redirect(url_for("manager_dashboard"))
    
@app.route("/pending_employees")
def pending_employees():
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()
        page = request.args.get("page", 1, type=int)

        pending = Employee.query.join(User).filter(
            Employee.manager_id == manager.id,
            User.is_approved == False
        ).paginate(
            page=page,
            per_page=10,
            error_out=False)

        return render_template(
            "pending_employees.html",
            employees=pending)

    except Exception as e:
        print("Pending Employee Error :", e)
        flash(
            "Unable to load pending employees.",
            "danger")
        return redirect(url_for("employee_management"))
    
@app.route("/approve_employee/<int:id>")
def approve_employee(id):
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        login_user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=login_user.id
        ).first()

        employee = Employee.query.filter_by(
            id=id,
            manager_id=manager.id
        ).first_or_404()

        user = User.query.get(employee.user_id)
        user.is_approved = True

        db.session.commit()

        flash(
            "Employee approved successfully.",
            "success")

    except Exception as e:
        db.session.rollback()
        print("Approve Error :", e)
        flash(
            "Unable to approve employee.",
            "danger")
    return redirect(url_for("pending_employees"))

@app.route("/reject_employee/<int:id>")
def reject_employee(id):
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        login_user = User.query.filter_by(
            username=session["username"]
        ).first()
        manager = Manager.query.filter_by(
            user_id=login_user.id
        ).first()
        employee = Employee.query.filter_by(
            id=id,
            manager_id=manager.id
        ).first_or_404()
        user = User.query.get(employee.user_id)

        db.session.delete(employee)
        db.session.delete(user)
        db.session.commit()
        flash(
            "Employee rejected successfully.",
            "success")

    except Exception as e:
        db.session.rollback()
        print("Reject Error :", e)
        flash(
            "Unable to reject employee.",
            "danger")
    return redirect(url_for("pending_employees"))

@app.route("/add_employee", methods=["GET", "POST"])
def add_employee():
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if not manager:
            flash("Manager profile not found.", "danger")
            return redirect(url_for("manager_dashboard"))

        if request.method == "POST":
            username = request.form["username"].strip()
            password = request.form["password"]

            if username == "" or password == "":
                flash("Username and Password are required.", "warning")
                return redirect(url_for("add_employee"))

            if len(password) < 8:
                flash("Password must be at least 8 characters.", "warning")
                return redirect(url_for("add_employee"))

            if User.query.filter_by(username=username).first():
                flash("Username already exists.", "warning")
                return redirect(url_for("add_employee"))

            new_user = User(
                username=username,
                password=generate_password_hash(password),
                role="employee",
                is_approved=False)

            db.session.add(new_user)
            db.session.flush()

            employee = Employee(
                user_id=new_user.id,
                manager_id=manager.id)
            db.session.add(employee)
            db.session.commit()
            flash(
                "Employee account created successfully. Employee can now login and complete the profile.",
                "success")
            return redirect(url_for("view_employees"))
        return render_template("add_employee.html")

    except Exception as e:
        db.session.rollback()
        print("Add Employee Error:", e)
        flash(
            "Unable to add employee.",
            "danger")
        return redirect(url_for("employee_management"))    
    
@app.route("/view_employees")
def view_employees():
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        page = request.args.get("page", 1, type=int)
        search = request.args.get("search", "").strip()
        query = Employee.query.filter_by(
            manager_id=manager.id)

        if search:
            query = query.filter(
                or_(
                    Employee.employee_name.ilike(f"%{search}%"),
                    Employee.employee_code.ilike(f"%{search}%"),
                    Employee.email.ilike(f"%{search}%"),
                    Employee.phone_number.ilike(f"%{search}%") ))

        employees = query.order_by(
            Employee.id.desc()
        ).paginate(
            page=page,
            per_page=10,
            error_out=False )

        return render_template(
            "view_employees.html",
            employees=employees,
            search=search)

    except Exception as e:
        db.session.rollback()
        print("View Employee Error:", e)
        flash(
            "Unable to load employees.",
            "danger")
        return redirect(url_for("employee_management"))
    
@app.route("/edit_employee/<int:id>", methods=["GET", "POST"])
def edit_employee(id):
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        employee = Employee.query.filter_by(
            id=id,
            manager_id=manager.id
        ).first_or_404()

        if request.method == "POST":
            employee_name = request.form["employee_name"].strip()
            employee_code = request.form["employee_code"].strip().upper()
            email = request.form["email"].strip()
            phone_number = request.form["phone_number"].strip()

            existing_code = Employee.query.filter(
                Employee.employee_code == employee_code,
                Employee.id != employee.id
            ).first()

            if existing_code:
                flash("Employee Code already exists.", "warning")
                return redirect(url_for("edit_employee", id=id))

            existing_email = Employee.query.filter(
                Employee.email == email,
                Employee.id != employee.id
            ).first()

            if existing_email:
                flash("Email already exists.", "warning")
                return redirect(url_for("edit_employee", id=id))

            employee.employee_name = employee_name
            employee.employee_code = employee_code
            employee.email = email
            employee.phone_number = phone_number

            db.session.commit()
            flash("Employee updated successfully.", "success")
            return redirect(url_for("view_employees"))

        return render_template(
            "edit_employee.html",
            employee=employee )

    except Exception as e:
        db.session.rollback()
        print("Edit Employee Error :", e)
        flash("Unable to update employee.", "danger")
        return redirect(url_for("view_employees"))    
    
@app.route("/delete_employee/<int:id>")
def delete_employee(id):

    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        employee = Employee.query.filter_by(
            id=id,
            manager_id=manager.id
        ).first_or_404()

        employee_user = User.query.get(employee.user_id)

        # Delete Daily Work
        DailyWork.query.filter_by(
            employee_id=employee.id
        ).delete(synchronize_session=False)

        # Delete Employee
        db.session.delete(employee)

        # Delete User
        db.session.delete(employee_user)

        db.session.commit()

        flash(
            "Employee deleted successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print("Delete Employee Error:", e)

        flash(
            "Unable to delete employee.",
            "danger"
        )

    return redirect(url_for("view_employees"))

@app.route("/daily_work_employees")
def daily_work_employees():
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        employees = Employee.query.filter_by(
            manager_id=manager.id
        ).order_by(
            Employee.employee_name
        ).all()

        return render_template(
            "daily_work_employees.html",
            employees=employees)

    except Exception as e:
        print("Daily Work Employees Error:", e)
        flash(
            "Unable to load employees.",
            "danger")
        return redirect(url_for("employee_management"))    

@app.route("/send_daily_work/<int:employee_id>", methods=["GET", "POST"])
def send_daily_work(employee_id):
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        employee = Employee.query.filter_by(
            id=employee_id,
            manager_id=manager.id
        ).first()

        if not employee:
            flash(
                "Employee not found.",
                "danger")
            return redirect(url_for("daily_work_employees"))

        if request.method == "POST":
            work_date = request.form["work_date"]
            quantity = request.form["quantity"]

            daily_work = DailyWork(
                employee_id=employee.id,
                manager_id=manager.id,
                work_date=work_date,
                quantity=quantity)
            db.session.add(daily_work)
            db.session.commit()
            flash(
                "Daily work assigned successfully.",
                "success" )
            return redirect(url_for("daily_work_employees"))
        return render_template(
            "send_daily_work.html",
            employee=employee)

    except Exception as e:
        db.session.rollback()
        print("Send Daily Work Error :", e)
        flash(
            "Unable to assign daily work.",
            "danger")

        return redirect(url_for("daily_work_employees"))

@app.route("/manager_daily_work_history/<int:employee_id>")
def manager_daily_work_history(employee_id):
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        employee = Employee.query.filter_by(
            id=employee_id,
            manager_id=manager.id
        ).first()

        if not employee:
            flash("Employee not found.", "danger")
            return redirect(url_for("daily_work_employees"))
        month = request.args.get(
            "month",
            date.today().month,
            type=int)

        year = request.args.get(
            "year",
            date.today().year,
            type=int)

        history = DailyWork.query.filter(
            DailyWork.employee_id == employee.id,
            extract("month", DailyWork.work_date) == month,
            extract("year", DailyWork.work_date) == year
        ).order_by(
            DailyWork.work_date.desc()
        ).all()

        month_total = db.session.query(
            func.sum(DailyWork.quantity)
        ).filter(
            DailyWork.employee_id == employee.id,
            extract("month", DailyWork.work_date) == month,
            extract("year", DailyWork.work_date) == year
        ).scalar() or 0

        return render_template(
            "manager_daily_work_history.html",
            employee=employee,
            history=history,
            month=month,
            year=year,
            month_total=month_total)

    except Exception as e:
        print("Manager Daily Work History Error :", e)
        flash(
            "Unable to load history.",
            "danger")

        return redirect(url_for("daily_work_employees"))
    
@app.route("/edit_daily_work/<int:id>", methods=["GET", "POST"])
def edit_daily_work(id):
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        daily_work = DailyWork.query.get_or_404(id)
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if daily_work.manager_id != manager.id:
            flash("Unauthorized access.", "danger")
            return redirect(url_for("daily_work_employees"))

        if request.method == "POST":

            daily_work.work_date = request.form["work_date"]
            daily_work.quantity = request.form["quantity"]
            db.session.commit()
            flash(
                "Daily work updated successfully.",
                "success")

            return redirect(
                url_for(
                    "manager_daily_work_history",
                    employee_id=daily_work.employee_id))

        return render_template(
            "edit_daily_work.html",
            work=daily_work)

    except Exception as e:
        db.session.rollback()
        print("Edit Daily Work Error :", e)
        flash(
            "Unable to update daily work.",
            "danger")

        return redirect(url_for("daily_work_employees"))
    
@app.route("/delete_daily_work/<int:id>")
def delete_daily_work(id):
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:
        daily_work = DailyWork.query.get_or_404(id)
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if daily_work.manager_id != manager.id:
            flash("Unauthorized access.", "danger")
            return redirect(url_for("daily_work_employees"))
        employee_id = daily_work.employee_id

        db.session.delete(daily_work)
        db.session.commit()

        flash(
            "Daily work deleted successfully.",
            "success")

        return redirect(
            url_for(
                "manager_daily_work_history",
                employee_id=employee_id))

    except Exception as e:
        db.session.rollback()
        print("Delete Daily Work Error :", e)
        flash(
            "Unable to delete daily work.",
            "danger")

        return redirect(url_for("daily_work_employees"))
    
@app.route("/manager_salary_requests")
def manager_salary_requests():

    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if not manager:
            flash("Manager profile not found.", "danger")
            return redirect(url_for("manager_dashboard"))

        # Only this manager's employee requests
        requests = SalaryRequest.query.filter_by(
            manager_id=manager.id
        ).order_by(
            SalaryRequest.id.desc()
        ).all()

        return render_template(
            "manager_salary_requests.html",
            requests=requests
        )

    except Exception as e:

        print(
            "Manager Salary Requests Error:",
            e
        )

        flash(
            "Unable to load salary requests.",
            "danger"
        )

        return redirect(
            url_for("manager_dashboard")
        )
        
@app.route("/approve_salary_request/<int:id>")
def approve_salary_request(id):

    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if not manager:
            flash(
                "Manager profile not found.",
                "danger"
            )
            return redirect(
                url_for("manager_dashboard")
            )

        salary_request = SalaryRequest.query.filter_by(
            id=id,
            manager_id=manager.id
        ).first()

        if not salary_request:
            flash(
                "Request not found or unauthorized access.",
                "danger"
            )
            return redirect(
                url_for("manager_salary_requests")
            )

        # Only Pending request can be approved
        if salary_request.status != "Pending":
            flash(
                "This request has already been processed.",
                "warning"
            )
            return redirect(
                url_for("manager_salary_requests")
            )

        salary_request.status = "Approved"
        salary_request.manager_reason = None
        salary_request.response_date = date.today()

        db.session.commit()

        flash(
            "Request approved successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        print(
            "Approve Salary Request Error:",
            e
        )

        flash(
            "Unable to approve request.",
            "danger"
        )

    return redirect(
        url_for("manager_salary_requests")
    )
    
@app.route("/reject_salary_request/<int:id>", methods=["GET", "POST"])
def reject_salary_request(id):

    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "manager":
        return redirect(url_for("login"))

    try:

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        manager = Manager.query.filter_by(
            user_id=user.id
        ).first()

        if not manager:
            flash(
                "Manager profile not found.",
                "danger"
            )
            return redirect(
                url_for("manager_dashboard")
            )

        salary_request = SalaryRequest.query.filter_by(
            id=id,
            manager_id=manager.id
        ).first()

        if not salary_request:
            flash(
                "Request not found or unauthorized access.",
                "danger"
            )
            return redirect(
                url_for("manager_salary_requests")
            )

        if salary_request.status != "Pending":
            flash(
                "This request has already been processed.",
                "warning"
            )
            return redirect(
                url_for("manager_salary_requests")
            )

        if request.method == "POST":

            manager_reason = request.form.get(
                "manager_reason",
                ""
            ).strip()

            if not manager_reason:
                flash(
                    "Please enter rejection reason.",
                    "warning"
                )
                return render_template(
                    "reject_salary_request.html",
                    request_data=salary_request
                )

            salary_request.status = "Rejected"

            salary_request.manager_reason = manager_reason

            salary_request.response_date = date.today()

            db.session.commit()

            flash(
                "Request rejected successfully.",
                "success"
            )

            return redirect(
                url_for("manager_salary_requests")
            )

        return render_template(
            "reject_salary_request.html",
            request_data=salary_request
        )

    except Exception as e:

        db.session.rollback()

        print(
            "Reject Salary Request Error:",
            e
        )

        flash(
            "Unable to reject request.",
            "danger"
        )

        return redirect(
            url_for("manager_salary_requests")
        )
        
    
    

# ------------------------------employees page creation---------------------------------
    
@app.route("/employee_dashboard", methods=["GET", "POST"])
def employee_dashboard():
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "employee":
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        employee = Employee.query.filter_by(
            user_id=user.id
        ).first()

        if (
            not employee or
            not employee.employee_name or
            not employee.employee_code or
            not employee.email or
            not employee.phone_number):
            flash(
                "Please complete your profile first.",
                "warning")
            return redirect(url_for("complete_profile"))

        return render_template(
            "employee_dashboard.html",
            employee = Employee.query.filter_by(
                user_id=user.id
            ).first(),

            manager = db.session.get(
                Manager,
                employee.manager_id))

    except Exception as e:
        print("Employee Dashboard Error :", e)
        flash(
            "Unable to load dashboard.",
            "danger")

        return redirect(url_for("login"))

@app.route("/my_daily_work")
def my_daily_work():
    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "employee":
        return redirect(url_for("login"))

    try:
        user = User.query.filter_by(
            username=session["username"]
        ).first()

        employee = Employee.query.filter_by(
            user_id=user.id
        ).first()

        if not employee:
            flash(
                "Employee profile not found.",
                "danger")
            return redirect(url_for("employee_dashboard"))

        month = request.args.get(
            "month",
            date.today().month,
            type=int)

        year = request.args.get(
            "year",
            date.today().year,
            type=int)

        history = DailyWork.query.filter(
            DailyWork.employee_id == employee.id,
            extract("month", DailyWork.work_date) == month,
            extract("year", DailyWork.work_date) == year
        ).order_by(
            DailyWork.id.desc()
        ).all()

        month_total = db.session.query(
            func.sum(DailyWork.quantity)
        ).filter(
            DailyWork.employee_id == employee.id,
            extract("month", DailyWork.work_date) == month,
            extract("year", DailyWork.work_date) == year
        ).scalar() or 0

        return render_template(
            "my_daily_work.html",
            employee=employee,
            history=history,
            month=month,
            year=year,
            month_total=month_total)

    except Exception as e:
        print("My Daily Work Error :", e)
        flash(
            "Unable to load daily work history.",
            "danger")

        return redirect(url_for("employee_dashboard"))

@app.route("/salary_request", methods=["GET", "POST"])
def salary_request():

    if "username" not in session:
        return redirect(url_for("login"))

    if session["role"] != "employee":
        return redirect(url_for("login"))

    try:

        user = User.query.filter_by(
            username=session["username"]
        ).first()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        employee = Employee.query.filter_by(
            user_id=user.id
        ).first()

        if not employee:
            flash(
                "Employee profile not found.",
                "danger"
            )
            return redirect(url_for("employee_dashboard"))

        if request.method == "POST":

            request_type = request.form.get(
                "request_type"
            )

            amount = request.form.get(
                "amount"
            )

            reason = request.form.get("reason", "").strip()

            # Validation

            if request_type not in ["Salary", "Advance"]:
                flash(
                    "Please select a valid request type.",
                    "warning"
                )
                return redirect(
                    url_for("salary_request")
                )

            if not amount:
                flash(
                    "Please enter amount.",
                    "warning"
                )
                return redirect(
                    url_for("salary_request")
                )

            try:
                amount = float(amount)
            except ValueError:
                flash(
                    "Please enter a valid amount.",
                    "danger"
                )
                return redirect(
                    url_for("salary_request")
                )

            if amount <= 0:
                flash(
                    "Amount must be greater than 0.",
                    "warning"
                )
                return redirect(
                    url_for("salary_request")
                )

            if not reason:
                flash(
                    "Please enter reason.",
                    "warning"
                )
                return redirect(
                    url_for("salary_request")
                )

            # Employee's manager

            manager = Manager.query.get(
                employee.manager_id
            )

            if not manager:
                flash(
                    "Manager not found.",
                    "danger"
                )
                return redirect(
                    url_for("employee_dashboard")
                )

            # Create request

            new_request = SalaryRequest(
                employee_id=employee.id,
                manager_id=manager.id,
                request_type=request_type,
                amount=amount,
                reason=reason,
                status="Pending"
            )

            db.session.add(new_request)
            db.session.commit()

            flash(
                "Request sent to your manager successfully.",
                "success"
            )

            return redirect(
                url_for("salary_request")
            )

        requests = SalaryRequest.query.filter_by(
            employee_id=employee.id
        ).order_by(
            SalaryRequest.id.desc()
        ).all()

        return render_template(
            "salary_request.html",
            employee=employee,
            requests=requests
        )

    except Exception as e:

        db.session.rollback()

        print(
            "Salary Request Error:",
            e
        )

        flash(
            "Unable to process your request.",
            "danger"
        )

        return redirect(
            url_for("employee_dashboard")
        )
        
        
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)