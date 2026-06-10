# stats.py
from fastapi import APIRouter, Query
from database import get_db_connection
from datetime import datetime

router = APIRouter(prefix="/api/stats", tags=["统计信息"])

@router.get("/overview")
def get_overview_stats(username: str = Query(None)):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 项目统计
            cursor.execute("SELECT COUNT(*) as total FROM projects")
            total_projects = cursor.fetchone()['total'] or 0
            
            cursor.execute("SELECT COUNT(*) as completed FROM projects WHERE status IN ('已完成', 'closed')")
            completed_projects = cursor.fetchone()['completed'] or 0
            
            cursor.execute("SELECT COUNT(*) as in_progress FROM projects WHERE status IN ('进行中', 'in_progress')")
            in_progress_projects = cursor.fetchone()['in_progress'] or 0
            
            delayed_projects = 0  # 项目延误暂不定义

            # 检查 tasks 表是否存在
            cursor.execute("SHOW TABLES LIKE 'tasks'")
            tasks_exist = cursor.fetchone() is not None
            
            total_tasks = 0
            completed_tasks = 0
            in_progress_tasks = 0
            delayed_tasks = 0
            my_tasks = {"total": 0, "completed": 0, "in_progress": 0, "delayed": 0}
            
            if tasks_exist:
                # 所有任务统计
                cursor.execute("SELECT COUNT(*) as cnt FROM tasks")
                total_tasks = cursor.fetchone()['cnt'] or 0
                
                cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'completed'")
                completed_tasks = cursor.fetchone()['cnt'] or 0
                
                cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'in_progress'")
                in_progress_tasks = cursor.fetchone()['cnt'] or 0
                
                # 检查 due_date 列是否存在
                cursor.execute("SHOW COLUMNS FROM tasks LIKE 'due_date'")
                has_due_date = cursor.fetchone() is not None
                if has_due_date:
                    today = datetime.now().date()
                    cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE due_date < %s AND status != 'completed'", (today,))
                    delayed_tasks = cursor.fetchone()['cnt'] or 0
                
                # 我的任务统计
                if username:
                    cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE assignee = %s", (username,))
                    my_tasks['total'] = cursor.fetchone()['cnt'] or 0
                    
                    cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE assignee = %s AND status = 'completed'", (username,))
                    my_tasks['completed'] = cursor.fetchone()['cnt'] or 0
                    
                    cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE assignee = %s AND status = 'in_progress'", (username,))
                    my_tasks['in_progress'] = cursor.fetchone()['cnt'] or 0
                    
                    if has_due_date:
                        today = datetime.now().date()
                        cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE assignee = %s AND due_date < %s AND status != 'completed'", (username, today))
                        my_tasks['delayed'] = cursor.fetchone()['cnt'] or 0

            return {
                "code": "SUCCESS",
                "data": {
                    "projects": {
                        "total": total_projects,
                        "completed": completed_projects,
                        "in_progress": in_progress_projects,
                        "delayed": delayed_projects
                    },
                    "all_tasks": {
                        "total": total_tasks,
                        "completed": completed_tasks,
                        "in_progress": in_progress_tasks,
                        "delayed": delayed_tasks
                    },
                    "my_tasks": my_tasks
                }
            }
    except Exception as e:
        print(f"[ERROR] /api/stats/overview: {str(e)}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()