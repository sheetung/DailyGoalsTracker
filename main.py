import os
import sqlite3
from datetime import datetime, timedelta
from pkg.plugin.context import *
from pkg.plugin.events import *
from pkg.platform.types import *
import time
import asyncio
import json

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

# 获取管理员
def get_admin_qq():
    """
    获取表中第一位用户的 QQ 号（管理员）。
    :return: 管理员的 QQ 号，如果表为空则返回 None。
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM checkins ORDER BY id ASC LIMIT 1")
    result = c.fetchone()
    conn.close()
    if result:
        return result[0]  # 返回第一位用户的 QQ 号
    else:
        return '0'  # 如果表为空，则返回 None

# 清空数据库，谨慎操作
def clear_database():
    """
    清空数据库中的所有数据。
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 删除 checkins 表中的所有记录
    c.execute("DELETE FROM checkins")
    
    # 删除 goals 表中的所有记录
    c.execute("DELETE FROM goals")
    
    conn.commit()
    conn.close()


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

def read_admin_id(user_id):
    """
    读取管理员 ID，如果文件或管理员不存在，则创建文件并将当前用户设置为管理员。
    
    Args:
        user_id (int): 当前用户的 ID。
    
    Returns:
        list: 返回一个列表，包含状态和管理员 ID。
             状态为 "存在" 或 "不存在"，管理员 ID 为整数。
    """
    # 获取当前脚本所在的文件夹路径
    current_directory = os.path.dirname(os.path.abspath(__file__))
    # 拼接文件路径
    file_path = os.path.join(current_directory, "admin_data.json")
    
    # 检查文件是否存在
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                admin_data = json.load(f)  # 读取文件内容
                if "admin_id" in admin_data:  # 检查是否已存在管理员
                    return ["存在", admin_data["admin_id"]]  # 返回状态和管理员 ID
                else:
                    # 如果文件中没有管理员 ID，则写入当前用户 ID
                    admin_data["admin_id"] = user_id
                    with open(file_path, "w") as f:
                        json.dump(admin_data, f)  # 写入文件
                    return ["不存在", user_id]
        except json.JSONDecodeError:
            # 如果文件内容不是合法的 JSON，则重新创建文件
            admin_data = {"admin_id": user_id}
            with open(file_path, "w") as f:
                json.dump(admin_data, f)
            return ["不存在", user_id]
    else:
        # 如果文件不存在，则创建文件不写入
        with open(file_path, "w") as f:
            return ["不存在", user_id]


# 插件主体
@register(name="DailyGoalsTracker", 
          description="打卡系统,实现每日目标打卡，可重复打卡不同目标，并且统计持续打卡时间，月年打卡记录等", 
          version="0.7", 
          author="sheetung")
