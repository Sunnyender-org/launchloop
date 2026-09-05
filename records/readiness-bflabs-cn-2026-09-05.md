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

## Owner gate 两步（2026-09-05 已完成，Ender 授权）

- [x] Cloudflare 开关：实际位置不在 Security → Settings 的"配置"按钮里，而是 **AI Crawl Control → 概述 → "托管 robots.txt" 开关**（`/bflabs.cn/ai/overview`）。用 ego-browser 晨曦档案关闭。关闭后约 10 秒线上 robots.txt 的 `# BEGIN Cloudflare Managed content` 块消失
- [x] PR #18 合并（advisory 文案审查因 CI 侧模型不可用而失败，与改动无关；两项仓库校验通过），`wrangler deploy` 版本 `82236830-7fe2-433c-adb6-7f8d3d6f5a80`

## 复测（部署后）

报告：`records/readiness-bflabs-cn-2026-09-05-check-after.md`。硬门槛 FAIL 0，退出码 0。

| ID | 修复前 | 修复后 |
|---|---|---|
| L01 http → https | FAIL（http 200） | PASS（301） |
| F02 AI 搜索爬虫 | FAIL（ClaudeBot、Google-Extended 被 Cloudflare 托管块拦） | PASS |
| F05 canonical | FAIL | PASS |
| F07 JSON-LD | FAIL | PASS（Organization / WebSite / WebApplication） |
| R01 安全头 | WARN（四项全缺） | PASS |
| F09 Open Graph | WARN（三项全缺） | WARN（仅缺 og:image，需要一张 1200×630 的图） |

## 遗留决策

- **GPTBot**：2026-09-05 Ender 决定放行。理由：GEO 产品，希望被模型学到。线上当前无 GPTBot 规则即默认放行，无需改动；下次动 robots.txt 时顺手加显式 `User-agent: GPTBot` / `Allow: /`，让决策可见。M12 关闭。
- og:image：需要设计一张 1200×630 分享图，放 `public/og.png` 后加 `og:image`。
