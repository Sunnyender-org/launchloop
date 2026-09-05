# LaunchLoop 主清单

版本：v0.1（2026-09-05）
适用：小团队自助 SaaS / Web 产品，从"前后端开发完成"到"有人付钱、有人搜到"。

图例：
- `[H]` 硬门槛：不过不许进下一门。
- `[S]` 软项：建议做，不阻塞。
- `[O]` 可选：视产品形态决定。

每一项后面括号里是依据来源，完整 URL 见 `references.md`。

---

## 阶段一：Pre-launch（T-14 → T-1）

### 门 1 · Ready —— 出事能发现、能回滚、能恢复

依据：Google SRE Launch Coordination Checklist（精简到小团队够用的子集）、Vercel / Next.js Production Checklist。

**环境与密钥**
- [ ] `[H]` 生产与测试环境完全隔离：独立数据库、独立密钥、独立第三方账号（Stripe / 邮件 / 分析）
- [ ] `[H]` 代码里零硬编码密钥，全部走环境变量或 secrets vault；`grep -r "sk_live\|sk_test" src/` 为空
- [ ] `[H]` staging 的 `noindex` / `Disallow: /` 不会带进生产（这是 SEO 上线第一杀手，见门 4）
- [ ] `[S]` 环境变量用 schema 校验（如 Zod），缺变量时启动即失败而不是运行时才炸

**可观测**
- [ ] `[H]` 健康检查端点（`/api/health` 或同等）返回 200，并接入部署平台的 health check
- [ ] `[H]` 错误追踪（Sentry 或同等）在生产环境上报成功，至少手动触发过一次
- [ ] `[H]` 核心路径有结构化日志：注册、登录、下单、webhook 接收。日志里**不写卡号、不写 PII**（Stripe go-live 明文要求）
- [ ] `[S]` 5xx 率、支付失败、邮件失败三条告警能到人（手机 / 飞书 / Slack）

**可恢复**
- [ ] `[H]` 数据库有自动备份，并**做过一次真实恢复演练**（备份存在 ≠ 能恢复）
- [ ] `[H]` 有回滚手段：上一版镜像可一键回滚，或高风险功能有 feature flag 可关
- [ ] `[S]` 数据库迁移与应用启动分离（迁移失败不该把服务拖死）

**依赖与容量**
- [ ] `[S]` 列出所有第三方依赖（支付、邮件、OAuth、CDN、AI API）及其挂掉时的降级表现
- [ ] `[S]` 关键 API 有超时与重试上限；AI API 有额度告警
- [ ] `[O]` 预估 10 倍流量时最先挂的是哪一层（SRE 清单的 10x 问题），至少心里有数

**邮件与账号**
- [ ] `[H]` 生产域名发出的邮件（注册验证、密码重置、收据）能到 Gmail / Outlook / QQ 邮箱收件箱，不进垃圾箱；SPF / DKIM / DMARC 配好
- [ ] `[H]` 注册 → 验证 → 登录 → 登出 → 忘记密码，在生产域名上全链路走通

### 门 2 · Live —— 切生产：域名、密钥、webhook、法务页

依据：Stripe Go-live checklist、Paddle Go-live checklist。

**先做一个决策：谁是法律卖方（Merchant of Record）**

| 路线 | 法律卖方 | 税务申报 | 发票抬头 | 适合 |
|---|---|---|---|---|
| 直接 Stripe | 你 | 你（可加 Stripe Tax 算税，申报仍是你） | 你的公司 | B2B 定制合同、自有发票主体、复杂 Billing、已有会计 |
| Stripe Managed Payments（2026-02 起，preview 约 35 国） | Stripe | Stripe | Stripe | 已在 Stripe 生态、想少管税；注意综合费率约 6%+ |
| Paddle / Creem / Lemon Squeezy 等 MoR | 平台 | 平台 | 平台 | 全球自助 SaaS，把税务和拒付外包；费率约 5% + $0.50 |

