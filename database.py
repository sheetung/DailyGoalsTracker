import os
import sqlite3
from datetime import datetime, timedelta, timezone
import json

# 数据库和图片存储路径
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = "data/plugins/DailyGoalsTracker"
DB_PATH = os.path.join(BASE_DIR, 'checkin.db')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')

# 创建UTC+8时区对象
china_tz = timezone(timedelta(hours=8))

class DatabaseManager:
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        """初始化数据库"""
        os.makedirs(IMAGES_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                checkin_time DATETIME NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checkin_id INTEGER NOT NULL,
                goal TEXT NOT NULL,
                FOREIGN KEY (checkin_id) REFERENCES checkins(id)
            )
        ''')
        conn.commit()
        conn.close()

    def checkin(self, user_id, goals):
        """打卡功能"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now(china_tz).strftime('%Y-%m-%d %H:%M:%S')
        c.execute(
            "INSERT INTO checkins (user_id, checkin_time) VALUES (?, ?)",
            (user_id, now)
        )
        checkin_id = c.lastrowid
        for goal in goals:
            c.execute(
                "INSERT INTO goals (checkin_id, goal) VALUES (?, ?)",
                (checkin_id, goal)
            )
        conn.commit()
        conn.close()
        return checkin_id

    def get_checkins(self, user_id):
        """查询打卡记录"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT * FROM checkins WHERE user_id = ?",
            (user_id,)
        )
        checkins = c.fetchall()
        conn.close()
        return checkins

    def get_goals(self, checkin_id):
        """查询打卡目标"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT goal FROM goals WHERE checkin_id = ?",
            (checkin_id,)
        )
        goals = [row[0] for row in c.fetchall()]
        conn.close()
        return goals

    def get_admin_qq(self):
        """获取表中第一位用户的 QQ 号（管理员）"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id FROM checkins ORDER BY id ASC LIMIT 1")
        result = c.fetchone()
        conn.close()
        return result[0] if result else '0'

    def clear_database(self):
        """清空数据库中的所有数据"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM checkins")
        c.execute("DELETE FROM goals")
        conn.commit()
        conn.close()

    def has_checked_in_today(self, user_id, goal):
        """查询用户当天是否已经打卡了某个目标"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        today = datetime.now(china_tz).date()
        c.execute(
            "SELECT 1 FROM checkins JOIN goals ON checkins.id = goals.checkin_id "
            "WHERE user_id = ? AND DATE(checkin_time) = ? AND goal = ?",
            (user_id, today, goal)
        )
        result = c.fetchone()
        conn.close()
        return result is not None

    def get_consecutive_days(self, user_id, goal=None):
        """计算连续打卡天数"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        query = """
            SELECT DISTINCT DATE(checkin_time) as checkin_date
            FROM checkins
            JOIN goals ON checkins.id = goals.checkin_id
            WHERE user_id = ?
        """
        params = [user_id]
        if goal:
            query += " AND goal = ?"
            params.append(goal)
        query += " ORDER BY checkin_date DESC"
        c.execute(query, tuple(params))
        dates = [row[0] for row in c.fetchall()]
        conn.close()
        
        if not dates:
            return 0
        
        date_objs = []
        today = datetime.now(china_tz).date()

        for date_str in dates:
            if ' ' in date_str:
                date_part = date_str.split(' ')[0]
            else:
                date_part = date_str
            try:
                date_obj = datetime.strptime(date_part, '%Y-%m-%d').date()
                date_objs.append(date_obj)
            except ValueError:
                continue
        
        if not date_objs:
            return 0
        
        consecutive_days = 0
        if date_objs[0] == today:
            consecutive_days = 1
            prev_date = date_objs[0]
            for date_obj in date_objs[1:]:
                if (prev_date - date_obj).days == 1:
                    consecutive_days += 1
                    prev_date = date_obj
                else:
                    break
        return consecutive_days

    def clear_old_checkins(self):
        """清理30天前的打卡记录"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        cutoff_date = (datetime.now(china_tz) - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute("DELETE FROM checkins WHERE checkin_time < ?", (cutoff_date,))
        c.execute("DELETE FROM goals WHERE checkin_id NOT IN (SELECT id FROM checkins)")
        conn.commit()
        conn.close()

    def delete_goals(self, user_id, goal):
        """删除用户特定目标的所有记录"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute(
                "DELETE FROM goals WHERE checkin_id IN (SELECT id FROM checkins WHERE user_id = ?) AND goal = ?",
                (user_id, goal)
            )
            deleted_goals = c.rowcount
            c.execute(
                "DELETE FROM checkins WHERE id NOT IN (SELECT checkin_id FROM goals)"
            )
            conn.commit()
            return deleted_goals
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def delete_all_checkins(self, user_id):
        """删除用户所有打卡记录"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("DELETE FROM checkins WHERE user_id = ?", (user_id,))
            deleted_checkins = c.rowcount
            conn.commit()
            return deleted_checkins
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def read_admin_id(self, user_id):
        """读取或创建管理员ID"""
        current_directory = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(current_directory, "admin_data.json")
        
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    admin_data = json.load(f)
                    if "admin_id" in admin_data:
                        return ["存在", admin_data["admin_id"]]
                    else:
                        admin_data["admin_id"] = user_id
                        with open(file_path, "w") as f:
                            json.dump(admin_data, f)
                        return ["不存在", user_id]
            except json.JSONDecodeError:
                admin_data = {"admin_id": user_id}
                with open(file_path, "w") as f:
                    json.dump(admin_data, f)
                return ["不存在", user_id]
        else:
            with open(file_path, "w") as f:
                return ["不存在", user_id]
    def get_recent_checkins(self, user_id, days=30):
        """获取用户近期的打卡记录（按目标分组）"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        cutoff_date = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        
        # 获取打卡记录和目标
        c.execute('''
            SELECT c.id, c.checkin_time, g.goal 
            FROM checkins c
            JOIN goals g ON c.id = g.checkin_id
            WHERE c.user_id = ? AND c.checkin_time >= ?
            ORDER BY g.goal, c.checkin_time
        ''', (user_id, cutoff_date))
        
        records = c.fetchall()
        conn.close()
        
        # 按目标分组
        goal_data = {}
        for record in records:
            checkin_id, checkin_time, goal = record
            if goal not in goal_data:
                goal_data[goal] = []
            goal_data[goal].append(checkin_time)
        
        return goal_data
