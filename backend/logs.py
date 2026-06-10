# logs.py
from fastapi import APIRouter, Query
from database import get_db_connection
from datetime import datetime
from events import notify_log_created  # 导入通知函数

router = APIRouter(prefix="/api/logs", tags=["操作日志"])

@router.get("/")
def get_operation_logs(
    page: int = Query(1, ge=1), 
    page_size: int = Query(20, ge=1, le=100),
    start_date: str = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(None, description="结束日期 YYYY-MM-DD")
):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            date_condition = ""
            params = []
            
            if start_date:
                date_condition += " AND DATE(created_at) >= %s"
                params.append(start_date)
            
            if end_date:
                date_condition += " AND DATE(created_at) <= %s"
                params.append(end_date)
            
            count_sql = "SELECT COUNT(*) as total FROM operation_logs WHERE 1=1" + date_condition
            cursor.execute(count_sql, params)
            total = cursor.fetchone()['total']
            
            offset = (page - 1) * page_size
            data_sql = f"""
                SELECT id, operator, action, target_type, target_name, details, created_at
                FROM operation_logs
                WHERE 1=1 {date_condition}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([page_size, offset])
            cursor.execute(data_sql, params)
            logs = cursor.fetchall()
            
            for log in logs:
                if log['created_at']:
                    log['created_at'] = log['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            
            return {
                "code": "SUCCESS",
                "data": logs,
                "total": total,
                "page": page,
                "page_size": page_size,
                "start_date": start_date,
                "end_date": end_date
            }
    except Exception as e:
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


# 添加一个测试接口，用于测试事件推送
@router.post("/test-notify")
def test_notify():
    """测试事件推送接口"""
    notify_log_created({
        "action": "test",
        "operator": "system",
        "message": "这是一条测试通知"
    })
    return {"code": "SUCCESS", "message": "测试通知已发送"}