- [ ] `[H]` 路线已定，并在 record 里写清"发票上是谁"。**这个决策上线后再换会导致客户流失，必须在有客户之前定。**

**Stripe 路线（直接接或 Managed Payments）**
- [ ] `[H]` 锁定 API version；SDK 版本与 API version 匹配
- [ ] `[H]` 沙箱对象（customer / product / price）**不能**带入 live；在 live 重建商品目录，价格 ID 的映射方式写进代码而不是硬编码
- [ ] `[H]` 换 live 密钥：`pk_live_` 进前端，`sk_live_` / `rk_live_` 进服务端环境变量
- [ ] `[H]` 单独注册 **live webhook endpoint**（test 与 live 的 endpoint 和 `whsec_` 签名密钥是分开的），验签通过
- [ ] `[H]` webhook 处理满足 Stripe 三条官方要求：**延迟到达也正确、重复到达幂等（用 `event.id` 去重）、乱序到达不出错**
- [ ] `[H]` 以 Stripe 为账本：本地订阅状态可以从 Stripe 数据完全重建
- [ ] `[H]` 卡被拒、3DS 挑战、网络超时三种失败对用户有明确提示，不是 500
- [ ] `[S]` Stripe Tax 打开并给每个 product 设 tax code；或自建税逻辑经会计确认过门槛
- [ ] `[S]` Statement descriptor 设成客户认得出的名字（降低拒付）
- [ ] `[S]` 退款路径确认：Dashboard 退款、API 退款、部分退款、余额不足时 pending 的处理
- [ ] `[S]` 订阅生命周期：取消、降级、欠费重试（dunning）、试用到期邮件

**Paddle / 同类 MoR 路线**
- [ ] `[H]` 账户审批通过，**域名验证**完成（localhost 和未验证域名不能 live）
- [ ] `[H]` sandbox → live：设置镜像、商品目录在 live 重建、换 API key 与 API 主机
- [ ] `[H]` 新建 live notification destination 并验签
- [ ] `[H]` 含税 / 不含税默认值定好（B2B 常不含税）
- [ ] `[H]` 打款账户、最低打款额、税务品类审批完成

**法务与合规页**
- [ ] `[H]` Terms of Service、Privacy Policy、Refund Policy、Cookie / 同意（按用户所在地 GDPR / CCPA）四页上线，footer 可达
- [ ] `[H]` Refund Policy 与支付平台实际行为一致（MoR 可能在 60 天内自行退款以防拒付，"不退款"写了也没用）
- [ ] `[H]` 联系邮箱 / 支持入口真的有人收
- [ ] `[S]` 数据处理与子处理方（Stripe / Paddle / 邮件 / 分析）在隐私政策里列出
- [ ] `[S]` EU B2B：checkout 能收 VAT 号，发票合规；MoR 代开还是你自开，checkout 文案要一致
- [ ] `[S]` 试用转付费前有邮件提醒，取消入口一键可达（多国消费法规要求）
- [ ] `[O]` PCI：用托管 Checkout（Stripe Checkout / Paddle.js）走轻量 SAQ；自建卡表则责任陡增，小团队不要自建

**域名与证书**
- [ ] `[H]` 生产域名 DNS 指向正确，HTTPS 证书自动续期
- [ ] `[H]` `www` 与裸域、`http` 与 `https` 单向 301，只有一个 canonical 主机名
- [ ] `[S]` 旧域名 / 旧路径（如有）301 到新地址

### 门 3 · Paid —— 一张真卡走完整个钱的回路

依据：自建。这是 LaunchLoop 相对业界清单最独有的一道门：Stripe 的清单只到"webhook 注册好"，不管你的权益有没有真的开。

- [ ] `[H]` 用**真卡、真金额**（可以是最低档）在生产环境走一遍：
  1. 下单成功，Stripe / Paddle 后台看到 live 交易
  2. webhook 到达，本地权益（订阅状态 / 额度 / 功能开关）**自动**开通，不靠人工
  3. 用户收到收据 / 发票邮件，抬头与门 2 决策一致
  4. 后台发起退款，webhook 到达，权益**自动**回收或按策略保留到期末
  5. 用户自助取消订阅，下期不再扣款
