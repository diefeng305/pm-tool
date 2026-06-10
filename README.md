# 项目管理系统

基于 FastAPI + MySQL + 原生 HTML/CSS/JS 的项目管理系统。

## 功能特点

- 用户认证与权限管理
- 项目管理（创建、编辑、删除、搜索）
- 任务管理（发布、执行、审核）
- 里程碑管理
- 操作日志记录
- 实时事件推送
- 系统配置管理

## 技术栈

- **后端**: FastAPI (Python 3.10)
- **数据库**: MySQL 8.0
- **前端**: 原生 HTML/CSS/JS
- **容器化**: Docker & Docker Compose

## 快速启动

```bash
# 克隆项目
git clone https://github.com/您的用户名/project-management-system.git
cd project-management-system

# 启动服务
docker compose up -d

# 访问系统
http://localhost:8000
