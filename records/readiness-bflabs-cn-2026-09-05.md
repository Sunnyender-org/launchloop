# LaunchLoop 上线记录：readiness.bflabs.cn（Found 门复查）

这是 LaunchLoop 的第一份真实 record。产品早已上线，本次不是首发，而是用 `launchloop-check` 对一个已上线的免费工具做 Lite 档复查，并走完 check → implement → PR 的回路。公开站点，无敏感数据，故提交进仓库作为示例。

## 基本信息

| 项 | 值 |
|---|---|
| 产品 | BFLabs Agent Readiness（网站 AI 就绪度免费诊断） |
| 生产域名 | https://readiness.bflabs.cn |
| 档 | Lite（免费工具，不收钱） |
| 部署平台 | Cloudflare Worker + Assets，自定义域名 |
| 仓库 | Sunnyender-org/bflabs-agent-readiness，`app/readiness-web` |
| 支付路线 | 不适用（Lite） |
| Owner：工程 / SEO-GEO | Ender |

## 门 4 · Found —— 复查结果

自动检查：`records/readiness-bflabs-cn-2026-09-05-check-before.md`（修复前）。硬门槛 FAIL 4 项：

| ID | 发现 | 根因 | 处理 |
|---|---|---|---|
| L01 | `http://` 返回 200，不跳 https | Worker 未处理协议；Cloudflare 未开 Always Use HTTPS | Worker 入口加 301（PR #18） |
| F02 | robots.txt 拦了 ClaudeBot、Google-Extended | **Cloudflare "Managed robots.txt / Content Signals" 开关自动前置了 Disallow 块，仓库里看不到** | 仓库 robots.txt 显式 Allow 五家 AI 搜索爬虫（PR #18）；关开关是后台操作，待 Owner |
| F05 | 首页无 canonical | 未写 | `index.html` 加 canonical + Open Graph（PR #18） |
| F07 | 无 JSON-LD | 未写 | 加 Organization / WebSite / WebApplication，事实全部来自页面已有文案（PR #18） |

顺手：R01 安全头（HSTS / nosniff / X-Frame-Options / Referrer-Policy）在 Worker 层统一加上。

仓库侧安全检查（S 系列）：S01 / S02 / S03 PASS；S04 标 UNKNOWN（D1 数据库，RLS 不适用，应用层隔离由代码负责）；S05 UNKNOWN（本仓库没有 AI 调用，限流由 Cloudflare ratelimit binding 提供）。

## 教训（回流到 LAUNCHLOOP.md）

1. **线上 robots.txt 必须 `curl` 核对，不能只看仓库。** CDN 层的托管规则会改你的 robots.txt 而不留痕。已加为 Found 门硬门槛。
2. 一个做 GEO 诊断的产品自己被 CDN 开关拦了两家 AI 爬虫。清单的价值就在这种"自己觉得肯定没问题"的地方。

## 待 Owner 的两步

- [ ] Cloudflare Dashboard → `bflabs.cn` → Security → Settings → 关闭 **Managed robots.txt**（或 Content Signals 设 `ai-input=yes`）
- [ ] 合并 PR #18 并 `wrangler deploy`

## 复测（部署后填）

```bash
python3 skills/launchloop-check/scripts/check.py --url https://readiness.bflabs.cn --tier lite \
  --report records/readiness-bflabs-cn-2026-09-05-check-after.md
```

| ID | 修复后状态 |
|---|---|
| L01 | |
| F02 | |
| F05 | |
| F07 | |