- [ ] `[H]` 上一步每个环节的截图或日志贴进 `records/`
- [ ] `[H]` 用**欧洲卡**（或 Stripe 的 3DS 测试卡在 live 等价路径）走一遍，确认 SCA / 3DS 挑战不会静默失败——这是欧洲转化率杀手
- [ ] `[S]` 对账：webhook 成功 ≠ 钱已结算。看一次 payout 记录，知道钱多久到账
- [ ] `[S]` 拒付（chargeback）流程：谁收到通知、多少天内要回应、证据从哪里导出
- [ ] `[O]` 本地化 checkout：目标市场的本币显示和本地支付方式（如巴西 / 印度 / 中国大陆能翻倍转化）

### 门 4 · Found —— Google 能索引，AI 爬虫放行，关键页可引用

依据：Google Search Essentials、Google "AI Features and Your Website"、OpenAI 爬虫文档、Princeton GEO 论文、2026 年 Ahrefs 数据。
这道门是 BF Labs 自己的 GEO 产品线（`bflabs-agent-readiness`、`bflabs-geo`）在 LaunchLoop 里的落点，见 README "与 BF Labs GEO 资产的关系"。

**传统 SEO 硬门槛**
- [ ] `[H]` 生产 `robots.txt` 没有 `Disallow: /`；关键页没有 `noindex`（用 `curl -I` 和查看源码双重确认）
- [ ] `[H]` `sitemap.xml` 可访问、只含 200 页面、已在 Google Search Console 提交
- [ ] `[H]` Google Search Console 与 Bing Webmaster Tools 完成域名验证（Bing 是 ChatGPT 搜索和 Copilot 的索引来源）
- [ ] `[H]` 每个关键页有唯一 `<title>`、`<meta description>`、`canonical`、一个 `<h1>`、`lang` 属性
- [ ] `[H]` 关键页（首页、定价、功能、文档入口）**服务端渲染出可读文本**；禁用 JS 后仍能看到正文。大多数 AI 爬虫不渲染 JS
- [ ] `[S]` Core Web Vitals 绿色；Lighthouse 移动端 > 90
- [ ] `[S]` Open Graph / Twitter Card 齐，分享出去有图有标题

**GEO 第一档：上线日硬门槛**
- [ ] `[H]` `robots.txt` 明确放行你想出现的 AI 搜索爬虫。至少：`OAI-SearchBot`（ChatGPT 搜索结果，不放行就不出现）、`PerplexityBot`、`ClaudeBot`、`Google-Extended`、`Bingbot`
- [ ] `[H]` **单独决策** `GPTBot`（训练用，不影响 ChatGPT 搜索引用）是否放行，并记录理由
- [ ] `[H]` JSON-LD 结构化数据：`Organization`（含 logo、sameAs 社交链接）、`SoftwareApplication` 或 `Product`（含定价）、有 FAQ 的页面加 `FAQPage`。**内容必须与页面可见文本一致**（Google 明文要求）。Google 2023 年弃用了 FAQ 富摘要，但 AI 引擎仍在解析 `FAQPage`
- [ ] `[H]` 关键页每个 H2 下的第一段是 30–90 字的**直接回答**，能独立成句被摘走（ChatGPT / Perplexity / AI Overviews 都优先抽这一段）
- [ ] `[H]` 有一页"可引用的一页纸"：产品是什么、给谁用、不给谁用、定价、与主要替代品的对比。AI 和人类都要能直接摘
- [ ] `[H]` `/llms.txt` 放在站点根目录：H1 站名 + 一段 30–60 字描述 + 按 H2 分组的 20–80 个关键 URL（定价、文档、关于、可引用一页纸），每条一句话说明；所有 URL 绝对路径且返回 200；Content-Type 为 `text/plain` 或 `text/markdown`；不被 `robots.txt` 拦；`robots.txt` 里加一行 `# LLM directory: https://<domain>/llms.txt`。**团队决策：必选。** 依据不是排名（Google 官方不读它，Ahrefs 2026-06 数据 97% 零请求），而是它是给 agent / RAG / AI IDE 的导览目录，成本十分钟，且我们自己的 Agent Readiness 扫描器会检查它——我们卖给别人的东西自己不能不做
- [ ] `[O]` `/llms-full.txt` 或关键页 `.md` 镜像（文档站建议做）

