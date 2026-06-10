# projects.py
import re
import os
import json
import shutil
from datetime import datetime
from fastapi import APIRouter, Request, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from database import get_db_connection

router = APIRouter(prefix="/api/projects", tags=["高级项目全要素管理模块"])

class AdvancedProjectCreateRequest(BaseModel):
    name: str
    story: str
    requirements: List[str]
    tags: str
    category: str
    priority: str
    shipping_date: str
    auto_start: bool

class AddRequirementRequest(BaseModel):
    requirement: str

class PublishTaskRequest(BaseModel):
    title: str
    assignee: Optional[str] = ""
    priority: Optional[str] = "medium"
    due_date: Optional[str] = None
    reviewers: Optional[List[str]] = []

class UpdateTaskStatusRequest(BaseModel):
    status: str

# ========== 文件上传辅助函数 ==========

UPLOAD_BASE_DIR = "upload"

def get_project_upload_folder(project_code):
    folder_path = os.path.join(UPLOAD_BASE_DIR, project_code)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def get_project_image_folder(project_code):
    folder_path = os.path.join(UPLOAD_BASE_DIR, "images", project_code)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def get_next_file_number(project_code, original_filename, date_str):
    folder_path = get_project_upload_folder(project_code)
    base_name = os.path.splitext(original_filename)[0]
    ext = os.path.splitext(original_filename)[1]
    
    pattern = f"{base_name}_{date_str}_"
    existing = [f for f in os.listdir(folder_path) if f.startswith(pattern)]
    max_num = 0
    for f in existing:
        parts = f.split('_')
        if len(parts) >= 3:
            try:
                num = int(parts[-1].split('.')[0])
                max_num = max(max_num, num)
            except:
                pass
    next_num = max_num + 1
    return f"{base_name}_{date_str}_{next_num:03d}{ext}"

