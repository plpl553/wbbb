# GitHub 每日热点推送到飞书

这项任务每天北京时间 09:17 汇总 GitHub 近 7 天的新锐仓库，并通过仓库现有的飞书通知 Secret 发送一张消息卡片。调度复用仓库中曾连续成功运行的 `crawler.yml` 工作流 ID；原 TrendRadar 爬虫被限制为仅手动触发。鉴于 GitHub cron 在本仓库历史上约有 30 分钟排队延迟，工作流会在 08:30、08:45 和 09:00 提前申请运行；最先启动的任务等待到 09:17 再发送，后续任务通过上海自然日内的成功记录自动跳过，因此每天最多发送一次。

每个热点项目都会展示英文原始简介、中文翻译和一行中文用途说明，便于快速判断项目价值。翻译和摘要由 `glm-4.5-air` 一次批量生成；模型接口临时不可用时，任务会保留英文原文和基于仓库元数据生成的用途说明，不会因此中断飞书推送。

## 首次启用

1. 打开仓库 `Settings → Secrets and variables → Actions`。
2. 添加或确认 Repository secret `FEISHU_WEBHOOK_URL`，值为目标飞书群的自定义机器人 Webhook。
3. 如机器人启用了签名校验，再添加 `FEISHU_SIGNING_SECRET`。
4. 添加 Repository secret `ZHIPU_API_KEY`，值为智谱开放平台 API Key。
5. 打开 `Actions → GitHub Daily Hot to Feishu → Run workflow`。
6. 首次先勾选 `dry_run` 检查生成结果；确认后取消勾选，再运行一次完成真实推送。

如果飞书机器人启用了关键词校验，请允许关键词 `github`。消息正文固定包含该关键词。

## 热点口径

GitHub 没有公开的 Trending API。本任务使用 GitHub Search API，选择近 7 天创建、非 fork、未归档的公开仓库，并按当前累计 Star 数倒序取前 10 项。这个口径强调近期快速获得关注的新项目，且每天都能稳定复现。

## 调整设置

- 运行时间：编辑 `.github/workflows/crawler.yml` 的 cron。工作流使用 `Asia/Shanghai` 时区，在 08:30、08:45 和 09:00 提前排队，并调用 `.github/workflows/github-daily-hot-v2.yml` 在 09:17 执行发送。
- 统计窗口：修改 `github_daily_hot.py` 中的 `DEFAULT_DAYS`。
- 项目数量：修改 `github_daily_hot.py` 中的 `DEFAULT_LIMIT`。

Webhook 只能存放在 GitHub Secret 中，不要写进配置文件、代码、Issue 或 PR。

