# database.py
import os
import time
import hashlib
import hmac
import pymysql

def get_db_connection():
    """纯粹的底层数据库物理连接，不依赖 main，不依赖 auth"""
    host = os.getenv("DB_HOST", "pm-db")
    user = os.getenv("DB_USER", "pm_worker")
    password = os.getenv("DB_PASSWORD", "pm_worker_password_998")
    database = os.getenv("DB_NAME", "pm_database")
    
    retry_count = 5
    while retry_count > 0:
        try:
            conn = pymysql.connect(
                host=host,
                user=user,
                password=password,
                database=database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            return conn
        except Exception as e:
            print(f"数据库连接失败，正在重试... 错误: {str(e)}")
            time.sleep(2)
            retry_count -= 1
    raise Exception("无法连接到 MySQL 数据库")

def hash_password(password: str) -> str:
    """全局唯一的密码哈希"""
    salt = b"pm_secure_salt_2026"
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return pwd_hash.hex()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """密码强校验"""
    return hmac.compare_digest(hash_password(plain_password), hashed_password)