def save_upload_files(project_code, files):
    saved_files = []
    if not files:
        return saved_files
    
    date_str = datetime.now().strftime("%Y%m%d")
    for file in files:
        if file.filename:
            new_filename = get_next_file_number(project_code, file.filename, date_str)
            file_path = os.path.join(get_project_upload_folder(project_code), new_filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            saved_files.append(f"/upload/{project_code}/{new_filename}")
    return saved_files

def extract_seq_from_code(code: str) -> int:
    match_new = re.search(r'PROJ-\d{8}-(\d+)$', code)
    if match_new:
        return int(match_new.group(1))
    match_old = re.search(r'PROJ-(\d+)$', code)
    if match_old:
        return int(match_old.group(1))
    return 0

def generate_project_code(cursor) -> str:
    today = datetime.now().strftime("%Y%m%d")
    cursor.execute("SELECT seq FROM project_sequence FOR UPDATE")
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO project_sequence (seq) VALUES (0)")
        current_seq = 0
    else:
        current_seq = row['seq']
    new_seq = current_seq + 1
    cursor.execute("UPDATE project_sequence SET seq = %s", (new_seq,))
    return f"PROJ-{today}-{new_seq:03d}"

def insert_operation_log(cursor, operator: str, action: str, target_type: str, target_name: str, details: str = None):
    cursor.execute("""
        INSERT INTO operation_logs (operator, action, target_type, target_name, details)
        VALUES (%s, %s, %s, %s, %s)
    """, (operator, action, target_type, target_name, details))
    
    # 发送实时事件通知
    try:
        from events import notify_log_created
        notify_log_created({
            "id": cursor.lastrowid,
            "operator": operator,
            "action": action,
            "target_type": target_type,
            "target_name": target_name,
            "details": details
        })
    except ImportError:
        pass
    except Exception as e:
        print(f"发送事件通知失败: {e}")


def get_operator_from_request(request: Request, default: str = "admin") -> str:
    """从请求中获取操作者用户名"""
    username = request.headers.get("X-Username")
    if username:
        print(f"📝 从 X-Username 获取操作者: {username}")
        return username
    
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token.startswith("mock_token_"):
            parts = token.split("_")
            if len(parts) >= 2:
                print(f"📝 从 Token 解析操作者: {parts[1]}")
                return parts[1]
    
    print(f"⚠️ 无法从请求头获取操作者，使用默认值: {default}")
    return default


# ========== 1. 固定路径接口（优先） ==========

@router.get("/list")
def get_projects_list():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM projects")
            columns = [row["Field"] for row in cursor.fetchall()]
            select_fields = ["id", "name", "code", "description", "status", "created_at", "image_url", "completed_date"]
            optional_fields = ["category", "priority", "tags", "shipping_date", "auto_start"]
            for field in optional_fields:
                if field in columns:
                    select_fields.append(field)
            sql = f"SELECT {', '.join(select_fields)} FROM projects WHERE completed_date IS NULL ORDER BY id DESC"
            cursor.execute(sql)
            rows = cursor.fetchall()
            projects = []
            for row in rows:
                if "created_at" in row and row["created_at"]:
                    row["date"] = row["created_at"].strftime("%Y-%m-%d") if hasattr(row["created_at"], "strftime") else str(row["created_at"])
                else:
                    row["date"] = ""
                projects.append(row)
            return {"code": "SUCCESS", "data": projects}
    except Exception as e:
        print(f"[ERROR] /api/projects/list: {str(e)}")
        return {"code": "ERROR", "detail": f"查询项目列表失败: {str(e)}"}
    finally:
        connection.close()


@router.get("/archive-list")
def get_archive_projects_list():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM projects")
            columns = [row["Field"] for row in cursor.fetchall()]
            select_fields = ["id", "name", "code", "description", "status", "created_at", "image_url", "completed_date"]
            optional_fields = ["category", "priority", "tags", "shipping_date", "auto_start"]
            for field in optional_fields:
                if field in columns:
                    select_fields.append(field)
            sql = f"SELECT {', '.join(select_fields)} FROM projects WHERE completed_date IS NOT NULL ORDER BY completed_date DESC"
            cursor.execute(sql)
            rows = cursor.fetchall()
            projects = []
            for row in rows:
                if "created_at" in row and row["created_at"]:
                    row["date"] = row["created_at"].strftime("%Y-%m-%d") if hasattr(row["created_at"], "strftime") else str(row["created_at"])
                else:
                    row["date"] = ""
                if "completed_date" in row and row["completed_date"]:
                    row["completed_date"] = row["completed_date"].strftime("%Y-%m-%d") if hasattr(row["completed_date"], "strftime") else str(row["completed_date"])
                projects.append(row)
            return {"code": "SUCCESS", "data": projects}
    except Exception as e:
        print(f"[ERROR] /api/projects/archive-list: {str(e)}")
        return {"code": "ERROR", "detail": f"查询归档项目列表失败: {str(e)}"}
    finally:
        connection.close()


@router.get("/categories")
def get_project_categories():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM projects LIKE 'category'")
            if not cursor.fetchone():
                default_cats = ["⚙️ 机械结构类产品", "🔌 自动化控制/气动系统", "🤖 软件AI代理/局部署容器", "🛠️ 通用工装/治具/打样手模"]
                return {"code": "SUCCESS", "data": default_cats}
            cursor.execute("SELECT DISTINCT category FROM projects WHERE category IS NOT NULL AND category != ''")
            categories = [row["category"] for row in cursor.fetchall()]
            default_cats = ["⚙️ 机械结构类产品", "🔌 自动化控制/气动系统", "🤖 软件AI代理/局部署容器", "🛠️ 通用工装/治具/打样手模"]
            for cat in default_cats:
                if cat not in categories:
                    categories.append(cat)
            return {"code": "SUCCESS", "data": categories}
    except Exception as e:
        return {"code": "ERROR", "detail": f"加载类别失败: {str(e)}"}
    finally:
        connection.close()


@router.get("/search")
def search_projects(
    keyword: str = None,
    category: str = None,
    tag: str = None,
    created_start: str = None,
    created_end: str = None,
    shipping_start: str = None,
    shipping_end: str = None,
    completed_start: str = None,
    completed_end: str = None,
    include_archived: str = "true"
):
    """高级项目搜索"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM projects")
            columns = [row["Field"] for row in cursor.fetchall()]
            select_fields = ["id", "name", "code", "description", "status", "created_at", "image_url", "completed_date"]
            optional_fields = ["category", "priority", "tags", "shipping_date", "auto_start"]
            for field in optional_fields:
                if field in columns:
                    select_fields.append(field)
            
            sql = f"SELECT {', '.join(select_fields)} FROM projects WHERE 1=1"
            params = []
            
            include_archived_bool = include_archived.lower() == "true"
            if not include_archived_bool:
                sql += " AND completed_date IS NULL"
            
            if keyword and keyword.strip():
                sql += " AND (name LIKE %s OR code LIKE %s OR description LIKE %s)"
                like_pattern = f"%{keyword.strip()}%"
                params.extend([like_pattern, like_pattern, like_pattern])
            
            if category and category != 'all' and category != '':
                sql += " AND category = %s"
                params.append(category)
            
            if tag and tag.strip():
                sql += " AND tags LIKE %s"
                params.append(f"%{tag.strip()}%")
            
            if created_start:
                sql += " AND DATE(created_at) >= %s"
                params.append(created_start)
            if created_end:
                sql += " AND DATE(created_at) <= %s"
                params.append(created_end)
            
            if "shipping_date" in columns:
                if shipping_start:
                    sql += " AND shipping_date >= %s"
                    params.append(shipping_start)
                if shipping_end:
                    sql += " AND shipping_date <= %s"
                    params.append(shipping_end)
            
            if completed_start:
                sql += " AND completed_date >= %s"
                params.append(completed_start)
            if completed_end:
                sql += " AND completed_date <= %s"
                params.append(completed_end)
            
            sql += " ORDER BY created_at DESC"
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            projects = []
            for row in rows:
                if "created_at" in row and row["created_at"]:
                    row["date"] = row["created_at"].strftime("%Y-%m-%d") if hasattr(row["created_at"], "strftime") else str(row["created_at"])
                else:
                    row["date"] = ""
                if "completed_date" in row and row["completed_date"]:
                    row["completed_date"] = row["completed_date"].strftime("%Y-%m-%d") if hasattr(row["completed_date"], "strftime") else str(row["completed_date"])
                projects.append(row)
            return {"code": "SUCCESS", "data": projects}
    except Exception as e:
        print(f"[ERROR] /api/projects/search: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.get("/users/list-simple")
def get_users_simple():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT username, name FROM users WHERE is_active = 1 ORDER BY username")
            users = cursor.fetchall()
            return {"code": "SUCCESS", "data": users}
    except Exception as e:
        print(f"[ERROR] /api/projects/users/list-simple: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


# ========== 2. 任务中心接口 ==========

@router.get("/tasks/all")
def get_all_tasks(
    sort_by: str = "created_at",
    priority: str = None,
    status: str = None
):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT t.*, p.name as project_name,
                       DATE_FORMAT(t.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at_str,
                       DATE_FORMAT(t.due_date, '%%Y-%%m-%%d') as due_date_str,
                       DATE_FORMAT(t.completed_at, '%%Y-%%m-%%d %%H:%%i:%%s') as completed_at_str
                FROM tasks t
                JOIN projects p ON t.project_code = p.code
                WHERE 1=1
            """
            params = []
            
            if priority and priority != 'all':
                sql += " AND t.priority = %s"
                params.append(priority)
            
            if status and status != 'all':
                sql += " AND t.status = %s"
                params.append(status)
            
            if sort_by == 'created_at':
                sql += " ORDER BY t.created_at DESC"
            elif sort_by == 'priority':
                sql += " ORDER BY FIELD(t.priority, 'high', 'medium', 'low')"
            elif sort_by == 'due_date':
                sql += " ORDER BY CASE WHEN t.due_date IS NULL THEN 1 ELSE 0 END, t.due_date ASC"
            else:
                sql += " ORDER BY t.created_at DESC"
            
            cursor.execute(sql, params)
            tasks = cursor.fetchall()
            return {"code": "SUCCESS", "data": tasks}
    except Exception as e:
        print(f"[ERROR] /api/projects/tasks/all: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.get("/tasks/my")
def get_my_tasks(
    username: str,
    sort_by: str = "created_at",
    priority: str = None,
    status: str = None
):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT t.*, p.name as project_name,
                       DATE_FORMAT(t.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at_str,
                       DATE_FORMAT(t.due_date, '%%Y-%%m-%%d') as due_date_str,
                       DATE_FORMAT(t.completed_at, '%%Y-%%m-%%d %%H:%%i:%%s') as completed_at_str
                FROM tasks t
                JOIN projects p ON t.project_code = p.code
                WHERE t.assignee = %s
            """
            params = [username]
            
            if priority and priority != 'all':
                sql += " AND t.priority = %s"
                params.append(priority)
            
            if status and status != 'all':
                sql += " AND t.status = %s"
                params.append(status)
            
            if sort_by == 'created_at':
                sql += " ORDER BY t.created_at DESC"
            elif sort_by == 'priority':
                sql += " ORDER BY FIELD(t.priority, 'high', 'medium', 'low')"
            elif sort_by == 'due_date':
                sql += " ORDER BY CASE WHEN t.due_date IS NULL THEN 1 ELSE 0 END, t.due_date ASC"
            else:
                sql += " ORDER BY t.created_at DESC"
            
            cursor.execute(sql, params)
            tasks = cursor.fetchall()
            return {"code": "SUCCESS", "data": tasks}
    except Exception as e:
        print(f"[ERROR] /api/projects/tasks/my: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.get("/tasks/completed")
def get_completed_tasks(
    sort_by: str = "completed_at",
    priority: str = None
):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT t.*, p.name as project_name,
                       DATE_FORMAT(t.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at_str,
                       DATE_FORMAT(t.due_date, '%%Y-%%m-%%d') as due_date_str,
                       DATE_FORMAT(t.completed_at, '%%Y-%%m-%%d %%H:%%i:%%s') as completed_at_str
                FROM tasks t
                JOIN projects p ON t.project_code = p.code
                WHERE t.status = 'completed'
            """
            params = []
            
            if priority and priority != 'all':
                sql += " AND t.priority = %s"
                params.append(priority)
            
            if sort_by == 'created_at':
                sql += " ORDER BY t.created_at DESC"
            elif sort_by == 'completed_at':
                sql += " ORDER BY t.completed_at DESC"
            else:
                sql += " ORDER BY t.completed_at DESC"
            
            cursor.execute(sql, params)
            tasks = cursor.fetchall()
            return {"code": "SUCCESS", "data": tasks}
    except Exception as e:
        print(f"[ERROR] /api/projects/tasks/completed: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.get("/tasks/{task_id}")
def get_task_detail(task_id: int):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT t.*, p.name as project_name, p.code as project_code,
                       DATE_FORMAT(t.created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at_str,
                       DATE_FORMAT(t.due_date, '%%Y-%%m-%%d') as due_date_str,
                       DATE_FORMAT(t.completed_at, '%%Y-%%m-%%d %%H:%%i:%%s') as completed_at_str
                FROM tasks t
                JOIN projects p ON t.project_code = p.code
                WHERE t.id = %s
            """, (task_id,))
            task = cursor.fetchone()
            if not task:
                return {"code": "ERROR", "detail": "任务不存在"}
            
            if task.get('feedback_files'):
                try:
                    task['feedback_files'] = task['feedback_files'].split(',') if task['feedback_files'] else []
                except:
                    task['feedback_files'] = []
            else:
                task['feedback_files'] = []
            
            if task.get('reviewers'):
                try:
                    task['reviewers'] = json.loads(task['reviewers'])
                except:
                    task['reviewers'] = []
            else:
                task['reviewers'] = []
            
            if task.get('review_feedback'):
                try:
                    task['review_records'] = json.loads(task['review_feedback'])
                except:
                    task['review_records'] = []
            else:
                task['review_records'] = []
            
            return {"code": "SUCCESS", "data": task}
    except Exception as e:
        print(f"[ERROR] /api/projects/tasks/{task_id}: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.post("/tasks/{task_id}/complete")
async def complete_task(task_id: int, request: Request):
    operator = get_operator_from_request(request, "admin")
    form = await request.form()
    feedback = form.get("feedback")
    
    files = []
    for key in form:
        if key == "files" or key.startswith("files"):
            f = form[key]
            if hasattr(f, "filename") and f.filename:
                files.append(f)
    
    print(f"完成任务 - task_id: {task_id}, operator: {operator}")
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT t.*, p.name as project_name, p.code as project_code, md.milestone_name
                FROM tasks t
                JOIN projects p ON t.project_code = p.code
                JOIN milestone_definitions md ON t.milestone_key = md.milestone_key
                WHERE t.id = %s
            """, (task_id,))
            task = cursor.fetchone()
            if not task:
                return {"code": "ERROR", "detail": "任务不存在"}
            
            if task['status'] != 'in_progress':
                return {"code": "ERROR", "detail": "只有进行中的任务可以标记为完成"}
            
            saved_files = save_upload_files(task['project_code'], files) if files else []
            completed_at = datetime.now()
            existing_files = task.get('feedback_files') or ''
            if existing_files and saved_files:
                feedback_files_str = existing_files + ',' + ','.join(saved_files)
            elif saved_files:
                feedback_files_str = ','.join(saved_files)
            else:
                feedback_files_str = existing_files
            
            review_records = []
            if task.get('review_feedback'):
                try:
                    review_records = json.loads(task['review_feedback'])
                except:
                    review_records = []
            
            completion_record = {
                "id": len(review_records) + 1,
                "type": "completion",
                "operator": operator,
                "action": "complete",
                "action_text": "完成任务",
                "feedback": feedback or "",
                "files": saved_files,
                "created_at": completed_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            review_records.append(completion_record)
            
            cursor.execute("""
                UPDATE tasks 
                SET status = 'completed', 
                    completed_at = %s,
                    feedback = %s,
                    feedback_files = %s,
                    completed_by = %s,
                    current_review_status = 'pending',
                    review_feedback = %s
                WHERE id = %s
            """, (completed_at, feedback, feedback_files_str, operator, json.dumps(review_records), task_id))
            
            insert_operation_log(cursor, operator, "complete_task", "task", task['title'],
                                f"项目: {task['project_name']}, 里程碑: {task['milestone_name']}")
            
            connection.commit()
            return {"code": "SUCCESS", "message": "任务已完成，等待审核", "files": saved_files}
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] 完成任务失败: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.post("/tasks/{task_id}/start")
def start_task(task_id: int, request: Request):
    operator = get_operator_from_request(request, "admin")
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT t.*, p.name as project_name, md.milestone_name
                FROM tasks t
                JOIN projects p ON t.project_code = p.code
                JOIN milestone_definitions md ON t.milestone_key = md.milestone_key
                WHERE t.id = %s
            """, (task_id,))
            task = cursor.fetchone()
            if not task:
                return {"code": "ERROR", "detail": "任务不存在"}
            
            if task['status'] != 'pending':
                return {"code": "ERROR", "detail": "只有待处理的任务可以开始"}
            
            cursor.execute("UPDATE tasks SET status = 'in_progress' WHERE id = %s", (task_id,))
            cursor.execute("""
                UPDATE project_milestones 
                SET status = 'in_progress'
                WHERE project_code = %s AND milestone_key = %s AND status != 'completed'
            """, (task['project_code'], task['milestone_key']))
            
            insert_operation_log(cursor, operator, "start_task", "task", task['title'],
                                f"项目: {task['project_name']}, 里程碑: {task['milestone_name']}")
            
            connection.commit()
            return {"code": "SUCCESS", "message": "任务已开始"}
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] 开始任务失败: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.post("/tasks/{task_id}/submit-review")
async def submit_task_review(task_id: int, request: Request):
    operator = get_operator_from_request(request, "admin")
    form = await request.form()
    action = form.get("action")
    feedback = form.get("feedback")
    
    if action not in ['approve', 'reject']:
        return {"code": "ERROR", "detail": "无效的审校操作"}
    
    files = []
    for key in form:
        if key == "files" or key.startswith("files"):
            f = form[key]
            if hasattr(f, "filename") and f.filename:
                files.append(f)
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT t.*, p.name as project_name, p.code as project_code, md.milestone_name
                FROM tasks t
                JOIN projects p ON t.project_code = p.code
                JOIN milestone_definitions md ON t.milestone_key = md.milestone_key
                WHERE t.id = %s
            """, (task_id,))
            task = cursor.fetchone()
            if not task:
                return {"code": "ERROR", "detail": "任务不存在"}
            
            if task['status'] != 'completed':
                return {"code": "ERROR", "detail": "只有已完成的任务才能进行审校"}
            
            reviewers = []
            if task.get('reviewers'):
                try:
                    reviewers = json.loads(task['reviewers'])
                except:
                    reviewers = []
            
            is_admin = operator == 'admin'
            is_reviewer = operator in reviewers
            
            if not (is_admin or is_reviewer):
                return {"code": "ERROR", "detail": "您没有权限审校此任务"}
            
            saved_files = save_upload_files(task['project_code'], files) if files else []
            
            review_records = []
            if task.get('review_feedback'):
                try:
                    review_records = json.loads(task['review_feedback'])
                except:
                    review_records = []
            
            new_record = {
                "id": len(review_records) + 1,
                "type": "review",
                "reviewer": operator,
                "action": action,
                "action_text": "通过" if action == 'approve' else "退回",
                "feedback": feedback or "",
                "files": saved_files,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            review_records.append(new_record)
            
            if action == 'approve':
                new_status = 'completed'
                current_review_status = 'approved'
                if task['milestone_key'] == 'archive':
                    cursor.execute("UPDATE projects SET completed_date = CURDATE() WHERE code = %s", (task['project_code'],))
            else:
                new_status = 'in_progress'
                current_review_status = 'rejected'
            
            cursor.execute("""
                UPDATE tasks 
                SET status = %s,
                    current_review_status = %s,
                    reviewer = %s,
                    reviewed_at = %s,
                    review_feedback = %s
                WHERE id = %s
            """, (new_status, current_review_status, operator, datetime.now(), json.dumps(review_records), task_id))
            
            insert_operation_log(cursor, operator, f"review_task_{action}", "task", task['title'],
                                f"项目: {task['project_name']}, 里程碑: {task['milestone_name']}")
            
            connection.commit()
            return {"code": "SUCCESS", "message": "审校已提交", "action": action}
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] 审校任务失败: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, request: Request):
    operator = get_operator_from_request(request, "admin")
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT t.*, p.name as project_name, p.code as project_code, md.milestone_name
                FROM tasks t
                JOIN projects p ON t.project_code = p.code
                JOIN milestone_definitions md ON t.milestone_key = md.milestone_key
                WHERE t.id = %s
            """, (task_id,))
            task = cursor.fetchone()
            if not task:
                return {"code": "ERROR", "detail": "任务不存在"}
            
            cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            insert_operation_log(cursor, operator, "delete_task", "task", task['title'],
                                f"项目: {task['project_name']}, 里程碑: {task['milestone_name']}")
            connection.commit()
            return {"code": "SUCCESS", "message": "任务已删除"}
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] 删除任务失败: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


# ========== 3. 带项目编码参数的接口 ==========

@router.post("/add")
def add_project(data: AdvancedProjectCreateRequest, request: Request):
    connection = get_db_connection()
    operator = get_operator_from_request(request, "admin")
    print(f"📝 创建项目，操作者: {operator}")
    
    try:
        with connection.cursor() as cursor:
            project_code = generate_project_code(cursor)
            
            cursor.execute("SHOW COLUMNS FROM projects")
            columns = [row["Field"] for row in cursor.fetchall()]
            insert_fields = ["code", "name", "description", "status"]
            insert_values = [project_code, data.name, data.story, "进行中" if data.auto_start else "未启动"]
            optional_map = {
                "category": data.category,
                "priority": data.priority,
                "tags": data.tags,
                "shipping_date": data.shipping_date,
                "auto_start": 1 if data.auto_start else 0
            }
            for field, value in optional_map.items():
                if field in columns:
                    insert_fields.append(field)
                    insert_values.append(value)
            placeholders = ", ".join(["%s"] * len(insert_fields))
            sql = f"INSERT INTO projects ({', '.join(insert_fields)}) VALUES ({placeholders})"
            cursor.execute(sql, insert_values)
            
            for req in data.requirements:
                if req and req.strip():
                    cursor.execute("""
                        INSERT INTO project_requirements (project_code, requirement, is_original, added_by)
                        VALUES (%s, %s, 1, %s)
                    """, (project_code, req.strip(), operator))
            
            cursor.execute("SELECT milestone_key FROM milestone_definitions")
            all_milestones = cursor.fetchall()
            for m in all_milestones:
                cursor.execute("""
                    INSERT IGNORE INTO project_milestones (project_code, milestone_key, status)
                    VALUES (%s, %s, 'not_started')
                """, (project_code, m['milestone_key']))
            
            insert_operation_log(cursor, operator, "create_project", "project", data.name, f"项目编码: {project_code}")
            connection.commit()
            print(f"✅ 项目创建成功: {project_code}, 操作者: {operator}")
            return {"code": "SUCCESS", "message": "项目创建成功", "project_code": project_code}
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] /api/projects/add: {str(e)}")
        return {"code": "ERROR", "detail": f"数据库写入失败: {str(e)}"}
    finally:
        connection.close()


@router.delete("/{code}")
def delete_project(code: str, request: Request):
    operator = get_operator_from_request(request, "admin")
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM projects WHERE code = %s", (code,))
            proj = cursor.fetchone()
            if not proj:
                return {"code": "ERROR", "detail": "项目不存在"}
            project_name = proj["name"]
            cursor.execute("DELETE FROM projects WHERE code = %s", (code,))
            insert_operation_log(cursor, operator, "delete_project", "project", project_name, f"项目编码: {code}")
            connection.commit()
            return {"code": "SUCCESS", "message": "项目已删除"}
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] 删除项目失败: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.get("/{code}/milestones")
def get_project_milestones(code: str):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT code FROM projects WHERE code = %s", (code,))
            if not cursor.fetchone():
                return {"code": "ERROR", "detail": "项目不存在"}
            
            cursor.execute("SELECT milestone_key, milestone_name, phase, sort_order FROM milestone_definitions ORDER BY sort_order")
            all_milestones = cursor.fetchall()
            
            cursor.execute("SELECT milestone_key, status FROM project_milestones WHERE project_code = %s", (code,))
            milestone_status = {row['milestone_key']: row['status'] for row in cursor.fetchall()}
            
            result = []
            for m in all_milestones:
                status = milestone_status.get(m['milestone_key'], 'not_started')
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_tasks,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
                        SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_tasks,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_tasks
                    FROM tasks                    WHERE project_code = %s AND milestone_key = %s
                """, (code, m['milestone_key']))
                task_stats = cursor.fetchone()
                
                result.append({
                    'milestone_key': m['milestone_key'],
                    'milestone_name': m['milestone_name'],
                    'phase': m['phase'],
                    'sort_order': m['sort_order'],
                    'status': status,
                    'task_stats': {
                        'total': task_stats['total_tasks'] or 0,
                        'completed': task_stats['completed_tasks'] or 0,
                        'in_progress': task_stats['in_progress_tasks'] or 0,
                        'pending': task_stats['pending_tasks'] or 0
                    }
                })
            
            return {"code": "SUCCESS", "data": result}
    except Exception as e:
        print(f"[ERROR] /api/projects/{code}/milestones: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.get("/{code}/milestones/{milestone_key}/tasks")
def get_milestone_tasks(code: str, milestone_key: str, sort_by: str = "created_at", priority: str = None):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT id, title, description, assignee, status, priority, 
                       due_date, completed_at, created_at,
                       DATE_FORMAT(created_at, '%%Y-%%m-%%d %%H:%%i:%%s') as created_at_str,
                       DATE_FORMAT(due_date, '%%Y-%%m-%%d') as due_date_str
                FROM tasks
                WHERE project_code = %s AND milestone_key = %s
            """
            params = [code, milestone_key]
            
            if priority and priority != 'all':
                sql += " AND priority = %s"
                params.append(priority)
            
            if sort_by == 'created_at':
                sql += " ORDER BY created_at DESC"
            elif sort_by == 'priority':
                sql += " ORDER BY FIELD(priority, 'high', 'medium', 'low')"
            elif sort_by == 'due_date':
                sql += " ORDER BY due_date ASC"
            else:
                sql += " ORDER BY created_at DESC"
            
            cursor.execute(sql, params)
            tasks = cursor.fetchall()
            return {"code": "SUCCESS", "data": tasks}
    except Exception as e:
        print(f"[ERROR] /api/projects/{code}/milestones/{milestone_key}/tasks: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.post("/{code}/milestones/{milestone_key}/publish-task")
def publish_milestone_task(code: str, milestone_key: str, task_data: PublishTaskRequest, request: Request):
    operator = get_operator_from_request(request, "admin")
    title = task_data.title.strip()
    assignee = task_data.assignee
    priority = task_data.priority
    due_date = task_data.due_date
    reviewers = task_data.reviewers or []
    
    if not title:
        return {"code": "ERROR", "detail": "任务标题不能为空"}
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM projects WHERE code = %s", (code,))
            project = cursor.fetchone()
            if not project:
                return {"code": "ERROR", "detail": "项目不存在"}
            
            cursor.execute("SELECT milestone_name FROM milestone_definitions WHERE milestone_key = %s", (milestone_key,))
            milestone = cursor.fetchone()
            if not milestone:
                return {"code": "ERROR", "detail": "里程碑不存在"}
            
            reviewers_json = json.dumps(reviewers) if reviewers else "[]"
            
            cursor.execute("""
                INSERT INTO tasks (project_code, milestone_key, title, assignee, priority, due_date, status, reviewers)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
            """, (code, milestone_key, title, assignee, priority, due_date, reviewers_json))
            task_id = cursor.lastrowid
            
            cursor.execute("""
                UPDATE project_milestones 
                SET status = 'task_published'
                WHERE project_code = %s AND milestone_key = %s AND status = 'not_started'
            """, (code, milestone_key))
            
            cursor.execute("""
                INSERT IGNORE INTO project_milestones (project_code, milestone_key, status)
                VALUES (%s, %s, 'task_published')
            """, (code, milestone_key))
            
            insert_operation_log(cursor, operator, "create_task", "task", title, 
                                f"项目: {project['name']}, 里程碑: {milestone['milestone_name']}")
            
            connection.commit()
            return {"code": "SUCCESS", "message": "任务已发布", "task_id": task_id}
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] 发布任务失败: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.post("/{code}/add-requirement")
def add_project_requirement(code: str, req_data: AddRequirementRequest, request: Request):
    operator = get_operator_from_request(request, "admin")
    requirement = req_data.requirement.strip()
    if not requirement:
        return {"code": "ERROR", "detail": "需求内容不能为空"}
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT code FROM projects WHERE code = %s", (code,))
            if not cursor.fetchone():
                return {"code": "ERROR", "detail": "项目不存在"}
            
            cursor.execute("""
                INSERT INTO project_requirements (project_code, requirement, is_original, added_by)
                VALUES (%s, %s, 0, %s)
            """, (code, requirement, operator))
            connection.commit()
            return {"code": "SUCCESS", "message": "需求已添加"}
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] 添加需求失败: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.get("/{code}")
def get_project_by_code(code: str):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW COLUMNS FROM projects")
            columns = [row["Field"] for row in cursor.fetchall()]
            select_fields = ", ".join(columns)
            sql = f"SELECT {select_fields} FROM projects WHERE code = %s"
            cursor.execute(sql, (code,))
            project = cursor.fetchone()
            if not project:
                return {"code": "ERROR", "detail": "项目不存在"}
            if "created_at" in project and project["created_at"]:
                project["date"] = project["created_at"].strftime("%Y-%m-%d") if hasattr(project["created_at"], "strftime") else str(project["created_at"])
            
            cursor.execute("""
                SELECT id, requirement, is_original, added_by, 
                       DATE_FORMAT(added_at, '%%Y-%%m-%%d %%H:%%i:%%s') as added_at
                FROM project_requirements 
                WHERE project_code = %s 
                ORDER BY is_original DESC, added_at ASC
            """, (code,))
            requirements = cursor.fetchall()
            project['requirements'] = requirements
            
            return {"code": "SUCCESS", "data": project}
    except Exception as e:
        print(f"[ERROR] /api/projects/{code}: {str(e)}")
        return {"code": "ERROR", "detail": f"查询详情失败: {str(e)}"}
    finally:
        connection.close()


# ========== 4. 项目图片和状态管理接口 ==========

@router.post("/{code}/upload-image")
async def upload_project_image(code: str, request: Request, file: UploadFile = File(...)):
    operator = get_operator_from_request(request, "admin")
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_types:
        return {"code": "ERROR", "detail": "只支持 JPG、PNG、GIF、WEBP 格式的图片"}
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM projects WHERE code = %s", (code,))
            project = cursor.fetchone()
            if not project:
                return {"code": "ERROR", "detail": "项目不存在"}
            
            project_image_dir = get_project_image_folder(code)
            cursor.execute("SELECT image_url FROM projects WHERE code = %s", (code,))
            old = cursor.fetchone()
            if old and old.get('image_url'):
                old_path = os.path.join(".", old['image_url'].lstrip('/'))
                if os.path.exists(old_path):
                    os.remove(old_path)
            
            ext = os.path.splitext(file.filename)[1]
            timestamp = int(datetime.now().timestamp())
            filename = f"{code}_{timestamp}{ext}"
            file_path = os.path.join(project_image_dir, filename)
            
            contents = await file.read()
            with open(file_path, "wb") as f:
                f.write(contents)
            
            image_url = f"/upload/images/{code}/{filename}"
            cursor.execute("UPDATE projects SET image_url = %s WHERE code = %s", (image_url, code))
            connection.commit()
            
            insert_operation_log(cursor, operator, "upload_image", "project", project['name'], f"项目编码: {code}")
            return {"code": "SUCCESS", "message": "图片上传成功", "image_url": image_url}
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] 上传图片失败: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.post("/{code}/toggle-status")
def toggle_project_status(code: str, request: Request):
    operator = get_operator_from_request(request, "admin")
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT status, name, completed_date FROM projects WHERE code = %s", (code,))
            project = cursor.fetchone()
            if not project:
                return {"code": "ERROR", "detail": "项目不存在"}
            
            if project.get('completed_date'):
                return {"code": "ERROR", "detail": "项目已完结，无法更改状态"}
            
            current_status = project['status']
            if current_status == '未启动' or current_status == '已暂停':
                new_status = '进行中'
                action_text = "启动"
            elif current_status == '进行中':
                new_status = '已暂停'
                action_text = "暂停"
            else:
                return {"code": "ERROR", "detail": f"当前状态 '{current_status}' 无法切换"}
            
            cursor.execute("UPDATE projects SET status = %s WHERE code = %s", (new_status, code))
            connection.commit()
            
            insert_operation_log(cursor, operator, f"{action_text}_project", "project", project['name'],
                                f"项目编码: {code}, 新状态: {new_status}")
            
            return {"code": "SUCCESS", "message": f"项目已{action_text}", "status": new_status}
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] 切换项目状态失败: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()