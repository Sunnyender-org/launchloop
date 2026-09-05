# 修法索引：检查 ID → 修复配方

ID 与 `launchloop-check/scripts/check.py` 一一对应。每条写：症状、根因、修法、验证、模板。

## Ready 门（R / S 系列）

### R01 安全响应头
- 根因：框架默认不发 HSTS / nosniff / frame / referrer 头。
- 修法：按框架加。模板 `templates/security-headers.md` 给了 Next.js `headers()`、Astro / Vite 静态站的 `_headers`（Cloudflare Pages / Netlify）、Nginx、Cloudflare Worker 四种。
- 验证：`curl -sI https://domain | grep -i "strict-transport\|x-content-type\|x-frame\|referrer"`。
- 注意：`Strict-Transport-Security` 一旦加了 `preload` 很难撤回，第一次只加 `max-age=31536000; includeSubDomains`。

### R02 生产 URL 暴露 .env / .git
- **第一步不是修配置，是轮换所有密钥。** `.env` 被读到过就当作已泄露。
- 根因：静态目录直接映射了仓库根，或反向代理没拒绝点开头路径。
- 修法：Nginx `location ~ /\.(?!well-known) { deny all; }`；Vercel / Cloudflare Pages 默认不会暴露，若暴露说明把仓库根当 `public` 目录了，改 `outputDirectory`。
- 验证：`curl -sI https://domain/.env` 应为 404 / 403。

### R03 健康检查端点
- 修法：加 `/api/health`，只查数据库连通（`SELECT 1`）与关键外部依赖可达，返回 `{ "ok": true, "db": "up" }`；接入部署平台的 health check。模板 `templates/health-endpoint.md`。
- 不要在 health 里返回版本号、commit hash 以外的任何内部信息。

### S01 .env 被 git 跟踪
- `git rm --cached .env`，`.gitignore` 加 `.env*` 和 `!.env.example`。
- **历史里仍在**：告诉用户用 `git log --all -p -- .env` 看曾经提交过什么，全部轮换。改写历史（filter-repo）是可选项，轮换是必选项。

### S02 源码里硬编码密钥
- 同 S01：先轮换。然后把值改成 `process.env.X` / `os.environ["X"]`，在 `.env.example` 加同名空变量。
- 若匹配到的是占位符（`sk-your-key-here`）或测试固件，在报告里标注即可，不用改。

### S03 密钥进了前端 bundle
- 根因：变量用了 `NEXT_PUBLIC_` / `VITE_` / `REACT_APP_` / `EXPO_PUBLIC_` 前缀，构建时会内联到浏览器 JS。
- 修法：去掉前缀；把用到它的调用挪到服务端（Next.js Route Handler / Server Action、Astro endpoint、Cloudflare Worker、Supabase Edge Function）；前端改调自己的服务端接口。
- 唯一例外：Supabase `anon` key、Stripe `pk_` publishable key、PostHog / Plausible 的公开 key 允许进前端。
- 验证：`npm run build` 后 `grep -r "sk_live\|sk-\|service_role" .next/static dist/` 为空。
- **轮换**：已经部署过的构建里那把 key 已经公开了。

### S04 表未启用 RLS
- 只对 Supabase / PostgREST 栈有意义。D1 / Prisma / Drizzle 直连的应用由代码负责按用户过滤，检查会标 UNKNOWN，人工确认每个查询都带 `where user_id = current`。
- 修法：模板 `templates/supabase-rls.sql`：对每张表 `enable row level security`，按 `auth.uid()` 写 select / insert / update / delete 四条 policy。**生成 SQL 给人审，不直接跑生产。**
- 验证：用两个账号登录，A 尝试读 B 的行，必须为空或 403。这是 M06。

### S05 昂贵接口无限流 / 花费上限
- 两层：代码限流 + 平台硬上限，缺一不可。
- 代码：模板 `templates/rate-limit.md`（Next.js middleware + Upstash Ratelimit；Cloudflare Worker 用 KV / Durable Object 计数；Python 用 slowapi）。按 IP 和按用户各一条，匿名用户额度远低于登录用户。
- 平台：OpenAI → Settings → Limits → Monthly budget；Anthropic → Plans & billing → Spend limit。这是 M05，人做，五分钟。
- 验证：`for i in $(seq 1 30); do curl -s -o /dev/null -w "%{http_code}\n" -X POST https://domain/api/generate; done` 应出现 429。

