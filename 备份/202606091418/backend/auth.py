# auth.py
import time
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from database import get_db_connection, verify_password, hash_password

router = APIRouter(
    prefix="/api",
    tags=["用户及权限管理模块"]
)

class LoginRequest(BaseModel):
    username: str
    password: str

class PasswordChangeRequest(BaseModel):
    username: str
    old_password: str
    new_password: str

class UserCreateRequest(BaseModel):
    username: str
    password: str
    name: Optional[str] = ""
    gender: Optional[str] = "保密"
    user_type: Optional[str] = "user"
    position: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""

class UserUpdateRequest(BaseModel):
    password: Optional[str] = None
    name: Optional[str] = ""
    gender: Optional[str] = "保密"
    position: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    permissions: Optional[List[str]] = []

class PermissionUpdateRequest(BaseModel):
    permissions: List[str]

# 权限定义
PERMISSIONS = {
    "create_project": {"name": "创建项目", "description": "新建项目和编辑项目信息"},
    "delete_project": {"name": "删除项目", "description": "删除项目（谨慎操作）"},
    "create_task": {"name": "创建任务", "description": "发布和指派任务"},
    "delete_task": {"name": "删除任务", "description": "删除任务（谨慎操作）"},
    "audit_flow": {"name": "流程审批", "description": "审核任务完成和退回"},
    "manage_users": {"name": "用户管理", "description": "添加、编辑、删除用户账号"},
    "view_all_projects": {"name": "查看所有项目", "description": "查看系统中所有项目"},
    "system_settings": {"name": "系统设置", "description": "修改系统配置参数"}
}


def get_user_permissions(cursor, username: str) -> List[str]:
    """获取用户权限列表"""
    try:
        cursor.execute("""
            SELECT permissions FROM user_permissions WHERE username = %s
        """, (username,))
        row = cursor.fetchone()
        if row and row['permissions']:
            try:
                perms = json.loads(row['permissions'])
                print(f"📖 读取用户 {username} 权限: {perms}")
                return perms
            except Exception as e:
                print(f"解析权限失败: {e}")
                return []
        else:
            print(f"⚠️ 用户 {username} 没有权限记录")
            return []
    except Exception as e:
        print(f"获取用户权限失败: {e}")
        return []


def set_user_permissions(cursor, username: str, permissions: List[str]):
    """设置用户权限"""
    try:
        perms_json = json.dumps(permissions)
        print(f"💾 保存用户 {username} 权限: {permissions}")
        cursor.execute("""
            INSERT INTO user_permissions (username, permissions) 
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE permissions = %s
        """, (username, perms_json, perms_json))
    except Exception as e:
        print(f"设置用户权限失败: {e}")


def init_permissions_table():
    """初始化权限表"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # 创建权限表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    permissions TEXT DEFAULT '[]',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX (username)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # 为所有现有用户初始化权限记录
            cursor.execute("SELECT username, user_type FROM users")
            users = cursor.fetchall()
            for user in users:
                cursor.execute("SELECT id FROM user_permissions WHERE username = %s", (user['username'],))
                if not cursor.fetchone():
                    if user['user_type'] == 'admin':
                        default_perms = list(PERMISSIONS.keys())
                    else:
                        default_perms = ["create_project", "create_task"]
                    cursor.execute("""
                        INSERT INTO user_permissions (username, permissions) VALUES (%s, %s)
                    """, (user['username'], json.dumps(default_perms)))
                    print(f"✅ 为用户 {user['username']} 初始化权限: {default_perms}")
            
            connection.commit()
            print("✅ 权限表初始化完成")
    except Exception as e:
        print(f"⚠️ 权限表初始化失败: {e}")
    finally:
        connection.close()


# 在模块加载时初始化权限表
init_permissions_table()


@router.post("/auth/login")
def api_login(data: LoginRequest):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s", (data.username,))
            user = cursor.fetchone()
            if not user:
                return {"code": "ERROR", "detail": "账户不存在，请联系管理员建立"}
            
            if user["is_active"] != 1:
                return {"code": "ERROR", "detail": "该账户已被全局停用，拒绝登录访问"}
                
            if not verify_password(data.password, user["password_hash"]):
                return {"code": "ERROR", "detail": "登录密码校验失败，请重新输入"}
            
            permissions = get_user_permissions(cursor, user["username"])
            
            return {
                "code": "SUCCESS",
                "message": "登录成功认证",
                "token": f"mock_token_{user['username']}_{int(time.time())}",
                "username": user["username"],
                "name": user["name"] or user["username"],
                "role": user["user_type"],
                "position": user["position"] or "未定岗",
                "email": user["email"] or "",
                "phone": user["phone"] or "",
                "permissions": permissions
            }
    except Exception as e:
        return {"code": "ERROR", "detail": f"服务器内部数据库查询错误: {str(e)}"}
    finally:
        connection.close()


@router.get("/users/list")
def get_users_list():
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT u.username, u.name, u.gender, u.user_type, u.position, u.email, u.phone, u.is_active
                FROM users u
                ORDER BY u.id ASC
            """)
            users = cursor.fetchall()
            
            result = []
            for user in users:
                # 每次都从数据库实时读取权限
                perms = get_user_permissions(cursor, user['username'])
                
                # 如果没有权限记录，创建默认权限
                if not perms:
                    if user['user_type'] == 'admin':
                        perms = list(PERMISSIONS.keys())
                    else:
                        perms = ["create_project", "create_task"]
                    set_user_permissions(cursor, user['username'], perms)
                
                user_dict = dict(user)
                user_dict['permissions'] = perms
                result.append(user_dict)
                print(f"📋 返回用户 {user['username']} 权限: {perms}")
            
            return {"code": "SUCCESS", "data": result}
    except Exception as e:
        print(f"获取用户列表失败: {e}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.post("/users/add")
def add_user(data: UserCreateRequest):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (data.username,))
            if cursor.fetchone():
                return {"code": "ERROR", "detail": "该账户登录名已被占用"}
            
            pwd_hash = hash_password(data.password)
            
            sql = """
                INSERT INTO users (username, password_hash, name, gender, user_type, position, email, phone, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
            """
            cursor.execute(sql, (
                data.username, pwd_hash, data.name, data.gender, 
                data.user_type, data.position, data.email, data.phone
            ))
            
            if data.user_type == "admin":
                default_perms = list(PERMISSIONS.keys())
            else:
                default_perms = ["create_project", "create_task"]
            set_user_permissions(cursor, data.username, default_perms)
            
            connection.commit()
            return {"code": "SUCCESS", "message": "新成员账户建立成功"}
    except Exception as e:
        connection.rollback()
        print(f"添加用户失败: {e}")
        return {"code": "ERROR", "detail": f"服务器内部数据库写入失败: {str(e)}"}
    finally:
        connection.close()


