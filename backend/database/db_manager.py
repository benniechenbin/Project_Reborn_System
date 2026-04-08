import sqlite3
from pathlib import Path
from utils.logger import logger
from config.settings import settings

class DBManager:
    def __init__(self):
        # 确保数据库所在的文件夹存在
        self.db_path = Path(settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self):
        """✨ 继承旧项目的优秀基因：支持并发，支持字典式读取"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """初始化 Project Reborn 的地基：只需一张同步历史表"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # 创建专门记录“成长轨迹”的表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sync_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        audio_duration REAL,     -- 语音时长(分钟)
                        notes_count INTEGER,     -- 笔记篇数
                        word_count INTEGER       -- 知识库词汇量
                    )
                ''')
                conn.commit()
            logger.info("✅ Project Reborn 数据库地基就绪！")
        except Exception as e:
            logger.error(f"❌ 数据库初始化失败: {e}")

    def save_sync_record(self, metrics):
        """记录每一次的数据同步快照"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO sync_history (audio_duration, notes_count, word_count)
                    VALUES (?, ?, ?)
                ''', (
                    metrics.get('audio_duration', 0), 
                    metrics.get('notes_count', 0), 
                    metrics.get('word_count', 0)
                ))
                conn.commit()
            logger.info("💾 资产快照已成功写入 SQLite")
        except Exception as e:
            logger.error(f"❌ 保存同步记录失败: {e}")