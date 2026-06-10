-- 创建数据库
CREATE DATABASE IF NOT EXISTS pm_database CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE pm_database;

-- 1. 用户主表
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `name` VARCHAR(50) DEFAULT NULL,
    `gender` VARCHAR(10) DEFAULT '保密',
    `user_type` VARCHAR(20) DEFAULT 'user',
    `position` VARCHAR(100) DEFAULT NULL,
    `email` VARCHAR(100) DEFAULT NULL,
    `phone` VARCHAR(50) DEFAULT NULL,
    `is_active` TINYINT DEFAULT 1,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 用户权限表
CREATE TABLE IF NOT EXISTS `user_permissions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(50) NOT NULL UNIQUE,
    `permissions` TEXT DEFAULT '[]',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 项目主表
CREATE TABLE IF NOT EXISTS `projects` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `code` VARCHAR(50) NOT NULL UNIQUE,
    `name` VARCHAR(100) NOT NULL,
    `description` TEXT,
    `status` VARCHAR(20) DEFAULT '未启动',
    `category` VARCHAR(50) DEFAULT NULL,
    `priority` VARCHAR(20) DEFAULT '中',
    `tags` TEXT DEFAULT NULL,
    `shipping_date` DATE DEFAULT NULL,
    `auto_start` TINYINT DEFAULT 0,
    `image_url` VARCHAR(500) DEFAULT NULL,
    `completed_date` DATE DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 任务表
CREATE TABLE IF NOT EXISTS `tasks` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `project_code` VARCHAR(50) NOT NULL,
    `milestone_key` VARCHAR(50) DEFAULT NULL,
    `title` VARCHAR(200) NOT NULL,
    `description` TEXT,
    `assignee` VARCHAR(50) DEFAULT NULL,
    `status` ENUM('pending', 'in_progress', 'completed', 'delayed') DEFAULT 'pending',
    `priority` ENUM('low', 'medium', 'high') DEFAULT 'medium',
    `due_date` DATE DEFAULT NULL,
    `completed_at` TIMESTAMP NULL,
    `feedback` TEXT DEFAULT NULL,
    `feedback_files` TEXT DEFAULT NULL,
    `completed_by` VARCHAR(50) DEFAULT NULL,
    `review_feedback` TEXT DEFAULT NULL,
    `current_review_status` VARCHAR(20) DEFAULT 'pending',
    `reviewer` VARCHAR(50) DEFAULT NULL,
    `reviewed_at` TIMESTAMP NULL,
    `reviewers` TEXT DEFAULT NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (`project_code`),
    INDEX (`assignee`),
    FOREIGN KEY (`project_code`) REFERENCES `projects`(`code`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. 操作日志表
CREATE TABLE IF NOT EXISTS `operation_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `operator` VARCHAR(50) NOT NULL,
    `action` VARCHAR(50) NOT NULL,
    `target_type` VARCHAR(20) NOT NULL,
    `target_name` VARCHAR(200) NOT NULL,
    `details` TEXT,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (`operator`),
    INDEX (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. 项目序号表
CREATE TABLE IF NOT EXISTS `project_sequence` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `seq` INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. 项目需求表
CREATE TABLE IF NOT EXISTS `project_requirements` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `project_code` VARCHAR(50) NOT NULL,
    `requirement` TEXT NOT NULL,
    `is_original` TINYINT DEFAULT 0,
    `added_by` VARCHAR(50) NOT NULL,
    `added_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (`project_code`),
    FOREIGN KEY (`project_code`) REFERENCES `projects`(`code`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. 里程碑定义表
CREATE TABLE IF NOT EXISTS `milestone_definitions` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `phase` VARCHAR(20) NOT NULL,
    `milestone_key` VARCHAR(50) NOT NULL UNIQUE,
    `milestone_name` VARCHAR(100) NOT NULL,
    `sort_order` INT DEFAULT 0,
    INDEX (`phase`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9. 项目里程碑状态表
CREATE TABLE IF NOT EXISTS `project_milestones` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `project_code` VARCHAR(50) NOT NULL,
    `milestone_key` VARCHAR(50) NOT NULL,
    `status` ENUM('not_started', 'task_published', 'in_progress', 'completed') DEFAULT 'not_started',
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_project_milestone` (`project_code`, `milestone_key`),
    INDEX (`project_code`),
    FOREIGN KEY (`project_code`) REFERENCES `projects`(`code`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 10. 系统配置表
CREATE TABLE IF NOT EXISTS `system_config` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `config_key` VARCHAR(50) NOT NULL UNIQUE,
    `config_value` TEXT,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ========== 初始化默认数据 ==========

-- 插入默认里程碑定义
INSERT IGNORE INTO `milestone_definitions` (`phase`, `milestone_key`, `milestone_name`, `sort_order`) VALUES
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
('后期', 'archive', '资料归档', 12);

-- 插入管理员账户（密码: admin123）
INSERT IGNORE INTO `users` (`username`, `password_hash`, `name`, `user_type`, `position`, `email`, `is_active`) 
VALUES ('admin', '83c2c6a9b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3', '核心管理员', 'admin', '系统总监', 'admin@renbin.ren', 1);

-- 插入管理员权限（所有权限）
INSERT IGNORE INTO `user_permissions` (`username`, `permissions`) 
VALUES ('admin', '["create_project","delete_project","create_task","delete_task","audit_flow","manage_users","view_all_projects","system_settings"]');

-- 插入默认系统配置
INSERT IGNORE INTO `system_config` (`config_key`, `config_value`) VALUES
('logo_text', '📦 PM_SYSTEM'),
('system_name', '项目管理系统'),
('language', 'zh'),
('theme', 'light');

-- 初始化项目序号
INSERT IGNORE INTO `project_sequence` (`seq`) VALUES (0);