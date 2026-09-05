# LaunchLoop Check — https://readiness.bflabs.cn

- 档: **lite**  · 仓库: /Users/sunny/Work/CC/bflabs-agent-readiness  · 时间: 2026-09-05 21:13:18
- 结果: 15 pass · 0 fail · 3 warn · 2 unknown · 7 manual
- **硬门槛失败: 0** → 可以进下一门（人工项另勾）

## 门 · Ready

| ID | 检查 | 状态 | 硬 | 证据 |
|---|---|---|---|---|
| R01 | 安全响应头 | PASS | S | HSTS / nosniff / frame / referrer 齐 |
| R02 | 生产 URL 不暴露 .env / .git | PASS | H | 均为 404/403 或非文件内容 |
| S01 | .env 不在 git 里 | PASS | H | 仅 .env.example 或无 |
| S02 | 源码里无硬编码密钥 | PASS | H | 扫描 212 个文件未见密钥模式 |
| S03 | 密钥不进前端 bundle（公开前缀变量名审查） | PASS | H | 公开前缀变量名中无 SECRET / SERVICE_ROLE / OPENAI 等 |
| S04 | 每张表启用 RLS | UNKNOWN | H | 未检测到 Supabase / PostgREST；RLS 不适用。请确认应用层每个查询都按当前用户过滤（D1 / Prisma / Drizzle 等由代码负责隔离） |
| S05 | 昂贵接口有 rate limit + 花费上限 | UNKNOWN | H | 未检测到 AI 调用；若有其他昂贵接口（邮件/短信/图片）请手动确认 |
| S08 | .env.example 存在 | WARN | S | 无；新环境部署时容易漏变量 |
| M02 | 可回滚：上一版镜像或 feature flag 可一键关 | MANUAL | H | 只能人工确认；在 record 里勾 |
| M04 | 错误追踪（Sentry 等）在生产已收到一次手动触发 | MANUAL | H | 只能人工确认；在 record 里勾 |
| M05 | AI / 邮件 / 短信平台后台已设月度花费硬上限 | MANUAL | H | 只能人工确认；在 record 里勾 |
| M06 | 用第二个账号尝试读他人数据，失败 | MANUAL | H | 只能人工确认；在 record 里勾 |

## 门 · Live

| ID | 检查 | 状态 | 硬 | 证据 |
|---|---|---|---|---|
| L01 | http → https 跳转 | PASS | H | 301 → https://readiness.bflabs.cn/ |
| L02 | www / 裸域单一 canonical 主机 | WARN | S | www.readiness.bflabs.cn 不可达；如果你只用 readiness.bflabs.cn 也可以，但建议另一个 301 过来 |

## 门 · Found

| ID | 检查 | 状态 | 硬 | 证据 |
|---|---|---|---|---|
| F00 | 首页可访问 | PASS | H | HTTP 200, final https://readiness.bflabs.cn |
| F01 | robots.txt 未误拦搜索引擎 | PASS | H | 无全站 Disallow |
| F02 | AI 搜索爬虫放行 | PASS | H | AI 搜索爬虫均可访问; GPTBot(训练用) 放行 —— 这是独立决策，记录理由即可 |
| F03 | sitemap.xml 可访问且条目 200 | PASS | H | https://readiness.bflabs.cn/sitemap.xml: 4 条 |
| F03m | Search Console + Bing Webmaster 已验证并提交 sitemap | MANUAL | H | 无法自动检测，需人工确认 |
| F04 | 首页无 noindex | PASS | H | meta robots='' x-robots-tag='' |
| F05 | title / description / canonical / 单 h1 / lang | PASS | H | title='BFLabs Agent Readiness' canonical=https://readiness.bflabs.cn/ |
| F06 | 首页服务端渲染出可读文本（AI 爬虫不跑 JS） | PASS | H | 禁 JS 可见文本 1233 字符 |
| F07 | JSON-LD 结构化数据 | PASS | H | types=['Organization', 'WebApplication', 'WebSite'] invalid_blocks=0 |
| F08 | llms.txt | PASS | H | 8 个绝对链接, content-type=text/plain |
| F09 | Open Graph 分享卡 | WARN | S | 缺 og:image |
| M12 | GPTBot 放行与否已做决策并记录理由 | MANUAL | H | 只能人工确认；在 record 里勾 |
| M13 | Agent Readiness 扫描（readiness.bflabs.cn 或 geo-discover）三轴 pass | MANUAL | H | 只能人工确认；在 record 里勾 |

## 说明

- UNKNOWN 表示无法自动判定，不是失败；MANUAL 表示只能人工确认。两者都要在 record 里补。
- 此脚本只覆盖可自动化的部分。Paid 门几乎全部是人工项，这是设计使然。
- 修复请用 `launchloop-implement`，每个 FAIL 的修法都对应其 templates/ 里的一个模板。