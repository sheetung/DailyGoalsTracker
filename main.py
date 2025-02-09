import os
import sqlite3
from datetime import datetime, timedelta
from pkg.plugin.context import *
from pkg.plugin.events import *
from pkg.platform.types import *

# 数据库和图片存储路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'checkin.db')
IMAGES_DIR = os.path.join(BASE_DIR, 'images')

# 初始化数据库
def init_db():
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

# 打卡功能
def checkin(user_id, goals):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 不包含毫秒
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

# 查询打卡记录
def get_checkins(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT * FROM checkins WHERE user_id = ?",
        (user_id,)
    )
    checkins = c.fetchall()
    conn.close()
    return checkins

# 查询打卡目标
def get_goals(checkin_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT goal FROM goals WHERE checkin_id = ?",
        (checkin_id,)
    )
    goals = [row[0] for row in c.fetchall()]
    conn.close()
    return goals

# 查询用户当天是否已经打卡了某个目标
def has_checked_in_today(user_id, goal):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute(
        "SELECT 1 FROM checkins JOIN goals ON checkins.id = goals.checkin_id "
        "WHERE user_id = ? AND DATE(checkin_time) = ? AND goal = ?",
        (user_id, today, goal)
    )
    result = c.fetchone()
    conn.close()
    return result is not None

# 计算连续打卡天数（修正版）
def get_consecutive_days(user_id, goal=None):
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
    
    # 处理可能的日期时间格式，提取日期部分
    date_objs = []
    today = datetime.now().date()
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
    # 检查今天是否打卡
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

# 清理旧打卡记录（修正为删除30天前的记录）
def clear_old_checkins():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cutoff_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("DELETE FROM checkins WHERE checkin_time < ?", (cutoff_date,))
    c.execute("DELETE FROM goals WHERE checkin_id NOT IN (SELECT id FROM checkins)")
    conn.commit()
    conn.close()

# 删除用户特定目标的所有记录
def delete_goals(user_id, goal):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # 删除指定用户的目标记录
        c.execute(
            "DELETE FROM goals WHERE checkin_id IN (SELECT id FROM checkins WHERE user_id = ?) AND goal = ?",
            (user_id, goal)
        )
        deleted_goals = c.rowcount
        # 清理无目标的打卡记录
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

# 删除用户所有打卡记录
def delete_all_checkins(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # 删除用户所有打卡记录及相关目标
        c.execute("DELETE FROM checkins WHERE user_id = ?", (user_id,))
        deleted_checkins = c.rowcount
        conn.commit()
        return deleted_checkins
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# 插件主体
@register(name="DailyGoalsTracker", 
          description="打卡系统,实现每日目标打卡，可重复打卡不同目标，并且统计持续打卡时间，月年打卡记录等", 
          version="0.2", 
          author="sheetung")
class MyPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        pass

    async def initialize(self):
        init_db()

    @handler(GroupMessageReceived)
    async def group_normal_received(self, ctx: EventContext):
        msg = str(ctx.event.message_chain)
        user_id = ctx.event.sender_id
        group_id = ctx.event.launcher_id

        parts = msg.split(maxsplit=1)
        cmd = parts[0].strip()
        goals_str = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "打卡":
            clear_old_checkins()
            # 获取目标列表
            if not goals_str:
                # 使用上次目标
                last_checkins = get_checkins(user_id)
                if not last_checkins:
                    await ctx.reply(MessageChain([At(user_id), Plain("\n请输入打卡目标且没有历史记录！\n \
                                                                            打卡命令有：\n打卡 健身\n打卡记录\n打卡删除 健身\n打卡删除 所有")]))
                    return
                last_checkin_id = last_checkins[-1][0]
                goals = get_goals(last_checkin_id)
            else:
                goals = [g.strip() for g in goals_str.split(",") if g.strip()]

            if not goals:
                await ctx.reply(MessageChain([At(user_id), Plain(" 打卡目标不能为空！")]))
                return

            # 过滤已打卡目标
            new_goals = []
            has_duplicate = False
            for goal in goals:
                if has_checked_in_today(user_id, goal):
                    has_duplicate = True
                    await ctx.reply(MessageChain([At(user_id), Plain(f" 目标【{goal}】今日已打卡！")]))
                else:
                    new_goals.append(goal)

            if not new_goals:
                return

            # 执行打卡
            checkin_id = checkin(user_id, new_goals)
            if checkin_id:
                # 获取各目标连续天数
                details = []
                for goal in new_goals:
                    days = get_consecutive_days(user_id, goal)
                    details.append(f"【{goal}】连续打卡 {days} 天")
                
                reply_msg = "打卡成功！\n" + "\n".join(details)
                await ctx.reply(MessageChain([At(user_id), Plain(f" {reply_msg}")]))
            else:
                await ctx.reply(MessageChain([At(user_id), Plain(" 打卡失败，请稍后重试！")]))
        
        elif cmd == "打卡删除":

            if goals_str == "所有":
                # 删除用户所有打卡记录
                count = delete_all_checkins(user_id)
                reply = f"已删除所有打卡记录，共{count}次打卡"
            else:
                # 删除特定目标
                goal_to_delete = goals_str
                deleted_count = delete_goals(user_id, goal_to_delete)
                if deleted_count == 0:
                    reply = f"未找到目标【{goal_to_delete}】的打卡记录"
                else:
                    reply = f"已删除目标【{goal_to_delete}】的{deleted_count}条记录"
            
            await ctx.reply(MessageChain([At(user_id), Plain(f" {reply}")]))

        elif msg.strip() == "打卡记录":
            checkins = get_checkins(user_id)
            if not checkins:
                await ctx.reply(MessageChain([At(user_id), Plain(" 暂无打卡记录！")]))
                return

            # 统计各目标数据
            goals_data = {}
            for checkin_record in checkins:
                checkin_id = checkin_record[0]
                goals = get_goals(checkin_id)
                for goal in goals:
                    if goal not in goals_data:
                        goals_data[goal] = []
                    goals_data[goal].append(checkin_record[2])  # checkin_time

            # 生成统计信息
            report = ["打卡统计："]
            for goal, times in goals_data.items():
                total = len(times)
                consecutive = get_consecutive_days(user_id, goal)
                report.append(f"【{goal}】累计{total}天，连续{consecutive}天")

            await ctx.reply(MessageChain([At(user_id), Plain("\n".join(report))]))

# 初始化数据库
init_db()