### S06 支付 webhook 无幂等
- 根因：Stripe / Lemon Squeezy / Paddle / Creem 都会重发、乱序、延迟；handler 只按事件类型处理，没记录处理过的 `event.id`。
- 修法：模板 `templates/webhook-idempotent.md`：建 `processed_events(id primary key, type, received_at)` 表；handler 第一步 `insert ... on conflict do nothing`，插入 0 行就直接返回 200；验签在最前面；处理逻辑要能接受"先收到 `subscription.updated` 再收到 `checkout.completed`"。
- 验证：Stripe CLI `stripe trigger checkout.session.completed` 两次，权益只开一次；或者在 Dashboard 里对同一事件点 Resend。

### S07 noindex 未受环境控制
- 修法：模板 `templates/env-gated-noindex.md`：`robots` meta 与 `X-Robots-Tag` 按 `VERCEL_ENV === "production"` / `NODE_ENV` / 自定义 `SITE_ENV` 切换；预发布域名全部 noindex，生产全部 index。
- 验证：`curl -s https://domain | grep -i robots`；预发布域名同样查一遍，应相反。

### S08 无 .env.example
- 从 `.env` 复制一份，值全部清空或换成 `changeme`，提交。

## Live 门（L 系列）

### L01 http 未跳 https
- Vercel / Cloudflare Pages / Netlify 默认已做；自托管在 Nginx / Caddy 加 301。Cloudflare 开 "Always Use HTTPS"。

### L02 www 与裸域都 200
- 选一个（建议裸域），另一个 301。Vercel 在 Domains 里设 redirect；Cloudflare 用 Redirect Rule。同时 `canonical` 指向选定主机。

### L03 法务页缺失
- 模板 `templates/legal-pages.md`：ToS / Privacy / Refund / Cookie 四页的结构骨架与占位符，含中国路径需要的《个人信息保护法》与生成式 AI 标识段。
- **本 Skill 只出结构，不写有法律效力的正文。** 正文由人写或用 Termly / iubenda / GetTerms 类生成器生成后人审。模板顶部有"非法律意见"声明，保留它。
- Refund 页必须与支付平台实际行为一致：MoR 平台（Lemon Squeezy / Paddle / Creem）有自己的退款政策，会覆盖你写的"不退款"。
- footer 加四个链接，且链接文字含 terms / privacy / refund 或 条款 / 隐私 / 退款，检查按这些词找。

### L04 定价页缺失或客户端渲染
- 加 `/pricing` 并从首页导航链过去；必须 SSR / SSG，禁 JS 能看到价格数字。价格数字从单一来源（配置文件或支付平台 API 的构建时快照）取，不手写两份。

## Found 门（F 系列）

### F01 robots.txt 全站 Disallow 或不存在
- 模板 `templates/robots.txt`。删掉 `Disallow: /`；staging 域名才需要它，用 S07 的方式按环境生成。

### F02 AI 搜索爬虫被拦
- 在 `robots.txt` 为 `OAI-SearchBot`、`PerplexityBot`、`ClaudeBot`、`Google-Extended`、`Bingbot` 各加显式 `Allow: /` 组。模板同上。
- `GPTBot` 是训练用，与 ChatGPT 搜索引用无关；**保持用户原决策**，只在用户明确说放行时加。
- 同时检查 CDN / WAF 的 bot 规则：Cloudflare "Bot Fight Mode" 会拦这些 UA，robots.txt 放了也没用。Cloudflare 有 "Verified Bots" 白名单，确认这几家在里面。
- **Cloudflare "Managed robots.txt"（Content Signals）会在你的 robots.txt 前面自动插入一段 `# BEGIN Cloudflare Managed content`，其中默认 `Disallow: /` 了 ClaudeBot、Google-Extended、GPTBot、CCBot、Bytespider、Applebot-Extended 等。** 这段是后台开关生成的，不在你的仓库里，`launchloop-check` 会把它当成真实拦截报 F02 FAIL（它确实生效）。修法：Cloudflare Dashboard → 域名 → Security → Settings（或 Bots）→ 关闭 "Managed robots.txt"，或在 Content Signals 里把 `ai-input` 设为 yes；然后确认自己的 robots.txt 里为 AI 搜索爬虫显式 Allow。真实案例：readiness.bflabs.cn 2026-09-05 被这个开关拦了 ClaudeBot 和 Google-Extended。

