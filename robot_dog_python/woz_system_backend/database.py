"""
简化的SQLite数据库操作模块
"""
import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging

from .config import DATABASE_PATH

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DATABASE_PATH)
        self.init_tables()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
        return conn

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """执行查询并返回结果"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """执行更新操作并返回影响的行数"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Update execution failed: {e}")
            raise

    def execute_insert(self, query: str, params: tuple = ()) -> str:
        """执行插入操作并返回最后插入的ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Insert execution failed: {e}")
            raise

    def init_tables(self):
        """初始化数据库表"""
        tables = [
            # 被试表
            """
            CREATE TABLE IF NOT EXISTS participants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # 被试图片表
            """
            CREATE TABLE IF NOT EXISTS participant_images (
                id TEXT PRIMARY KEY,
                participant_id TEXT NOT NULL,
                image_url TEXT NOT NULL,
                image_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (participant_id) REFERENCES participants (id) ON DELETE CASCADE
            )
            """,
            
            # 地图表
            """
            CREATE TABLE IF NOT EXISTS maps (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            
            # RJA目标点表
            """
            CREATE TABLE IF NOT EXISTS ja_targets (
                id TEXT PRIMARY KEY,
                map_id TEXT NOT NULL,
                name TEXT NOT NULL,
                data TEXT NOT NULL,
                sequence INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (map_id) REFERENCES maps (id) ON DELETE CASCADE
            )
            """,
            
            # 会话表
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                participant_id TEXT NOT NULL,
                map_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (participant_id) REFERENCES participants (id),
                FOREIGN KEY (map_id) REFERENCES maps (id)
            )
            """,
            
            # 指令表
            """
            CREATE TABLE IF NOT EXISTS instructions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES ja_targets (id)
            )
            """,
            
            # 提示尝试表
            """
            CREATE TABLE IF NOT EXISTS prompt_attempts (
                id TEXT PRIMARY KEY,
                instruction_id TEXT NOT NULL,
                level INTEGER NOT NULL,
                status TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (instruction_id) REFERENCES instructions (id) ON DELETE CASCADE
            )
            """,
            
            # 事件日志表
            """
            CREATE TABLE IF NOT EXISTS event_logs (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                event_name TEXT NOT NULL,
                event_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
            """
        ]
        
        try:
            with self.get_connection() as conn:
                for table_sql in tables:
                    conn.execute(table_sql)
                conn.commit()
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database tables: {e}")
            raise

    # 便捷方法
    def generate_id(self) -> str:
        """生成UUID"""
        return str(uuid.uuid4())

    def to_json(self, data: Any) -> str:
        """将数据转换为JSON字符串"""
        return json.dumps(data, ensure_ascii=False, default=str)

    def from_json(self, json_str: str) -> Any:
        """从JSON字符串解析数据"""
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return {}

    def update_timestamp(self, table: str, record_id: str):
        """更新记录的updated_at时间戳"""
        query = f"UPDATE {table} SET updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        self.execute_update(query, (record_id,))


# 全局数据库实例
db = Database()
