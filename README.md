# DailyGoalsTracker

<p align="center"> <img src="https://img.shields.io/badge/LangBot-Plugin-blue" alt="LangBot Plugin"> <img src="https://img.shields.io/badge/Version-v0.6-green" alt="Version"> </p><p align="center"> <b>LangBot 插件，实现每日目标打卡，可重复打卡不同目标，并统计持续打卡时间、月度和年度打卡记录等。</b> </p>

------

## 📚 项目简介

`DailyGoalsTracker` 是一个为 [LangBot](https://github.com/RockChinQ/LangBot) 设计的插件，旨在帮助用户通过简单的命令完成每日目标打卡，并记录打卡数据。它支持多目标打卡、打卡记录查询、数据统计等功能。

## 🛠️ 安装方法

在配置完成 [LangBot](https://github.com/RockChinQ/LangBot) 主程序后，使用管理员账号向机器人发送以下命令即可安装：

bash复制

```bash
!plugin get https://github.com/sheetung/DailyGoalsTracker
```

或者查看详细的 [插件安装说明](https://docs.langbot.app/plugin/plugin-intro.html#插件用法)。

------

## 📖 使用说明

### 📝 前置说明

- 支持前缀`/`触发插件，例如将 `打卡记录` or `/打卡记录`
- 如果需要修改关键词，可以编辑 `main.py` 中的关键词判定，例如将 `打卡记录` 修改为 `目标记录`。

### 🗄️ 数据库结构

本插件使用两个表：`checkins` 表存储打卡记录，`goals` 表存储打卡目标，通过外键关联。

#### 表 1：`checkins`

| 字段名         | 数据类型 | 约束条件                  | 说明                 |
| :------------- | :------- | :------------------------ | :------------------- |
| `id`           | INTEGER  | PRIMARY KEY AUTOINCREMENT | 唯一标识符，自增主键 |
| `user_id`      | TEXT     | NOT NULL                  | 用户的 QQ 号         |
| `checkin_time` | DATETIME | NOT NULL                  | 打卡时间（精确到秒） |

#### 表 2：`goals`

| 字段名       | 数据类型 | 约束条件                  | 说明                 |
| :----------- | :------- | :------------------------ | :------------------- |
| `id`         | INTEGER  | PRIMARY KEY AUTOINCREMENT | 唯一标识符，自增主键 |
| `checkin_id` | INTEGER  | NOT NULL                  | 关联的打卡记录 ID    |
| `goal`       | TEXT     | NOT NULL                  | 打卡目标             |

------

### 🚀 功能命令

#### 🐧 创建管理员

- **命令**：`创建打卡管理员`
- **功能**：记录当前管理员ID至`admin_data.json`

#### 💪 打卡目标

- **命令**：`打卡 <目标>`
- **示例**：`打卡 健身`
- **功能**：记录指定目标的打卡一次。

#### 📋 查看打卡记录

- **命令**：`打卡记录`
- **功能**：统计所有时间段的打卡记录。

#### 🛠️ 打卡管理

- **命令**：`打卡管理 删除`
- **功能**：默认第一条打卡记录者为管理员，触发命令后输入 `确认清空` 可清空所有数据库。
- **注意**：此操作不可恢复！

#### 🗑️ 删除指定打卡记录

- **命令**：`打卡删除 <目标>` 或 `打卡删除 所有`
- **功能**：删除指定目标的打卡记录或所有打卡记录。
- **注意**：仅操作当前提问账户的id

#### 🔁 重复打卡

- **命令**：`打卡`
- **功能**：默认打卡当前提问用户的前一次目标。

### 📂 数据迁移

迁移数据时，只需复制 `checkin.db` 数据库文件即可。

------

## 📝 待办事项（TODO）

- [ ] 增加月/年度排行榜功能。
- [ ] 增加管理员删除指定用户目标的功能。
- [x] 增加管理员功能，针对整个数据库进行修改。

------

## 📋 更新历史

- **v0.7**：独立管理员数据，不影响数据库
- **v0.6**：增加管理员功能。
- **v0.5**：增加打卡记录排序功能。
- **v0.2**：增加打卡删除功能。
- **v0.1**：初始化版本。

------

## 📚 关于

**DailyGoalsTracker** 是一个基于 [LangBot](https://github.com/RockChinQ/LangBot) 的插件，旨在帮助用户实现每日目标打卡、记录和统计功能。更多详情请参考 [LangBot 文档](https://docs.langbot.app/plugin/plugin-intro.html)。

<p align="center"> <a href="https://github.com/sheetung/DailyGoalsTracker/issues">报告问题</a> | <a href="https://github.com/sheetung/DailyGoalsTracker/pulls">贡献代码</a> </p>

------

### 🌟 如果你喜欢这个项目，请给它一个星标！🌟

------