### F03 sitemap 缺失或含非 200 条目
- Next.js：`app/sitemap.ts`；Astro：`@astrojs/sitemap`；其他框架用构建脚本生成。只放 canonical、200、可索引的 URL。`robots.txt` 里 `Sitemap:` 声明绝对 URL。
- 提交到 GSC 与 Bing Webmaster 是人工步骤（F03m）。

### F04 首页 noindex
- 同 S07。

### F05 title / description / canonical / h1 / lang
- Next.js Metadata API：每个 `page.tsx` 导出 `metadata` 或 `generateMetadata`，`alternates.canonical` 必填；`<html lang>` 在根 layout。
- 一页一个 `<h1>`。组件库的 Logo 常常是 `<h1>`，改成 `<div>` 或 `<p>`。

### F06 首页客户端渲染空壳
- 根因：Vite SPA / CRA，或 Next.js 整页 `'use client'` 且数据在 `useEffect` 里取。
- 修法：Next.js 把数据获取移到 Server Component；Vite SPA 用 `vite-plugin-ssr`/预渲染，或把营销页迁到 Astro（应用本体可以继续 SPA）。至少首页、定价、功能、文档入口四类页面必须 SSR。
- 验证：`curl -s https://domain | python3 -c "import sys,re,html; t=re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>',' ',sys.stdin.read(),flags=re.S); print(len(html.unescape(t).split()))"` 词数应 > 60。

### F07 JSON-LD 缺失或无效
- 模板 `templates/jsonld.md`：`Organization`（name / url / logo / sameAs）+ `SoftwareApplication` 或 `Product`（含 `offers` 价格）+ 有 FAQ 的页面加 `FAQPage`。
- **内容必须与页面可见文本一致**：价格、名称、FAQ 问答都从页面同一数据源渲染，不另写一份。
- 产品描述、价格、公司名是业务事实：从仓库现有数据取，取不到就问。
- 验证：Google Rich Results Test；或 `python3 -c "import json,sys; json.load(sys.stdin)"` 喂每个块确认能解析。

### F08 llms.txt 缺失或不合规
- 模板 `templates/llms.txt`。规则：`# 站名` 开头 → `>` 一段 30–60 字描述 → H2 分组 → 每行 `- [标题](绝对URL): 一句话`；20–80 个链接；全部 200；`Content-Type: text/plain` 或 `text/markdown`；< 100KB。
- 放在 `public/llms.txt`（静态）即可；Next.js 若要动态生成用 `app/llms.txt/route.ts` 并显式设 content-type。
- 链接的页面清单：定价、文档入口、关于、可引用一页纸、对比页、变更日志。裸 URL 列表也算合规（检查会识别）。
- `robots.txt` 加一行 `# LLM directory: https://domain/llms.txt`。
- 验证：`curl -sI https://domain/llms.txt` 看 200 与 content-type；重跑 check。

### F09 Open Graph
- Next.js Metadata API 的 `openGraph` 与 `twitter` 字段；`og:image` 1200×630，绝对 URL。

## 只能人做的（M 系列）

本 Skill 对 M 系列只给步骤，不代做：

- M01 备份恢复演练：给出对应数据库的 dump / restore 命令，让人在临时实例上跑一遍。
- M05 花费上限：给出 OpenAI / Anthropic / Resend / Twilio 后台的路径。
- M06 越权读取测试：给出两个账号的测试脚本。
- M07 MoR 决策：给出 `LAUNCHLOOP.md` 门 2 的对比表和 `CHINA.md` 的主体决策表，让人选。
- M10 / M11 真卡烟测：给出 `templates/launch-record.md` 里的六步表格，让人填。
- M13 Agent Readiness 扫描：给出 readiness.bflabs.cn 或 `geo-discover` 的入口。
