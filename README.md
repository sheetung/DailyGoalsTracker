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

触发命令`打卡 健身`

会记录 `健身` 打卡一次

触发命令`打卡记录`

统计所有时间段的打卡记录

**谨慎操作，不可恢复**另有指令 `打卡删除 健身`、`打卡删除 所有`

## 更新历史

v0.2 增加打卡删除功能

v0.1 初始化