**GEO 第二档：上线后 4–12 周的持续工作**（见阶段三）

**用什么工具跑这道门**
- `bflabs-agent-readiness`（`geo-discover` 子 Skill 或 readiness.bflabs.cn）：对生产域名跑一次扫描，Discoverable / Understandable / Actionable 三轴全部 pass 即视为本门 GEO 硬门槛通过；扫描报告贴进 record
- `bflabs-geo` MCP（geo.bflabs.app）：`geo_diagnose` → `geo_guidance` 给出修复任务，改完 `geo_record_implementation` 留证据
- [ ] `[O]` `webmcp-enable` 子 Skill：让 Agent 能直接操作你的站（WebMCP）。这是 Found 之上的一层——不只是被读懂，还能被调用；SaaS 有 API 的建议做

### 商业准备
- [ ] `[H]` 定价页上线，价格与 Stripe / Paddle 后台一致
- [ ] `[H]` 支持渠道明确：邮箱、飞书 / Discord / Crisp 任一，且有人值
- [ ] `[H]` 分析事件能打到：`signup` → `activate`（用到核心功能一次）→ `pay`。用 PostHog / Plausible / GA4 任一
- [ ] `[S]` 状态页（或至少一个专门发状态的 X / 飞书账号）
- [ ] `[S]` 发布物料：一条 X 线程、一张产品截图、一段 30 秒视频、Product Hunt 页面草稿
- [ ] `[S]` 上线日 owner 表：谁盯支付与登录、谁回评论、谁有回滚权限

---

## 阶段二：Launch（当天）

原则：**当天只做分发和盯盘，不临场改计费、不改 schema、不换密钥。**

**开闸前 30 分钟**
- [ ] `[H]` 抽查 10 个关键 URL：HTTP 200、无 `noindex`、canonical 正确、结构化数据用 Rich Results Test 通过
- [ ] `[H]` `robots.txt` 与 `sitemap.xml` 线上再看一眼
- [ ] `[H]` Live 支付再走一单（可退款）
- [ ] `[H]` 监控大屏打开：5xx 率、支付失败、webhook 失败队列、邮件退信、注册数

**分发**
- [ ] 按物料顺序发：X 线程 → Product Hunt / Hacker News（如做）→ 社群 → 邮件列表
- [ ] 产品**必须已经能注册 + 付钱**再发；不要"先发帖再补支付"
- [ ] 一人专职回评论，一人专职看后台，两人不重叠

**当天异常处理**
- [ ] 支付失败率突增 → 先看 webhook 失败队列和 Stripe Dashboard 的 decline 原因，再动代码
- [ ] 5xx 突增 → 先回滚，再排查
- [ ] Google 突然抓不到 → 查 `robots.txt` 和 CDN / WAF 是否把 Googlebot 当 bot 拦了

---

## 阶段三：Post-launch（D1 → D30，然后进入常态）

### 稳定（D1–D3）
- [ ] `[H]` 前 72 小时每天看：Search Console 抓取异常与"已发现-未索引"、Stripe / Paddle webhook 失败队列、退信率、错误追踪新增 issue
- [ ] `[H]` 第一个完整计费周期内（月付则 30 天）有人值班到续费扣款成功
- [ ] `[S]` 拒付 / 退款响应 SLA 定下来（如 24 小时内回）

