# DailyGoalsTracker

<p align="center"> <img src="https://img.shields.io/badge/LangBot-Plugin-blue" alt="LangBot Plugin"> <img src="https://img.shields.io/badge/Version-v1.31-green" alt="Version"> </p><p align="center"> <b>LangBot 插件，实现每日目标打卡，可重复打卡不同目标，并统计持续打卡时间、月度和年度打卡记录等。</b> </p>

------

## 📚 项目简介

`DailyGoalsTracker` 是一个为 [LangBot](https://github.com/RockChinQ/LangBot) 设计的插件，旨在帮助用户通过简单的命令完成每日目标打卡，并记录打卡数据。它支持多目标打卡、打卡记录查询、数据统计等功能。

加群push群主更新，反馈bug,交流

[![QQ群](https://img.shields.io/badge/QQ群-965312424-green)](https://qm.qq.com/cgi-bin/qm/qr?k=en97YqjfYaLpebd9Nn8gbSvxVrGdIXy2&jump_from=webapi&authKey=41BmkEjbGeJ81jJNdv7Bf5EDlmW8EHZeH7/nktkXYdLGpZ3ISOS7Ur4MKWXC7xIx)

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

为避免私聊触发ai问答，请在传入消息中忽略`/`，如图

![忽略规则](figs/1.png)

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

- 以下命令均可使用前缀`/`触发

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
- **功能**：需使用命令`创建打卡管理员`创建管理员，触发命令后输入 `确认清空` 可清空所有数据库。
- **注意**：此操作不可恢复！

#### 🗑️ 删除指定打卡记录

- **命令**：`打卡删除 <目标>` 或 `打卡删除 所有`
- **功能**：删除指定目标的打卡记录或所有打卡记录。
- **注意**：仅操作当前提问账户的id

#### 🔁 重复打卡

- **命令**：`打卡`
- **功能**：默认打卡当前提问用户的前一次目标。

### 🔭 打卡分析

- **命令**：`打卡分析`
- **功能**：调用AI分析30天内的打卡记录

### 🍕 补漏打卡

- **命令**：`打卡补 <用户id> <目标> <时间>`
- **示例**：`打卡补 755855262 健身 2025-03-12`
- **功能**：补漏打卡

### 📂 数据迁移

迁移数据时，只需复制 `checkin.db` 数据库文件即可。


------

## 📝 待办事项（TODO）

- [x] 通过AI分析打卡记录⭐
- [ ] 增加月/年度排行榜功能。
- [ ] 增加管理员删除指定用户目标的功能。
- [x] 增加管理员功能，针对整个数据库进行修改。

------

## 📋 更新历史

- **v1.31**：增加补卡功能
- **v1.21**：**！！！重构数据库**，谨慎按照补充说明操作
- **v1.11**：增加数据库备份功能
- **v1.01**：增加AI分析功能
- **v0.91**：更改数据库存放路径`data/plugins/DailyGoalsTracker/`
- **v0.85**：增加黑白名单适配
- **v0.80**：优化插件格式
- **v0.70**：独立管理员数据，不影响数据库
- **v0.60**：增加管理员功能。
- **v0.50**：增加打卡记录排序功能。
- **v0.20**：增加打卡删除功能。
- **v0.10**：初始化版本。

### 补充说明

针对v1.21版本以前的用户升级的数据库操作

使用前请备份数据库，例如改名为`checkin_old.db`

运行`migrate_db.py`更新数据库

！！！如不会操作，进交流群找群主帮忙

------

## 📚 关于

**DailyGoalsTracker** 是一个基于 [LangBot](https://github.com/RockChinQ/LangBot) 的插件，旨在帮助用户实现每日目标打卡、记录和统计功能。更多详情请参考 [LangBot 文档](https://docs.langbot.app/plugin/plugin-intro.html)。

感谢ElvisChenML大佬的[Waifu](https://github.com/ElvisChenML/Waifu)插件提供的帮助

<p align="center"> <a href="https://github.com/sheetung/DailyGoalsTracker/issues">报告问题</a> | <a href="https://github.com/sheetung/DailyGoalsTracker/pulls">贡献代码</a> </p>

------

### 🌟 如果你喜欢这个项目，请给它一个星标！🌟

------