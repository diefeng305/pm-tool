# main.py
import os
import time
import shutil
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from database import get_db_connection, hash_password

app = FastAPI(title="模块化项目管理系统 核心引擎", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "upload"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/upload", StaticFiles(directory=UPLOAD_DIR), name="upload")

IMAGE_UPLOAD_DIR = "upload/images"
os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)

def ensure_column_exists(cursor, table, column, col_definition):
    try:
        cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
        if not cursor.fetchone():
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_definition}")
            print(f"✅ 添加列 {table}.{column}")
    except Exception as e:
        print(f"⚠️ 添加列 {table}.{column} 时出错: {e}")

def init_db():
    """不删除数据，仅创建缺失的表和字段"""
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # 用户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(50),
                    gender VARCHAR(10) DEFAULT '保密',
                    user_type VARCHAR(20) DEFAULT 'user',
                    position VARCHAR(100),
                    email VARCHAR(100),
                    phone VARCHAR(50),
                    is_active TINYINT DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # 项目表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(50) NOT NULL UNIQUE,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    status VARCHAR(20) DEFAULT '未启动',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            ensure_column_exists(cursor, "projects", "category", "category VARCHAR(50) DEFAULT NULL")
            ensure_column_exists(cursor, "projects", "priority", "priority VARCHAR(20) DEFAULT '中'")
            ensure_column_exists(cursor, "projects", "tags", "tags TEXT DEFAULT NULL")
            ensure_column_exists(cursor, "projects", "shipping_date", "shipping_date DATE DEFAULT NULL")
            ensure_column_exists(cursor, "projects", "auto_start", "auto_start TINYINT DEFAULT 0")
            ensure_column_exists(cursor, "projects", "image_url", "image_url VARCHAR(500) DEFAULT NULL")
            ensure_column_exists(cursor, "projects", "completed_date", "completed_date DATE DEFAULT NULL")
            
            # 任务表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    project_code VARCHAR(50) NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    assignee VARCHAR(50),
                    status ENUM('pending', 'in_progress', 'completed', 'delayed') DEFAULT 'pending',
                    due_date DATE,
                    completed_at TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX (project_code),
                    INDEX (assignee),
                    FOREIGN KEY (project_code) REFERENCES projects(code) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            try:
                cursor.execute("ALTER TABLE tasks MODIFY COLUMN status ENUM('pending', 'in_progress', 'completed', 'delayed') DEFAULT 'pending'")
            except: pass
            
            ensure_column_exists(cursor, "tasks", "milestone_key", "milestone_key VARCHAR(50) DEFAULT NULL")
            ensure_column_exists(cursor, "tasks", "priority", "priority ENUM('low', 'medium', 'high') DEFAULT 'medium'")
            ensure_column_exists(cursor, "tasks", "feedback", "feedback TEXT DEFAULT NULL")
            ensure_column_exists(cursor, "tasks", "feedback_files", "feedback_files TEXT DEFAULT NULL")
            ensure_column_exists(cursor, "tasks", "completed_by", "completed_by VARCHAR(50) DEFAULT NULL")
            ensure_column_exists(cursor, "tasks", "review_feedback", "review_feedback TEXT DEFAULT NULL")
            ensure_column_exists(cursor, "tasks", "current_review_status", "current_review_status VARCHAR(20) DEFAULT 'pending'")
            ensure_column_exists(cursor, "tasks", "reviewer", "reviewer VARCHAR(50) DEFAULT NULL")
            ensure_column_exists(cursor, "tasks", "reviewed_at", "reviewed_at TIMESTAMP NULL")
            ensure_column_exists(cursor, "tasks", "reviewers", "reviewers TEXT DEFAULT NULL")
            
            # 操作日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    operator VARCHAR(50) NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    target_type VARCHAR(20) NOT NULL,
                    target_name VARCHAR(200) NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX (operator),
                    INDEX (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_sequence (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    seq INT NOT NULL DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_requirements (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    project_code VARCHAR(50) NOT NULL,
                    requirement TEXT NOT NULL,
                    is_original TINYINT DEFAULT 0,
                    added_by VARCHAR(50) NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX (project_code),
                    FOREIGN KEY (project_code) REFERENCES projects(code) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS milestone_definitions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    phase VARCHAR(20) NOT NULL,
                    milestone_key VARCHAR(50) NOT NULL UNIQUE,
                    milestone_name VARCHAR(100) NOT NULL,
                    sort_order INT DEFAULT 0,
                    INDEX (phase)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            cursor.execute("SELECT COUNT(*) as cnt FROM milestone_definitions")
            if cursor.fetchone()['cnt'] == 0:
                milestones = [
                    ('前期', 'feasibility_study', '可行性研讨', 1),
                    ('前期', 'appearance_drawing', '外观图纸处理', 2),
                    ('前期', 'structure_drawing', '结构方案图处理', 3),
                    ('前期', 'model_validation', '模型验证', 4),
                    ('前期', 'quotation', '报价', 5),
                    ('中期', 'drawing_refinement', '图纸细化', 6),
                    ('中期', 'mold_making', '模具制作', 7),
                    ('中期', 'nameplate_marking', '铭牌标记制作', 8),
                    ('中期', 'product_certification', '产品测试认证', 9),
                    ('后期', 'production_tracking', '生产跟踪', 10),
                    ('后期', 'mold_payment', '模具费用支付申请', 11),
                    ('后期', 'archive', '资料归档', 12),
                ]
                for m in milestones:
                    cursor.execute("INSERT INTO milestone_definitions (phase, milestone_key, milestone_name, sort_order) VALUES (%s, %s, %s, %s)", m)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_milestones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    project_code VARCHAR(50) NOT NULL,
                    milestone_key VARCHAR(50) NOT NULL,
                    status ENUM('not_started', 'task_published', 'in_progress', 'completed') DEFAULT 'not_started',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_project_milestone (project_code, milestone_key),
                    INDEX (project_code),
                    FOREIGN KEY (project_code) REFERENCES projects(code) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    config_key VARCHAR(50) NOT NULL UNIQUE,
                    config_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            default_configs = [
                ('logo_text', '📦 PM_SYSTEM'),
                ('system_name', '项目管理系统'),
                ('language', 'zh'),
                ('theme', 'light')
            ]
            for key, value in default_configs:
                cursor.execute("INSERT IGNORE INTO system_config (config_key, config_value) VALUES (%s, %s)", (key, value))
            
            cursor.execute("SELECT COUNT(*) as cnt FROM project_sequence")
            if cursor.fetchone()['cnt'] == 0:
                cursor.execute("SELECT MAX(CAST(SUBSTRING_INDEX(code, '-', -1) AS UNSIGNED)) as max_seq FROM projects WHERE code LIKE 'PROJ-%'")
                result = cursor.fetchone()
                max_seq = result['max_seq'] if result and result['max_seq'] else 0
                cursor.execute("INSERT INTO project_sequence (seq) VALUES (%s)", (max_seq,))
                connection.commit()
            
            cursor.execute("SELECT id FROM users WHERE username = 'admin'")
            if not cursor.fetchone():
                admin_pwd = hash_password("admin123")
                cursor.execute("INSERT INTO users (username, password_hash, name, user_type, position, email, is_active) VALUES ('admin', %s, '核心管理员', 'admin', '系统总监', 'admin@renbin.ren', 1)", (admin_pwd,))
            else:
                cursor.execute("UPDATE users SET user_type = 'admin' WHERE username = 'admin'")
            
            connection.commit()
            print("✅ 数据库修复/初始化完成")
    except Exception as e:
        print(f"❌ 数据库操作错误: {str(e)}")
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()

def reset_db():
    """完全重置数据库：删除所有表，重建结构，保留 admin 用户"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[list(row.keys())[0]] for row in cursor.fetchall()]
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            connection.commit()
            print("✅ 所有表已删除")
    except Exception as e:
        print(f"❌ 删除表失败: {str(e)}")
        raise
    finally:
        connection.close()
    init_db()

# 初始化数据库
init_db()

# 导入路由模块
import auth
import projects
import stats
import logs
import events
import config

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(stats.router)
app.include_router(logs.router)
app.include_router(events.router)
app.include_router(config.router)

# 管理员重置系统接口
class ResetSystemRequest(BaseModel):
    mode: str  # "repair" 或 "full"

@app.post("/api/admin/reset-system")
async def admin_reset_system(request: Request, req: ResetSystemRequest):
    username = request.headers.get("X-Username")
    if username != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    if req.mode == "repair":
        try:
            init_db()
            return {"code": "SUCCESS", "message": "数据库结构修复完成，缺失的表和字段已添加，现有数据未受影响。"}
        except Exception as e:
            return {"code": "ERROR", "detail": str(e)}
    elif req.mode == "full":
        try:
            reset_db()
            return {"code": "SUCCESS", "message": "系统已完全重置，所有数据已清空，管理员账户保留。请重新登录。"}
        except Exception as e:
            return {"code": "ERROR", "detail": str(e)}
    else:
        return {"code": "ERROR", "detail": "无效的模式参数"}

# 静态页面路由
@app.get("/", response_class=HTMLResponse)
def read_index():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if not os.path.exists(index_path):
        index_path = os.path.join(os.path.dirname(__file__), "views", "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"无法读取主模板: {str(e)}")

@app.get("/views/{filename}", response_class=HTMLResponse)
def read_sub_view(filename: str):
    if not filename.endswith(".html"):
        raise HTTPException(status_code=400, detail="仅支持 HTML 文件")
    view_path = os.path.join(os.path.dirname(__file__), "views", filename)
    if not os.path.exists(view_path):
        raise HTTPException(status_code=404, detail=f"视图文件 {filename} 不存在")
    try:
        with open(view_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取子视图失败: {str(e)}")

@app.get("/project-detail", response_class=HTMLResponse)
def project_detail():
    view_path = os.path.join(os.path.dirname(__file__), "views", "project_detail.html")
    if not os.path.exists(view_path):
        raise HTTPException(status_code=404, detail="项目详情页面不存在")
    try:
        with open(view_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取详情页失败: {str(e)}")

@app.get("/task-detail", response_class=HTMLResponse)
def task_detail():
    view_path = os.path.join(os.path.dirname(__file__), "views", "task_detail.html")
    if not os.path.exists(view_path):
        raise HTTPException(status_code=404, detail="任务详情页面不存在")
    try:
        with open(view_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取任务详情页失败: {str(e)}")