@router.put("/users/update/{username}")
def update_user(username: str, data: UserUpdateRequest):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, user_type FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if not user:
                return {"code": "ERROR", "detail": "用户不存在"}
            
            update_fields = []
            params = []
            
            if data.name is not None:
                update_fields.append("name = %s")
                params.append(data.name)
            if data.gender is not None:
                update_fields.append("gender = %s")
                params.append(data.gender)
            if data.position is not None:
                update_fields.append("position = %s")
                params.append(data.position)
            if data.email is not None:
                update_fields.append("email = %s")
                params.append(data.email)
            if data.phone is not None:
                update_fields.append("phone = %s")
                params.append(data.phone)
            if data.password and data.password.strip():
                pwd_hash = hash_password(data.password)
                update_fields.append("password_hash = %s")
                params.append(pwd_hash)
            
            if update_fields:
                sql = f"UPDATE users SET {', '.join(update_fields)} WHERE username = %s"
                params.append(username)
                cursor.execute(sql, params)
            
            connection.commit()
            return {"code": "SUCCESS", "message": "用户信息更新成功"}
    except Exception as e:
        connection.rollback()
        print(f"更新用户失败: {e}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.delete("/users/delete/{username}")
def delete_user(username: str):
    if username == "admin":
        return {"code": "ERROR", "detail": "不能删除系统管理员账户"}
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE username = %s", (username,))
            cursor.execute("DELETE FROM user_permissions WHERE username = %s", (username,))
            connection.commit()
            return {"code": "SUCCESS", "message": "用户已删除"}
    except Exception as e:
        connection.rollback()
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.post("/users/toggle-status/{username}")
def toggle_user_status(username: str):
    if username == "admin":
        return {"code": "ERROR", "detail": "不能停用系统管理员账户"}
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT is_active FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if not user:
                return {"code": "ERROR", "detail": "用户不存在"}
            
            new_status = 0 if user['is_active'] == 1 else 1
            cursor.execute("UPDATE users SET is_active = %s WHERE username = %s", (new_status, username))
            connection.commit()
            return {"code": "SUCCESS", "message": "状态已更新", "is_active": new_status}
    except Exception as e:
        connection.rollback()
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.get("/users/permissions/{username}")
def get_user_permissions_api(username: str):
    """获取用户权限列表"""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            permissions = get_user_permissions(cursor, username)
            return {"code": "SUCCESS", "data": permissions, "all_permissions": PERMISSIONS}
    except Exception as e:
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.put("/users/permissions/{username}")
def update_user_permissions(username: str, data: PermissionUpdateRequest):
    """更新用户权限"""
    if username == "admin":
        return {"code": "ERROR", "detail": "系统管理员自动拥有全部权限，无需单独配置"}
    
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if not cursor.fetchone():
                return {"code": "ERROR", "detail": "用户不存在"}
            
            # 直接更新权限表
            perms_json = json.dumps(data.permissions)
            cursor.execute("""
                INSERT INTO user_permissions (username, permissions) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE permissions = %s
            """, (username, perms_json, perms_json))
            connection.commit()
            
            print(f"✅ 权限更新成功: {username} -> {data.permissions}")
            return {"code": "SUCCESS", "message": "权限更新成功", "permissions": data.permissions}
    except Exception as e:
        connection.rollback()
        print(f"权限更新失败: {e}")
        return {"code": "ERROR", "detail": str(e)}
    finally:
        connection.close()


@router.get("/users/permissions/list")
def get_all_permissions():
    """获取所有可用权限定义"""
    return {"code": "SUCCESS", "data": PERMISSIONS}