-- =================================================================
-- Meeting Assistant System - 达梦数据库用户表初始化脚本（对齐MySQL简化版）
-- 版本: 1.1.0
-- 创建日期: 2024-09-26
-- 描述: 与MySQL初始化脚本保持功能与结构一致，兼容达梦DM8语法
-- 注意: 外键约束和检查约束将在应用层实现
-- =================================================================

-- 事务设置
SET AUTOCOMMIT OFF;

-- =================================================================
-- 1. 用户主表 (users)
-- 对应MySQL脚本: /db/sql/mysql_user_init.sql
-- =================================================================

-- 删除已存在的表（如果存在）
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE users CASCADE CONSTRAINTS';
EXCEPTION
    WHEN OTHERS THEN
        NULL; -- 忽略表不存在的错误
END;
/

-- 创建用户表（字段与MySQL版本保持一致）
CREATE TABLE users (
    -- 主键字段（通过序列+触发器实现自增，模拟MySQL AUTO_INCREMENT）
    id            VARCHAR2(36)               NOT NULL,

    -- 基本信息字段
    name          VARCHAR2(100)      NOT NULL,
    user_name     VARCHAR2(50)       NOT NULL,
    gender        VARCHAR2(20)       DEFAULT NULL,
    phone         VARCHAR2(20)       DEFAULT NULL,
    email         VARCHAR2(255)      NOT NULL,
    company       VARCHAR2(200)      DEFAULT NULL,

    -- 权限和状态字段
    user_role     VARCHAR2(36)       DEFAULT 'user'      NOT NULL,
    status        VARCHAR2(20)       DEFAULT 'active'    NOT NULL,

    -- 安全信息字段
    password_hash VARCHAR2(255)      DEFAULT NULL,

    -- 时间戳字段
    created_at    TIMESTAMP          DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at    TIMESTAMP          DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- 关联字段
    created_by    VARCHAR2(36)       DEFAULT NULL,
    updated_by    VARCHAR2(36)       DEFAULT NULL,

    -- 主键约束
    CONSTRAINT pk_users PRIMARY KEY (id),

    -- 唯一键约束（与MySQL保持一致，仅user_name唯一）
    CONSTRAINT uk_users_user_name UNIQUE (user_name)
);

-- 添加表和字段注释
COMMENT ON TABLE users IS '用户信息表';
COMMENT ON COLUMN users.id IS '用户ID主键（自增）';
COMMENT ON COLUMN users.name IS '用户姓名';
COMMENT ON COLUMN users.user_name IS '用户账号';
COMMENT ON COLUMN users.gender IS '性别：male-男性，female-女性，other-其他';
COMMENT ON COLUMN users.phone IS '手机号码';
COMMENT ON COLUMN users.email IS '邮箱地址';
COMMENT ON COLUMN users.company IS '所属单位名称';
COMMENT ON COLUMN users.user_role IS '用户角色：admin-管理员，user-普通用户';
COMMENT ON COLUMN users.status IS '用户状态：active-激活，inactive-未激活，suspended-暂停';
COMMENT ON COLUMN users.password_hash IS '密码哈希值（bcrypt加密）';
COMMENT ON COLUMN users.created_at IS '创建时间';
COMMENT ON COLUMN users.updated_at IS '更新时间';
COMMENT ON COLUMN users.created_by IS '创建者用户ID';
COMMENT ON COLUMN users.updated_by IS '更新者用户ID';

-- 普通索引（与MySQL版本保持一致）
CREATE INDEX idx_users_email       ON users(email);
CREATE INDEX idx_users_phone       ON users(phone);
CREATE INDEX idx_users_user_name   ON users(user_name);
CREATE INDEX idx_users_role        ON users(user_role);
CREATE INDEX idx_users_status      ON users(status);
CREATE INDEX idx_users_company     ON users(company);
CREATE INDEX idx_users_created_at  ON users(created_at);
CREATE INDEX idx_users_created_by  ON users(created_by);
CREATE INDEX idx_users_updated_by  ON users(updated_by);

