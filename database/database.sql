CREATE DATABASE IF NOT EXISTS asset_management;
USE asset_management;


-- 1. USER TABLE
CREATE TABLE user (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    password VARCHAR(200) NOT NULL,
    role VARCHAR(20) NOT NULL,
    is_approved TINYINT(1) DEFAULT 0
);



-- 2. ADMIN TABLE
CREATE TABLE admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    admin_name VARCHAR(100) NOT NULL,
    admin_code VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    phone_number VARCHAR(15),

    CONSTRAINT fk_admin_user
        FOREIGN KEY (user_id)
        REFERENCES user(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);



-- 3. MANAGER TABLE
CREATE TABLE manager (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    manager_name VARCHAR(100) NOT NULL,
    manager_code VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    phone_number VARCHAR(15),

    CONSTRAINT fk_manager_user
        FOREIGN KEY (user_id)
        REFERENCES user(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);



-- 4. EMPLOYEE TABLE
CREATE TABLE employee (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    manager_id INT,
    employee_name VARCHAR(100) NOT NULL,
    employee_code VARCHAR(50) NOT NULL,
    email VARCHAR(100),
    phone_number VARCHAR(15),

    CONSTRAINT fk_employee_user
        FOREIGN KEY (user_id)
        REFERENCES user(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_employee_manager
        FOREIGN KEY (manager_id)
        REFERENCES manager(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);



-- 5. ASSET TABLE
CREATE TABLE asset (
    id INT AUTO_INCREMENT PRIMARY KEY,
    kapan_number VARCHAR(100) NOT NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_date DATE,
    total_quantity INT NOT NULL DEFAULT 0,
    available_quantity INT NOT NULL DEFAULT 0
);



-- 6. ASSET ASSIGNMENT TABLE
CREATE TABLE asset_assignment (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asset_id INT NOT NULL,
    manager_id INT NOT NULL,
    assigned_quantity INT NOT NULL DEFAULT 0,
    returned_quantity INT NOT NULL DEFAULT 0,
    assign_date DATE,
    return_date DATE,
    status VARCHAR(20),
    current_holder TINYINT(1) DEFAULT 0,

    CONSTRAINT fk_assignment_asset
        FOREIGN KEY (asset_id)
        REFERENCES asset(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_assignment_manager
        FOREIGN KEY (manager_id)
        REFERENCES manager(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);



-- 7. ASSET HISTORY TABLE
CREATE TABLE asset_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    asset_id INT NOT NULL,
    from_manager_id INT,
    to_manager_id INT,
    quantity INT NOT NULL,
    action VARCHAR(20),
    action_date DATE,
    reason VARCHAR(255),
    action_by VARCHAR(100),

    CONSTRAINT fk_history_asset
        FOREIGN KEY (asset_id)
        REFERENCES asset(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_history_from_manager
        FOREIGN KEY (from_manager_id)
        REFERENCES manager(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT fk_history_to_manager
        FOREIGN KEY (to_manager_id)
        REFERENCES manager(id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);



-- 8. DAILY WORK TABLE
CREATE TABLE daily_work (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    manager_id INT NOT NULL,
    work_date DATE,
    quantity INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_dailywork_employee
        FOREIGN KEY (employee_id)
        REFERENCES employee(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_dailywork_manager
        FOREIGN KEY (manager_id)
        REFERENCES manager(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);



-- 9. SALARY REQUEST TABLE
CREATE TABLE salary_request (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    manager_id INT NOT NULL,
    request_type VARCHAR(20),
    amount DECIMAL(10,2),
    reason TEXT,
    status VARCHAR(20),
    manager_reason TEXT,
    request_date DATE,
    response_date DATE,

    CONSTRAINT fk_salary_employee
        FOREIGN KEY (employee_id)
        REFERENCES employee(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_salary_manager
        FOREIGN KEY (manager_id)
        REFERENCES manager(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);