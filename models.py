from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_approved = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return self.username

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kapan_number = db.Column(db.String(100), unique=True, nullable=False)
    total_quantity = db.Column(db.Integer, nullable=False)
    available_quantity = db.Column(db.Integer, nullable=False)
    created_date = db.Column(db.Date, default=date.today)
    is_active = db.Column(db.Boolean, default=True)
    assignments = db.relationship( "AssetAssignment", back_populates="asset", cascade="all, delete-orphan")
    history = db.relationship( "AssetHistory", back_populates="asset", cascade="all, delete-orphan")

    def __repr__(self):
        return self.kapan_number
    
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer,db.ForeignKey("user.id"),unique=True,nullable=False)
    admin_name = db.Column(db.String(100), nullable=False)
    admin_code = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True)
    phone_number = db.Column(db.String(15))
    user = db.relationship( "User",backref="admin",uselist=False)

    def __repr__(self):
        return self.admin_name
    
class Manager(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column( db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    manager_name = db.Column(db.String(100), nullable=False)
    manager_code = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True)
    phone_number = db.Column(db.String(15))
    user = db.relationship( "User", backref="manager", uselist=False)
    employees = db.relationship( "Employee", back_populates="manager", cascade="all, delete-orphan")
    daily_works = db.relationship( "DailyWork", back_populates="manager", cascade="all, delete-orphan")
    
    def __repr__(self):
        return self.manager_name
    
class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column( db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    manager_id = db.Column( db.Integer, db.ForeignKey("manager.id"), nullable=False)
    employee_name = db.Column(db.String(100), nullable=True)
    employee_code = db.Column(db.String(50), unique=True, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=True)
    phone_number = db.Column(db.String(15), nullable=True)
    # is_approved = db.Column(db.Boolean, default=False)
    user = db.relationship( "User", backref="employee", uselist=False)
    manager = db.relationship( "Manager", back_populates="employees")
    daily_works = db.relationship( "DailyWork", back_populates="employee", cascade="all, delete-orphan")

    def __repr__(self):
        return self.employee_name

class AssetAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    manager_id = db.Column(db.Integer, db.ForeignKey("manager.id"))
    assigned_quantity = db.Column(db.Integer, nullable=False)
    returned_quantity = db.Column(db.Integer, default=0)
    assign_date = db.Column(db.Date, default=date.today)
    return_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="Assigned")
    current_holder = db.Column(db.Boolean, default=True)
    asset = db.relationship( "Asset", back_populates="assignments")
    manager = db.relationship( "Manager", backref="asset_assignments")

    def __repr__(self):
        return f"{self.asset.kapan_number} -> {self.manager.manager_name}"

class AssetHistory(db.Model):
    __tablename__ = "asset_history"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    from_manager_id = db.Column(db.Integer, db.ForeignKey("manager.id"))
    to_manager_id = db.Column(db.Integer, db.ForeignKey("manager.id"))
    quantity = db.Column(db.Integer, nullable=False)
    action = db.Column(db.String(20), nullable=False)
    action_date = db.Column(db.Date, default=date.today)
    reason = db.Column(db.String(255))
    action_by = db.Column(db.String(100))
    asset = db.relationship("Asset",back_populates="history")
    from_manager = db.relationship("Manager", foreign_keys=[from_manager_id])
    to_manager = db.relationship("Manager", foreign_keys=[to_manager_id])
    
    
class DailyWork(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column( db.Integer, db.ForeignKey("employee.id"), nullable=False)
    manager_id = db.Column( db.Integer, db.ForeignKey("manager.id"), nullable=False)
    work_date = db.Column( db.Date, nullable=False)
    quantity = db.Column( db.Integer, nullable=False)
    created_at = db.Column( db.DateTime, default=datetime.now)
    employee = db.relationship( "Employee", back_populates="daily_works")
    manager = db.relationship( "Manager", back_populates="daily_works")
    
    def __repr__(self):
        return f"{self.employee.employee_name} - {self.work_date}"
    
class SalaryRequest(db.Model):

    id = db.Column( db.Integer, primary_key=True)
    employee_id = db.Column( db.Integer, db.ForeignKey("employee.id"), nullable=False)
    manager_id = db.Column( db.Integer, db.ForeignKey("manager.id"), nullable=False)
    request_type = db.Column( db.String(20), nullable=False)
    amount = db.Column( db.Numeric(10, 2), nullable=False)
    reason = db.Column( db.Text, nullable=False)
    status = db.Column( db.String(20), nullable=False, default="Pending")
    manager_reason = db.Column( db.Text, nullable=True)
    request_date = db.Column( db.Date, default=date.today, nullable=False)
    response_date = db.Column( db.Date, nullable=True)
    employee = db.relationship( "Employee", backref="salary_requests")
    manager = db.relationship( "Manager", backref="salary_requests")

    def __repr__(self):
        return f"{self.request_type} - {self.amount}"