### 被找到（D3–D30，GEO 第二档）
- [ ] `[S]` 建一份 canonical prompt 目录：5–10 个你的品类问题（如"best X for Y"、"X 多少钱"），措辞固定不改。用 ChatGPT、Perplexity、Gemini、Google AI Mode 各跑一遍，记录：有没有提到你、引用的是哪个 URL、事实与价格对不对。D7 首测存进 record，之后至少每月复测（BeefAPI 实践为每周）。采样规则沿用 BeefAPI GEO 目录：只接受平台真实联网回答，每平台每题最多 3 个独立新会话，prompt 与目录不一致的结果只能当旁证不进基线。工具：`bflabs-agent-readiness` 的 `geo-measure`，或 `bflabs-geo` 的 `geo_retest` + 导入真实 AI 回答
- [ ] `[S]` 传统 SEO 内容：帮助中心、"X vs Y" 对比页、"X alternative" 页、用例页。这些同时是 GEO 的引用原料——Princeton GEO 论文的结论是加**引用、统计数据、权威表述**能提升 30–40% AI 可见度，本质是内容工作。工具：`geo-content` / `seo-plan` 子 Skill
- [ ] `[S]` 第三方提及：相关 subreddit 的真实参与、独立评测、目录站（如 G2 / AlternativeTo）、Show HN。**Reddit 不保证可见度，但正负面提及会直接影响 AI 里的品牌情绪**
- [ ] `[O]` 内链：从高流量页链向定价与对比页
- [ ] 不做：编辑 Wikipedia（新站既不现实也不合规）；买"LLM 专用 schema"；签说不清 KPI 的 GEO retainer

### 增长与回流
- [ ] `[S]` 周复盘：注册、激活、付费、退款、来源渠道五个数
- [ ] `[S]` AI 来源归因：把 referrer 含 chatgpt.com / perplexity.ai / gemini.google.com 等的访问、注册、付费单独打标，与 canonical prompt 复测结果并排看。**表述边界（沿用 BeefAPI 归因看板的规则）：可以说"做完 GEO 后出现 N 笔来自 AI referrer 的订单"，不能说"GEO 带来了收入"，除非有归因证据；可以说"0 投流"，不能说"0 成本"。** 工具：`bflabs-geo` 的业务事件导入 + `geo_report`
- [ ] `[H]` D30 复盘写回 `records/`，把踩到的坑回流到本文件
- [ ] `[H]` 把本次通过的 Ready + Live 子集整理成后续发布的 Definition of Done，小版本只跑子集

---

## 硬门槛速查（打印版）

进入下一门前，这些必须全绿：

**Ready**：环境隔离 · 零硬编码密钥 · staging noindex 不进生产 · 健康检查 · 错误追踪 · 核心日志无 PII · 备份且演练过恢复 · 可回滚 · 邮件可送达 · 账号全链路通
**Live**：MoR 决策已定 · live 密钥 · live webhook 验签 · webhook 延迟/重复/乱序三条通过 · 以支付平台为账本 · 失败提示友好 · 四页法务 · 退款政策与平台一致 · 支持邮箱有人 · HTTPS 与单一 canonical 主机
**Paid**：真卡走完 买→开权益→发票→退款→取消 · 有截图 · 欧洲卡 3DS 通过
**Found**：robots 无误拦 · sitemap 已提交 · GSC + Bing 验证 · title/canonical/h1 · 关键页 SSR 文本 · AI 爬虫放行 · GPTBot 单独决策 · JSON-LD 与可见文本一致 · H2 下 30–90 字直接回答 · 可引用一页纸 · llms.txt · Agent Readiness 扫描三轴 pass · 定价页与后台一致 · 支持渠道 · signup→activate→pay 事件
**Launch 当天**：10 URL 抽查 · live 再走一单 · 监控大屏
**Post-launch**：72 小时盯盘 · 值班到第一次续费 · D30 复盘回流 · 整理成发布 DoD
