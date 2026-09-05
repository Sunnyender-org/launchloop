# 依据与来源

调研日期：2026-09-05。由 Claude 主导、Grok 负责 X 平台检索，结论交叉验证。凡标"推断"的是综合判断，其余为可查证的事实。

## 一、为什么叫 LaunchLoop：业界没有一个词覆盖全部

| 术语 | 侧 | 覆盖 | 不覆盖 | 出处 |
|---|---|---|---|---|
| Definition of Done | 工程 / 敏捷 | 一个 Increment "做完"的质量门槛 | 收款、SEO、GTM | [Scrum Guide](https://scrumguides.org/scrum-guide.html) |
| Release Management / Release Readiness | 工程 / DevOps | 版本打包、部署、回滚 | 获客、定价 | ITIL 4（商业框架） |
| Go-Live Checklist | 工程 + 支付 | 从测试切到生产的操作 | GTM、GEO | [Stripe](https://docs.stripe.com/get-started/checklist/go-live)、[Paddle](https://developer.paddle.com/build/go-live-checklist) |
| Production Readiness Review (PRR) | 工程 + 运维 | 服务能否长期扛流量：SLO、监控、容量、on-call | 营销、定价 | [Cortex](https://www.cortex.io/post/how-to-create-a-great-production-readiness-checklist)、[DX](https://getdx.com/blog/production-readiness-checklist/) |
| Operational Readiness Review (ORR) | 运维 | 系统 / 人员 / 流程是否可交接运行 | 航天 / 政府色彩重 | [NASA SWEHB](https://swehb.nasa.gov/spaces/7150/pages/16449865/7.09+-+Entrance+and+Exit+Criteria) |
| Launch Coordination Engineering (LCE) + Launch Coordination Checklist | 运维 / SRE | 架构、容量、故障、监控、安全、发布、依赖、日程 | 支付、SEO、GEO | [SRE Book 第 27 章](https://sre.google/sre-book/reliable-product-launches/)、[附录 E](https://sre.google/sre-book/launch-checklist/) |
| Website Launch Checklist | 营销 + 技术 SEO | 域名、HTTPS、robots、sitemap、GSC | 支付幂等、税务 | 各 SEO 机构，无官方版 |
| Go-To-Market (GTM) Plan / Launch Plan | 商业 | 谁买、为何买、渠道、定价 | 部署、webhook、税务 | [Product Hunt Launch Guide](https://www.producthunt.com/launch)、[YC Library](https://www.ycombinator.com/library) |
| Pre-launch / Launch / Post-launch | 全公司 | 时间轴分期框架 | 它不是检查项本身 | 通用 |

注意：软件圈说的 PRR 与国防采办的 PRR（[DAU](https://aaf.dau.edu/aaf/mca/prr/)，硬件量产评审）同名不同物。

**结论（事实）**：SRE 不管税，Stripe 不管 SEO，Google 不管 webhook 幂等，Product Hunt 不管回滚。没有任何一份权威清单同时覆盖支付 + 法务 + SEO + GEO + 运维。
**结论（推断）**：短期内也不会出现，因为责任主体、约束源、产品形态都不同。小团队的正确做法是自己维护一份拼装 SOP，用阶段当目录，用各领域权威清单当附录。LaunchLoop 就是这份拼装。

## 二、各门的权威来源

### 门 1 · Ready
- Google SRE Book, Chapter 27 "Reliable Product Launches at Scale" — <https://sre.google/sre-book/reliable-product-launches/>
- Google SRE Book, Appendix E "Launch Coordination Checklist"（2005 年原版，仍公开）— <https://sre.google/sre-book/launch-checklist/>
- Vercel Production Checklist（运营 / 安全 / 可靠 / 性能 / 成本五支柱）— <https://vercel.com/docs/production-checklist>
- Next.js Production Checklist — <https://nextjs.org/docs/app/guides/production-checklist>

### 门 2 · Live
- Stripe Go-live checklist — <https://docs.stripe.com/get-started/checklist/go-live>
  官方要求原文：注册 live webhook；确认生产 endpoint "handles delayed webhook notifications, handles duplicate webhook notifications, doesn't require event notifications to occur in a specific order"。
- Stripe API keys（sandbox vs live，webhook 签名密钥独立）— <https://docs.stripe.com/keys>
- Stripe Webhooks — <https://docs.stripe.com/webhooks>
- Stripe Tax — <https://docs.stripe.com/tax>
- Stripe Refunds — <https://docs.stripe.com/refunds>
- Paddle Go-live checklist — <https://developer.paddle.com/build/go-live-checklist>
- Paddle: What is a Merchant of Record — <https://www.paddle.com/blog/what-is-merchant-of-record>
- PCI SSC — <https://www.pcisecuritystandards.org/>

**MoR 格局（2026 年 9 月）**
- Stripe 于 2026 年 2 月推出 Stripe Managed Payments（自营 MoR）：Checkout 一个参数切换，标准手续费之上再加 3.5%，public preview 约 35 国。二手来源：<https://appstackbuilder.com/blog/stripe-vs-lemon-squeezy-vs-paddle>，请以 Stripe 官方产品页为准。
- Lemon Squeezy 2024 年被 Stripe 收购，2026 年仍运营，但被定位为迁移到 Managed Payments 的入口。
- Paddle / Lemon Squeezy 费率约 5% + $0.50；MoR 与直接 Stripe 的成本交叉点大约在 $200–500K ARR。二手综述：<https://fungies.io/global-saas-launch-payments-checklist-2026/>
- Creem 定位偏 indie 的 MoR（<https://docs.creem.io/>），未找到与 Stripe / Paddle 同级的官方 go-live 清单；第三方博客上的费率数字未经确认。

### 门 3 · Paid
自建。灵感来自 Stripe go-live 只覆盖到 "webhook 注册好"，不检查权益是否真的开通；以及 fungies.io 2026 清单里 "test with European cards before launch — SCA/3DS catches most founders off guard" 的提醒。

### 门 4 · Found
- Google Search Essentials — <https://developers.google.com/search/docs/essentials>
- Google SEO Starter Guide — <https://developers.google.com/search/docs/fundamentals/seo-starter-guide>
- Google "AI Features and Your Website"（官方口径：出现在 AI Overviews / AI Mode 无额外技术要求）— <https://developers.google.com/search/docs/appearance/ai-features>
- Google 结构化数据 — <https://developers.google.com/search/docs/appearance/structured-data>
- OpenAI 爬虫文档（区分 OAI-SearchBot / GPTBot / ChatGPT-User）— <https://developers.openai.com/api/docs/bots>
- llms.txt 提案（Answer.AI / Jeremy Howard）— <https://llmstxt.org/>
- Princeton GEO 论文 "GEO: Generative Engine Optimization"（KDD 2024；引用、统计、权威表述提升最高约 40% 可见度，实验环境结果）— <https://arxiv.org/abs/2311.09735>
- web.dev Core Web Vitals — <https://web.dev/learn/performance/why-speed-matters>

**GEO 2026 年证据链**
- Ahrefs 2026-06：137,000 个站点中 97% 的 llms.txt 一个月零请求。转述：<https://nogood.io/blog/technical-aeo/>
- Google 官方：Search 不使用 llms.txt，放了既不帮也不害。报道：<https://searchengineland.com/google-says-llms-txt-files-wont-harm-or-help-your-search-rankings-480264>
- Ahrefs：被 AI Overviews 引用的页面与自然排名前 10 的重叠，从 2025-07 的 76% 降到 2026-02 的 38%。转述：<https://aicitationmonitor.com/blog/generative-engine-optimization-guide>
  推断：这意味着 "SEO 做好就自动有 GEO" 的官方口径正在过期，GEO 需要独立一条线。
- 大多数 AI 爬虫不渲染 JS，SSR 是硬要求。爬虫对照：<https://www.searchforged.com/aeo-encyclopedia/technical-aeo/technical-aeo-basics>
- FAQPage schema：Google 2023 年弃用富摘要后多数 SEO 停用，但 AI 引擎仍在解析，形成引用优势。<https://ranki.io/blog/aeo-checklist-2026-complete-guide>

**X 上的 2026 年共识与争议（Grok 检索）**
- Pieter Levels 2026-04-27："llms.txt did indeed turn out to be complete bullshit" — <https://x.com/levelsio/status/2048703164807868455>
- Ross Simmonds 2026-08-09：Google 说 AI search optimization 仍回到 SEO 基本功 — <https://x.com/TheCoolestCool/status/2086248612909257028>
- Juan Auriti 2026-08-25：llms.txt 不是 ranking factor；真正的栈是 access → orientation → schema → quotable content — <https://x.com/JuanAuriti/status/2092152497804575067>
- Harpreet 2026-06-25：25 条 "别浪费钱"，没人证明 llms.txt 或 LLM 专用 schema 有 ROI；Reddit 提及影响 AI 里的品牌情绪 — <https://x.com/harpreetchatha_/status/2069991843367198774>
- Lenny Rachitsky × Ethan Smith (Graphite)：AEO 战术里常提 Reddit、YouTube、落地页、help center — <https://x.com/lennysan/status/1967307346692239421>
- 姚金刚 2026-09-05：数智峰会现场调研约 95% 企业未系统部署 GEO — <https://x.com/yaojingang/status/2096069797704548760>

**团队决策：`llms.txt` 为硬门槛（2026-09-05）**
证据上它不是排名因子（见上），但决策依据是：它服务的是 agent / RAG / AI IDE 而不是搜索排名；成本十分钟；`bflabs-agent-readiness` 扫描器检查它，我们卖给客户的标准自己必须先达到。这是价值判断，不是证据推翻——如果未来数据显示 AI 平台开始大规模抓取，只是让这个决策更划算。

**不可信的说法（不要写进 SOP）**
- "放了 llms.txt 就能立刻进 ChatGPT / Claude / Perplexity"（与 OpenAI 官方 bot 文档和 Google 口径冲突；我们把它设为必选是因为它便宜且服务 agent，不是因为它能带来引用）
- "LLM 专用 schema"（无公开 ROI 证据）
- 把编辑 Wikipedia 当上线必做（新站不现实且不合规）
- 各 SEO 机构的 "43 点上线清单"（可参考，权威性远低于 SRE / Stripe / Google）

## 三、方法与局限
- 检索面：公开 Web（SRE / Stripe / Paddle / Vercel / Next.js / Google Search Central / OpenAI / llmstxt.org / arXiv）+ X 平台关键词与语义检索。
- 未拿到：ITIL 全文（商业授权）；Lemon Squeezy 旧 going-live 页已 404；Perplexity 官方 bot 文档抓取失败；Creem 文档为 JS 应用未能完整抽取。
- 时效：MoR 费率与 Stripe Managed Payments 覆盖国家变化快，每次上线前以官方页面复核。