/                                                                   

-- 自动更新时间触发器（模拟MySQL ON UPDATE CURRENT_TIMESTAMP）
CREATE OR REPLACE TRIGGER tr_users_before_update
    BEFORE UPDATE ON users
    FOR EACH ROW
BEGIN
    :NEW.updated_at := CURRENT_TIMESTAMP;
END;
/

-- =================================================================
-- 2. 更新现有meetings表，添加用户关联字段（与MySQL保持一致）
-- =================================================================
DECLARE
    v_count NUMBER;
    v_col_count NUMBER;
BEGIN
    -- 检查meetings表是否存在
    SELECT COUNT(*) INTO v_count
    FROM USER_TABLES
    WHERE TABLE_NAME = UPPER('meetings');

    IF v_count > 0 THEN
        -- 检查created_by字段是否存在
        SELECT COUNT(*) INTO v_col_count
        FROM USER_TAB_COLUMNS
        WHERE TABLE_NAME = UPPER('meetings')
          AND COLUMN_NAME = UPPER('created_by');

        -- 如果字段不存在则添加
        IF v_col_count = 0 THEN
            EXECUTE IMMEDIATE 'ALTER TABLE meetings ADD (
                created_by NUMBER(19) DEFAULT NULL,
                updated_by NUMBER(19) DEFAULT NULL
            )';

            -- 添加字段注释
            EXECUTE IMMEDIATE 'COMMENT ON COLUMN meetings.created_by IS ''创建者用户ID''';
            EXECUTE IMMEDIATE 'COMMENT ON COLUMN meetings.updated_by IS ''更新者用户ID''';

            -- 添加索引
            EXECUTE IMMEDIATE 'CREATE INDEX idx_meetings_created_by ON meetings(created_by)';
            EXECUTE IMMEDIATE 'CREATE INDEX idx_meetings_updated_by ON meetings(updated_by)';
        END IF;
    END IF;
END;
/

-- =================================================================
-- 4. 插入初始用户数据（如不存在则插入）
-- =================================================================

-- 插入系统管理员（如果不存在）
INSERT INTO users (
    name,
    user_name,
    email,
    user_role,
    status,
    password_hash,
    created_at,
    updated_at
)
SELECT
    '系统管理员',
    'admin',
    'admin@meeting-system.com',
    'admin',
    'active',
    '$2b$12$FeZo7nHnCkI9UhlSZgtyoOKAtIoScX5dAwT6n4EqxItVtG.XdfB6a', -- 默认密码: Admin123456
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM dual
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE user_name = 'admin'
);

-- 插入测试普通用户（如果不存在）
INSERT INTO users (
    name,
    user_name,
    email,
    gender,
    phone,
    company,
    user_role,
    status,
    password_hash,
    created_by,
    created_at,
    updated_at
)
SELECT
    '测试用户',
    'demo_user',
    'demo@meeting-system.com',
    'other',
    '13800138000',
    '示例科技有限公司',
    'user',
    'active',
    '$2b$12$dqxaCN4B14D9jOolnaI1rujOK.ho/g4lLtSqZ4VKSjyJy7lgxT6F6', -- 默认密码: 123456
    (SELECT id FROM users WHERE user_name = 'admin'),
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM dual
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE user_name = 'demo_user'
);

-- 事务提交
COMMIT;

-- =================================================================
-- 初始化完成提示与统计（与MySQL一致）
-- =================================================================
SELECT
    '达梦数据库用户表初始化完成！' AS "消息",
    (SELECT COUNT(*) FROM users) AS "用户表记录数",
    (SELECT COUNT(*) FROM users WHERE user_role = 'admin') AS "管理员数量",
    (SELECT COUNT(*) FROM users WHERE status = 'active') AS "活跃用户数"
FROM dual;

-- 显示用户列表
SELECT
    id,
    name,
    email,
    user_role,
    status,
    created_at
FROM users
ORDER BY created_at DESC;
