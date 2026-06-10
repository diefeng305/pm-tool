# config.py
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional
from database import get_db_connection

router = APIRouter(prefix="/api/config", tags=["系统配置"])

class SystemConfigRequest(BaseModel):
    logo_text: Optional[str] = None
    system_name: Optional[str] = None
    language: Optional[str] = None
    theme: Optional[str] = None


@router.get("/")
def get_config():
    """获取系统配置"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 确保表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    config_key VARCHAR(50) NOT NULL UNIQUE,
                    config_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # 初始化默认配置
            defaults = [
                ('logo_text', '📦 PM_SYSTEM'),
                ('system_name', '项目管理系统'),
                ('language', 'zh'),
                ('theme', 'light')
            ]
            for key, val in defaults:
                cursor.execute(
                    "INSERT IGNORE INTO system_config (config_key, config_value) VALUES (%s, %s)",
                    (key, val)
                )
            
            cursor.execute("SELECT config_key, config_value FROM system_config")
            rows = cursor.fetchall()
            config = {}
            for row in rows:
                config[row['config_key']] = row['config_value']
            
            return {"code": "SUCCESS", "data": config}
    except Exception as e:
        print(f"获取配置失败: {e}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.post("/")
def update_config(data: SystemConfigRequest, request: Request):
    """更新系统配置（只有管理员可以修改）"""
    # 获取当前用户
    username = request.headers.get("X-Username", "")
    
    # 检查是否为管理员
    if username != 'admin':
        return {"code": "ERROR", "detail": "只有管理员可以修改系统配置"}
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            if data.logo_text is not None:
                cursor.execute(
                    "INSERT INTO system_config (config_key, config_value) VALUES ('logo_text', %s) ON DUPLICATE KEY UPDATE config_value = %s",
                    (data.logo_text, data.logo_text)
                )
            if data.system_name is not None:
                cursor.execute(
                    "INSERT INTO system_config (config_key, config_value) VALUES ('system_name', %s) ON DUPLICATE KEY UPDATE config_value = %s",
                    (data.system_name, data.system_name)
                )
            if data.language is not None:
                cursor.execute(
                    "INSERT INTO system_config (config_key, config_value) VALUES ('language', %s) ON DUPLICATE KEY UPDATE config_value = %s",
                    (data.language, data.language)
                )
            if data.theme is not None:
                cursor.execute(
                    "INSERT INTO system_config (config_key, config_value) VALUES ('theme', %s) ON DUPLICATE KEY UPDATE config_value = %s",
                    (data.theme, data.theme)
                )
            connection.commit()
            return {"code": "SUCCESS", "message": "配置保存成功"}
    except Exception as e:
        connection.rollback()
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()
        
# 在 config.py 文件末尾添加以下代码

import os
import shutil
from fastapi import UploadFile, File

UPLOAD_DIR = "upload"
LOGO_DIR = os.path.join(UPLOAD_DIR, "logo")
os.makedirs(LOGO_DIR, exist_ok=True)


@router.post("/upload-logo")
async def upload_logo(request: Request, file: UploadFile = File(...)):
    """上传系统 Logo（只有管理员可以）"""
    username = request.headers.get("X-Username", "")
    
    if username != 'admin':
        return {"code": "ERROR", "detail": "只有管理员可以修改 Logo"}
    
    # 检查文件类型
    allowed_types = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml']
    if file.content_type not in allowed_types:
        return {"code": "ERROR", "detail": "只支持 PNG、JPG、SVG 格式的图片"}
    
    # 保存文件
    file_extension = file.filename.split('.')[-1]
    filename = f"logo.{file_extension}"
    file_path = os.path.join(LOGO_DIR, filename)
    
    # 删除旧 Logo
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # 保存新 Logo
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # 更新数据库中的 logo_url
    logo_url = f"/upload/logo/{filename}"
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO system_config (config_key, config_value) 
                VALUES ('logo_url', %s)
                ON DUPLICATE KEY UPDATE config_value = %s
            """, (logo_url, logo_url))
            connection.commit()
        return {"code": "SUCCESS", "message": "Logo 上传成功", "logo_url": logo_url}
    except Exception as e:
        connection.rollback()
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()        