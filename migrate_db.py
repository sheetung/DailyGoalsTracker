"""
数据库迁移工具 - 将旧版打卡数据库迁移到新版结构
版本说明：
- 旧数据库结构：
  checkins表 (id, user_id, checkin_time)
  goals表 (id, checkin_id, goal)
  关系：一个checkin记录对应多个goal
- 新数据库结构：
  goals表 (id, user_id, goal) - 存储用户的所有目标
  checkins表 (id, user_id, checkin_time, goal_id) - 每个打卡记录关联一个目标
功能说明：
1. 自动备份原始数据库
2. 创建新的数据结构
3. 迁移所有数据：
   - 将原goals表中的每个(goal,user_id)组合转为唯一goal记录
   - 为原checkins表中的每个goal创建对应的新打卡记录
4. 验证数据完整性
5. 提供替换原数据库选项
使用步骤：
1. 将本脚本放在与旧数据库(checkin.db)相同目录
2. 运行脚本: python migrate_script.py
3. 根据提示操作
注意事项：
- 迁移前会自动创建备份(checkin_backup.db)
- 如迁移失败，可从备份恢复
- 建议在测试环境先运行确认无误后再在生产环境使用
命令行参数(可选):
--old-db - 指定旧数据库路径(默认./checkin.db)
--new-db - 指定新数据库路径(默认./checkin_new.db)
"""
import sqlite3
import os
import shutil
from datetime import datetime

def migrate_database(old_db_path, new_db_path):
    """迁移数据库从旧结构到新结构"""
    
    # 创建新数据库并初始化表结构
    new_conn = sqlite3.connect(new_db_path)
    new_c = new_conn.cursor()
    
    # 创建新表结构（修正后的版本）
    new_c.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            goal TEXT NOT NULL,
            UNIQUE(user_id, goal)
        )
    ''')
    
    new_c.execute('''
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            checkin_time DATETIME NOT NULL,
            goal_id INTEGER NOT NULL,
            FOREIGN KEY (goal_id) REFERENCES goals(id)
        )
    ''')
    
    # 连接到旧数据库
    old_conn = sqlite3.connect(old_db_path)
    old_c = old_conn.cursor()
    
    try:
        # 第一步：处理目标数据
        goal_cache = {}  # 缓存格式: (user_id, goal) -> new_goal_id
        
        # 获取所有旧的目标数据（需要关联checkins表获取user_id）
        old_c.execute('''
            SELECT g.goal, c.user_id 
            FROM goals g
            INNER JOIN checkins c ON g.checkin_id = c.id
            ORDER BY c.id
        ''')
        
        for goal, user_id in old_c.fetchall():
            # 检查是否已存在该目标
            cache_key = (user_id, goal)
            if cache_key not in goal_cache:
                new_c.execute(
                    "SELECT id FROM goals WHERE user_id = ? AND goal = ?",
                    (user_id, goal)
                )
                existing = new_c.fetchone()
                
                if existing:
                    goal_cache[cache_key] = existing[0]
                else:
                    new_c.execute(
                        "INSERT INTO goals (user_id, goal) VALUES (?, ?)",
                        (user_id, goal)
                    )
                    goal_cache[cache_key] = new_c.lastrowid
        
        # 第二步：处理打卡记录
        old_c.execute('''
            SELECT c.id, c.user_id, c.checkin_time, g.goal
            FROM checkins c
            INNER JOIN goals g ON c.id = g.checkin_id
            ORDER BY c.id
        ''')
        
        # 用于跟踪已迁移的原始checkin_id
        migrated_checkins = set()
        
        for old_checkin_id, user_id, checkin_time, goal in old_c.fetchall():
            # 获取对应的新goal_id
            goal_id = goal_cache[(user_id, goal)]
            
            # 插入新的打卡记录（每个目标生成一条记录）
            new_c.execute(
                "INSERT INTO checkins (user_id, checkin_time, goal_id) VALUES (?, ?, ?)",
                (user_id, checkin_time, goal_id)
            )
            migrated_checkins.add(old_checkin_id)
        
        # 验证是否所有打卡记录都已处理
        old_c.execute("SELECT COUNT(DISTINCT id) FROM checkins")
        original_count = old_c.fetchone()[0]
        if len(migrated_checkins) != original_count:
            print(f"警告: 原始打卡记录{original_count}条，迁移后{len(migrated_checkins)}条")
        
        new_conn.commit()
        print(f"数据库迁移成功! 新数据库已保存到: {new_db_path}")
        
    except sqlite3.Error as e:
        print(f"迁移过程中发生数据库错误: {str(e)}")
        new_conn.rollback()
        raise
    finally:
        new_conn.close()
        old_conn.close()

def main():
    # 路径配置
    # BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = "data/plugins/DailyGoalsTracker"
    OLD_DB_PATH = os.path.join(BASE_DIR, "checkin.db")
    NEW_DB_PATH = os.path.join(BASE_DIR, "checkin_new.db")
    BACKUP_PATH = os.path.join(BASE_DIR, "checkin_backup.db")
    
    # 备份旧数据库
    try:
        if os.path.exists(OLD_DB_PATH):
            shutil.copy2(OLD_DB_PATH, BACKUP_PATH)
            print(f"已创建数据库备份: {BACKUP_PATH}")
        else:
            print(f"错误: 旧数据库不存在 {OLD_DB_PATH}")
            return
    except Exception as e:
        print(f"备份失败: {str(e)}")
        return
    
    # 执行迁移
    try:
        migrate_database(OLD_DB_PATH, NEW_DB_PATH)
        
        # 验证迁移结果
        with sqlite3.connect(NEW_DB_PATH) as conn:
            c = conn.cursor()
            
            # 检查目标表
            c.execute("SELECT COUNT(*) FROM goals")
            print(f"新数据库目标数量: {c.fetchone()[0]}")
            
            # 检查打卡记录表
            c.execute("SELECT COUNT(DISTINCT user_id, checkin_time) FROM checkins")
            print(f"唯一打卡记录数量: {c.fetchone()[0]}")
            
            # 检查外键约束
            c.execute("PRAGMA foreign_key_check")
            issues = c.fetchall()
            if issues:
                print("发现外键约束问题:")
                for table, rowid, parent, fkid in issues:
                    print(f"表 {table} 行 {rowid} 引用了不存在的 {parent}.{fkid}")
            else:
                print("外键约束检查通过")
                
        # 用户确认替换
        if input("是否替换旧数据库？(y/n): ").lower() == 'y':
            os.replace(NEW_DB_PATH, OLD_DB_PATH)
            print("已成功替换旧数据库")
        else:
            print("保留新旧两个数据库")
            
    except Exception as e:
        print(f"迁移失败: {str(e)}")
        print(f"请检查备份文件: {BACKUP_PATH}")

if __name__ == "__main__":
    main()
