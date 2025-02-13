# DailyGoalsTracker

参考仓库

[langbot_Checkin](https://github.com/GryllsGYS/langbot_Checkin)

## 安装

配置完成 [LangBot](https://github.com/RockChinQ/LangBot) 主程序后使用管理员账号向机器人发送命令即可安装：

```
!plugin get https://github.com/sheetung/DailyGoalsTracker
```
或查看详细的[插件安装说明](https://docs.langbot.app/plugin/plugin-intro.html#%E6%8F%92%E4%BB%B6%E7%94%A8%E6%B3%95)

## 使用

<!-- 插件开发者自行填写插件使用说明 -->
### 写在前面

若要与本插件使用相同的触发关键词，需要在bot后台设置触发规则，使用触发词触发ai对话例如：`ai`

否则修改`main.py`中关键词判定，例如：将`打卡记录`修改为`/打卡记录`

---

### 数据库结构

两个表：`checkins` 表存储打卡记录，`goals` 表存储打卡目标，通过外键关联。

**表 1：`checkins`**

| 字段名         | 数据类型 | 约束条件                  | 说明                 |
| :------------- | :------- | :------------------------ | :------------------- |
| `id`           | INTEGER  | PRIMARY KEY AUTOINCREMENT | 唯一标识符，自增主键 |
| `user_id`      | TEXT     | NOT NULL                  | 用户的 QQ 号         |
| `checkin_time` | DATETIME | NOT NULL                  | 打卡时间（精确到秒） |

**表 2：`goals`**

| 字段名       | 数据类型 | 约束条件                  | 说明                 |
| :----------- | :------- | :------------------------ | :------------------- |
| `id`         | INTEGER  | PRIMARY KEY AUTOINCREMENT | 唯一标识符，自增主键 |
| `checkin_id` | INTEGER  | NOT NULL                  | 关联的打卡记录 ID    |
| `goal`       | TEXT     | NOT NULL                  | 打卡目标             |

---


触发命令`打卡 健身`

会记录 `健身` 打卡一次

触发命令`打卡记录`

统计所有时间段的打卡记录

触发命令`打卡管理 删除`
默认第一条打卡记录者为管理员，触发命令后输入`确认清空`清空所有数据库

tips: 触发命令`打卡`,默认打卡前一次的目标

**谨慎操作，不可恢复**另有指令 `打卡删除 健身`、`打卡删除 所有`

> [!TIP]
> 迁移数据只需copy`checkin.db`数据库文件


## TODO

- [ ] 增加月/年度排行榜

- [ ] 增加管理员删除指定用户目标

- [x] 增加管理员功能，针对整个数据库做修改

## 更新历史

v0.6 增加管理员功能

v0.5 增加打卡记录排序功能

v0.2 增加打卡删除功能

v0.1 初始化

