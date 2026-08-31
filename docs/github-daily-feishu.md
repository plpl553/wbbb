# GitHub 每日热点推送到飞书

这项独立任务每天北京时间 09:00 汇总 GitHub 近 7 天的新锐仓库，并通过仓库现有的飞书通知 Secret 发送一张消息卡片。它不会改变 TrendRadar 原有的新闻抓取任务。

## 首次启用

1. 打开仓库 `Settings → Secrets and variables → Actions`。
2. 添加或确认 Repository secret `FEISHU_WEBHOOK_URL`，值为目标飞书群的自定义机器人 Webhook。
3. 如机器人启用了签名校验，再添加 `FEISHU_SIGNING_SECRET`。
4. 打开 `Actions → GitHub Daily Hot to Feishu → Run workflow`。
5. 首次先勾选 `dry_run` 检查生成结果；确认后取消勾选，再运行一次完成真实推送。

如果飞书机器人启用了关键词校验，请允许关键词 `github`。消息正文固定包含该关键词。

## 热点口径

GitHub 没有公开的 Trending API。本任务使用 GitHub Search API，选择近 7 天创建、非 fork、未归档的公开仓库，并按当前累计 Star 数倒序取前 10 项。这个口径强调近期快速获得关注的新项目，且每天都能稳定复现。

## 调整设置

- 运行时间：编辑 `.github/workflows/github-daily-hot.yml` 的 cron。GitHub Actions 使用 UTC，`0 1 * * *` 对应北京时间 09:00。
- 统计窗口：修改 `github_daily_hot.py` 中的 `DEFAULT_DAYS`。
- 项目数量：修改 `github_daily_hot.py` 中的 `DEFAULT_LIMIT`。

Webhook 只能存放在 GitHub Secret 中，不要写进配置文件、代码、Issue 或 PR。

