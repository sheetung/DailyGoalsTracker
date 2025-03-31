import os
import sqlite3
from datetime import datetime, timedelta, timezone
import json

# 数据库和图片存储路径
BASE_DIR = "data/plugins/DailyGoalsTracker"
DB_PATH = os.path.join(BASE_DIR, 'checkin.db')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')

# 创建UTC+8时区对象
china_tz = timezone(timedelta(hours=8))

class DatabaseManager:
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        """初始化数据库（新版结构）"""
        os.makedirs(IMAGES_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 创建目标表（新增UNIQUE约束）
        c.execute('''
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                goal TEXT NOT NULL,
                UNIQUE(user_id, goal)
            )
        ''')
        
        # 创建打卡记录表（新增goal_id外键）
        c.execute('''
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                checkin_time DATETIME NOT NULL,
                goal_id INTEGER NOT NULL,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def checkin(self, user_id, goals):
        """打卡功能（支持多目标）"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.now(china_tz).strftime('%Y-%m-%d %H:%M:%S')
        checkin_ids = []
        
        try:
            for goal in goals:
                # 获取或创建目标
                c.execute('''
                    INSERT OR IGNORE INTO goals (user_id, goal)
                    VALUES (?, ?)
                ''', (user_id, goal))
                
                # 获取目标ID
                c.execute('''
                    SELECT id FROM goals 
                    WHERE user_id = ? AND goal = ?
                ''', (user_id, goal))
                goal_id = c.fetchone()[0]
                
                # 插入打卡记录
                c.execute('''
                    INSERT INTO checkins (user_id, checkin_time, goal_id)
                    VALUES (?, ?, ?)
                ''', (user_id, now, goal_id))
                checkin_ids.append(c.lastrowid)
            
            conn.commit()
            return checkin_ids
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_checkins(self, user_id):
        """查询用户所有打卡记录"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT c.id, c.user_id, c.checkin_time, g.goal
            FROM checkins c
            JOIN goals g ON c.goal_id = g.id
            WHERE c.user_id = ?
        ''', (user_id,))
        checkins = c.fetchall()
        conn.close()
        return checkins

    def get_goals(self, checkin_id):
        """通过打卡记录获取目标"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT g.goal 
            FROM checkins c
            JOIN goals g ON c.goal_id = g.id
            WHERE c.id = ?
        ''', (checkin_id,))
        goals = [row[0] for row in c.fetchall()]
        conn.close()
        return goals

    def get_admin_qq(self):
        """获取管理员QQ（基于最早打卡记录）"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            SELECT user_id FROM checkins 
            ORDER BY checkin_time ASC 
            LIMIT 1
        ''')
        result = c.fetchone()
        conn.close()
        return result[0] if result else '0'

    def clear_database(self):
        """清空数据库（保持表结构）"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM checkins")
        c.execute("DELETE FROM goals")
        conn.commit()
        conn.close()

    def has_checked_in_today(self, user_id, goal):
        """检查当日目标打卡状态"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        today = datetime.now(china_tz).strftime('%Y-%m-%d')
        
        c.execute('''
            SELECT 1 FROM checkins c
            JOIN goals g ON c.goal_id = g.id
            WHERE c.user_id = ? 
            AND g.goal = ?
            AND DATE(c.checkin_time) = ?
            LIMIT 1
        ''', (user_id, goal, today))
        
        result = c.fetchone()
        conn.close()
        return result is not None

    def get_consecutive_days(self, user_id, goal=None):
        """计算连续打卡天数"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        query = '''
            SELECT DISTINCT DATE(c.checkin_time) as date
            FROM checkins c
            JOIN goals g ON c.goal_id = g.id
            WHERE c.user_id = ?
        '''
        params = [user_id]
        
        if goal:
            query += " AND g.goal = ?"
            params.append(goal)
        
        query += " ORDER BY date DESC"
        
        c.execute(query, params)
        dates = [row[0] for row in c.fetchall()]
        conn.close()
        
        # 后续计算逻辑保持不变...
        # [原有日期处理逻辑，此处省略]
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
        """清理30天前记录（级联删除）"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        cutoff = (datetime.now(china_tz) - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        
        # 先删除旧打卡记录
        c.execute('''
            DELETE FROM checkins 
            WHERE checkin_time < ?
        ''', (cutoff,))
        
        # 清理孤立目标
        c.execute('''
            DELETE FROM goals 
            WHERE id NOT IN (
                SELECT DISTINCT goal_id FROM checkins
            )
        ''')
        
        conn.commit()
        conn.close()

    def delete_goals(self, user_id, goal):
        """删除用户特定目标及相关记录"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        try:
            # 获取目标ID
            c.execute('''
                SELECT id FROM goals 
                WHERE user_id = ? AND goal = ?
            ''', (user_id, goal))
            goal_ids = [row[0] for row in c.fetchall()]
            
            if not goal_ids:
                return 0
                
            # 删除相关打卡记录
            c.execute('''
                DELETE FROM checkins 
                WHERE goal_id IN ({})
            '''.format(','.join('?'*len(goal_ids))), goal_ids)
            
            # 删除目标
            c.execute('''
                DELETE FROM goals 
                WHERE id IN ({})
            '''.format(','.join('?'*len(goal_ids))), goal_ids)
            
            conn.commit()
            return c.rowcount
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # 以下方法保持不变...
    # [保持原有 delete_all_checkins, read_admin_id, 
    #  get_recent_checkins, backup_database 等方法实现]
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
    
    def backup_database(self, backup_dir=BASE_DIR, max_backups=3):
        """备份数据库文件
        
        Args:
            backup_dir (str): 备份存储目录（相对路径）
            max_backups (int): 最大保留备份数量
        
        Returns:
            tuple: (备份是否成功, 备份文件路径或错误信息)
        """
        try:
            # 确保数据库文件存在
            if not os.path.exists(DB_PATH):
                return False, "数据库文件不存在"
            
            # 创建备份目录（如果不存在）
            abs_backup_dir = os.path.join(BASE_DIR, backup_dir)
            os.makedirs(abs_backup_dir, exist_ok=True)
            
            # 生成备份文件名（带时间戳）
            timestamp = datetime.now(china_tz).strftime("%Y%m%d_%H%M%S")
            backup_name = f"checkin_backup_{timestamp}.db"
            backup_path = os.path.join(abs_backup_dir, backup_name)
            
            # 执行备份（文件复制）
            with open(DB_PATH, 'rb') as src, open(backup_path, 'wb') as dst:
                dst.write(src.read())
            
            # 清理旧备份（按时间倒序保留最新的）
            backups = sorted(
                [f for f in os.listdir(abs_backup_dir) if f.startswith("checkin_backup")],
                key=lambda x: os.path.getmtime(os.path.join(abs_backup_dir, x)),
                reverse=True
            )
            
            for old_backup in backups[max_backups:]:
                try:
                    os.remove(os.path.join(abs_backup_dir, old_backup))
                except Exception as e:
                    self.log_error(f"删除旧备份失败: {old_backup} - {str(e)}")
            
            # 验证备份文件
            if os.path.exists(backup_path) and os.path.getsize(backup_path) > 0:
                return True, backup_path
            return False, "备份文件验证失败"
        
        except Exception as e:
            error_msg = f"数据库备份失败: {str(e)}"
            self.log_error(error_msg)
            return False, error_msg

    def log_error(self, message):
        """记录错误日志"""
        error_log_path = os.path.join(BASE_DIR, "error.log")
        timestamp = datetime.now(china_tz).strftime("%Y-%m-%d %H:%M:%S")
        with open(error_log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")

    # 在DatabaseManager类中添加以下方法
    def supplement_checkin(self, user_id, goal, checkin_date):
        """补打卡功能（纯标准库实现）"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        try:
            # 时区定义（中国时区 UTC+8）
            china_tz = timezone(timedelta(hours=8))
            
            # 支持的日期格式（增强兼容性）
            time_formats = [
                '%Y-%m-%d %H:%M',    # 标准格式
                '%Y-%m-%d',           # 仅日期
                '%Y-%m-%d %H:%M:%S',  # 带秒数
                '%Y/%m/%d %H:%M',     # 斜线分隔
                '%Y.%m.%d %H:%M',    # 点分隔
                '%Y-%m-%dT%H:%M',     # ISO格式
                '%Y%m%d %H%M'        # 紧凑格式
            ]
            # 预处理输入（统一分隔符）
            processed_date = checkin_date.replace('/', '-').replace('.', '-').replace('T', ' ')
            
            # 尝试解析日期
            checkin_time = None
            for fmt in time_formats:
                try:
                    checkin_time = datetime.strptime(processed_date, fmt)
                    break
                except ValueError:
                    continue
            # 处理纯数字格式（如20230317）
            if not checkin_time and len(processed_date) >= 8:
                try:
                    if ' ' in processed_date:
                        date_part, time_part = processed_date.split(' ', 1)
                        checkin_time = datetime.strptime(date_part, '%Y%m%d')
                        checkin_time = checkin_time.replace(
                            hour=int(time_part[:2]),
                            minute=int(time_part[2:4])
                        )
                    else:
                        checkin_time = datetime.strptime(processed_date, '%Y%m%d')
                except:
                    pass
            # 添加默认时间
            if checkin_time:
                if checkin_time.hour == 0 and checkin_time.minute == 0:
                    checkin_time = checkin_time.replace(hour=12)
            else:
                raise ValueError(
                    f"日期格式错误，支持格式示例：\n"
                    f"2025-03-17\n2025/3/17 12:00\n2025.12.31 23:59"
                )
            # 转换为中国时区（aware时间）
            checkin_time = checkin_time.replace(tzinfo=china_tz)
            
            # 获取当前时间（带时区）
            now = datetime.now(china_tz)
            
            # 未来时间检查
            if checkin_time > now:
                raise ValueError("不能补未来的打卡记录")
            
            # 转换为数据库存储格式（UTC时间）
            db_time = checkin_time.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            
            # 处理目标表
            c.execute('''
                INSERT OR IGNORE INTO goals (user_id, goal)
                VALUES (?, ?)
            ''', (user_id, goal))
            
            # 获取目标ID
            c.execute('''
                SELECT id FROM goals 
                WHERE user_id = ? AND goal = ?
            ''', (user_id, goal))
            goal_id = c.fetchone()[0]
            
            # 检查重复记录（按UTC日期比较）
            c.execute('''
                SELECT 1 FROM checkins 
                WHERE user_id = ? 
                AND goal_id = ?
                AND DATE(checkin_time) = DATE(?, 'utc')
            ''', (user_id, goal_id, db_time))
            
            if c.fetchone():
                raise ValueError("该日期已存在此目标的打卡记录")
            
            # 插入记录
            c.execute('''
                INSERT INTO checkins (user_id, checkin_time, goal_id)
                VALUES (?, ?, ?)
            ''', (user_id, db_time, goal_id))
            
            conn.commit()
            return c.lastrowid
        
        except sqlite3.Error as e:
            conn.rollback()
            raise ValueError(f"数据库错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"日期处理失败: {str(e)}")
        finally:
            conn.close()