class MyPlugin(BasePlugin):

    def __init__(self, host: APIHost):
        self.adminInit = False # 是否进入打卡管理命令标志
        self.start_time = 0 # 退出记录时间
        self.timeout_task = None  # 用于存储异步任务

    async def handle_timeout(self, ctx):
        """处理超时的异步任务"""
        try:
            await asyncio.sleep(7)  # 等待5秒
            if self.adminInit:  # 如果仍处于管理模式
                self.adminInit = False
                self.start_time = 0
                # 发送超时提示
                await ctx.send_message(
                    ctx.event.launcher_type,
                    str(ctx.event.launcher_id),
                    MessageChain([Plain(" 操作超时，已退出管理模式。")])
                )
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
        finally:
            self.timeout_task = None

    async def initialize(self):
        init_db()

    @handler(PersonMessageReceived)
    @handler(GroupMessageReceived)
    async def group_normal_received(self, ctx: EventContext):
        msg = str(ctx.event.message_chain)
        user_id = ctx.event.sender_id
        group_id = ctx.event.launcher_id

        parts = msg.split(maxsplit=2)
        cmd = parts[0].strip()
        parts1 = parts[1].strip() if len(parts) > 1 else ""
        parts2 = parts[2].strip() if len(parts) > 2 else ""

        # 处理 cmd，如果包含 / 则删除 /
        if '/' in cmd:
            cmd = cmd.replace('/', '')  # 删除所有 /，只保留文字部分

        if cmd == "打卡":
            clear_old_checkins()
            # 获取目标列表
            if not parts1:
                # 使用上次目标
                last_checkins = get_checkins(user_id)
                if not last_checkins:
                    await ctx.reply(MessageChain([At(user_id), Plain("\n请输入打卡目标且没有历史记录！\n \
                                                                            打卡命令有：\n打卡 健身\n打卡记录\n打卡删除 健身\n打卡删除 所有")]))
                    return
                last_checkin_id = last_checkins[-1][0]
                goals = get_goals(last_checkin_id)
            else:
                goals = [g.strip() for g in parts1.split(",") if g.strip()]

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

            if parts1 == "所有":
                # 删除用户所有打卡记录
                count = delete_all_checkins(user_id)
                reply = f"已删除所有打卡记录，共{count}次打卡"
            else:
                # 删除特定目标
                goal_to_delete = parts1
                deleted_count = delete_goals(user_id, goal_to_delete)
                if deleted_count == 0:
                    reply = f"未找到目标【{goal_to_delete}】的打卡记录"
                else:
                    reply = f"已删除目标【{goal_to_delete}】的{deleted_count}条记录"
            
            await ctx.reply(MessageChain([At(user_id), Plain(f" {reply}")]))
            return

        elif cmd == "打卡记录":
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

            # 生成统计信息（按累计天数>连续天数排序）
            report = ["打卡统计（按累计天数＞连续天数排序）："]
            # 收集所有目标数据
            goals_list = []
            for goal, times in goals_data.items():
                total = len(times)
                consecutive = get_consecutive_days(user_id, goal)
                goals_list.append((goal, total, consecutive))
            
            # 双重排序：累计降序 > 连续降序
            sorted_goals = sorted(goals_list, key=lambda x: (-x[1], -x[2]))
            
            # 生成排序后的报告
            for goal_info in sorted_goals:
                goal, total, consecutive = goal_info
                report.append(f"【{goal}】累计 {total} 天 | 连续 {consecutive} 天")

            await ctx.reply(MessageChain([At(user_id), Plain("\n".join(report))]))
            return

        # 创建管理员
        elif cmd == "创建打卡管理员":
            reAdmin_status, reAdmin_id = read_admin_id(user_id)
    
            if reAdmin_status == "不存在":
                # 如果管理员不存在，发送已创建管理员的消息
                await ctx.reply(MessageChain([At(reAdmin_id), Plain(f"已创建管理员{reAdmin_id}")]))
            elif reAdmin_status == "存在":
                # 如果管理员已存在，发送已存在管理员的消息
                await ctx.reply(MessageChain([At(reAdmin_id), Plain(f"已存在管理员{reAdmin_id}")]))
        # 删除用户所有打卡记录 管理员操作
        elif cmd == "打卡管理" and not self.adminInit:
            # 读取管理员状态和 ID
            reAdmin_status, reAdmin_id = read_admin_id(user_id)
            
            if parts1 == "删除":
                if reAdmin_status == "不存在":
                    # 如果管理员不存在，提示用户创建管理员
                    await ctx.reply(MessageChain([At(int(user_id)), Plain(f'未创建打卡管理员\n使用命令<创建打卡管理员>创建')]))
                    return
                elif reAdmin_status == "存在":
                    if user_id == reAdmin_id:
                        # 如果当前用户是管理员，进入管理模式
                        self.adminInit = True
                        # 取消之前的超时任务（如果有）
                        if self.timeout_task:
                            self.timeout_task.cancel()
                        # 创建新的超时检测任务
                        self.timeout_task = asyncio.create_task(self.handle_timeout(ctx))
                        await ctx.reply(MessageChain([At(user_id), Plain(f"确认清空？(确认清空)\n倒计时7S")]))
                    else:
                        # 如果当前用户不是管理员，提示需要管理员权限
                        await ctx.reply(MessageChain([At(int(user_id)), Plain(f'需管理员 {reAdmin_id} 权限')]))
                        return
            else:
                await ctx.reply(MessageChain([At(int(get_admin_qq())), Plain(f'正确格式：\n打卡管理 删除')]))
                    
        elif cmd == "确认清空" and self.adminInit:
            clear_database()
            self.adminInit = False #重置
            self.start_time = 0
            reply = f"已删除所有打卡记录"
            await ctx.reply(MessageChain([At(user_id), Plain(f" {reply}")]))
            return
                   
# 初始化数据库
init_db()