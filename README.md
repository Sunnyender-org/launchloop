# LaunchLoop（上线闭环）

> Deploy 不等于 Launch。上线的终点不是"网站能打开"，而是**有人付了钱、有人搜到你、AI 会引用你**。

LaunchLoop 是一套面向小团队（独立开发者 / 小型创业公司，产品多为 SaaS 或 Web 产品）的产品上线 SOP。它把业界原本分散在三个领域的成熟清单拼成一条完整回路：

| 业界现有叫法 | 覆盖范围 | 出处 |
|---|---|---|
| Production Readiness Review (PRR) / Launch Coordination Checklist | 工程与运维：服务能否长期扛线上流量 | Google SRE Book 第 27 章 + 附录 E |
| Go-Live Checklist | 从测试环境切到生产，尤其是支付 | Stripe / Paddle 官方文档 |
| Go-To-Market (GTM) Plan / Launch Plan | 商业与营销：谁买、怎么卖、怎么被发现 | Product Hunt、YC |

这三条线各自成熟，但**没有任何一份权威清单同时覆盖支付、法务、SEO、GEO 和运维**，GEO（生成式引擎优化，让 ChatGPT / Perplexity / Google AI 引用你）更是没被任何一份 launch checklist 纳入。LaunchLoop 就是填这个空。

## 四道门 + 一个回路

```
 Ready ──► Live ──► Paid ──► Found ──► Loop ──┐
 能扛      切生产    第一笔钱   被搜到/被引用  运营复盘   │
   ▲                                                    │
   └────────────────── 下次发布复用子集 ◄───────────────┘
```

| 门 | 一句话判定标准 | 硬门槛依据 |
|---|---|---|
| **Ready** | 出事能发现、能回滚、能恢复 | SRE Launch Coordination Checklist 精简版 |
| **Live** | 生产域名、生产密钥、生产 webhook、法务页齐 | Stripe / Paddle Go-live checklist |
| **Paid** | 一张真卡走完 买 → 开权益 → 发票 → 退款 → 取消 | 自建一页支付烟测 |
| **Found** | Google 能索引，AI 爬虫放行，关键页有可引用文本和结构化数据 | Google Search Essentials + GEO 硬门槛 |
| **Loop** | 前 72 小时有人盯，D30 有复盘，清单回流成发布 DoD | — |

每道门有 **硬门槛**（不过不许上）和 **软项**（建议做、不阻塞）。GEO 在 Found 门里分两档：上线日硬门槛（含 `llms.txt`，团队决策必选）和上线后 4–12 周的持续工作。

## 与 BF Labs GEO 资产的关系

LaunchLoop 是流程，不是工具。我们已有的三份 GEO 资产分别接在流程的不同位置：

| 资产 | 是什么 | 在 LaunchLoop 的位置 |
|---|---|---|
| [`bflabs-agent-readiness`](https://github.com/Sunnyender-org/bflabs-agent-readiness)（公开） | 网站 AI 就绪度扫描器 + 六个子 Skill（`geo-discover` / `geo-optimize` / `geo-content` / `geo-measure` / `seo-plan` / `webmcp-enable`）+ readiness.bflabs.cn 诊断站 | **Found 门的自动化检查器**。`geo-discover` 扫一次生产域名，三轴 pass 即 Found 门 GEO 硬门槛通过；`geo-optimize` 修上线日硬门槛；`geo-content` / `seo-plan` 是 Post-launch 内容工作；`geo-measure` 跑 AI 可见度复测；`webmcp-enable` 是 Found 之上的可选层 |
| `bflabs-geo`（私有，geo.bflabs.app MCP） | 在用户自己的 Agent 里跑的 GEO 服务：`geo_diagnose` → `geo_guidance` → `geo_record_implementation` → `geo_retest` → `geo_report`，并可导入真实 AI 回答与业务事件 | **Found 门 + Post-launch "被找到" + Loop 归因的执行闭环**。diagnose / guidance 对应 Pre-launch 修门槛；retest 对应 Post-launch 复测；业务事件导入与 `geo_report` 对应 Loop 里的 AI 来源归因 |
| BeefAPI 自身的 GEO 实践 | canonical prompt 目录、周度多平台真实联网采样、归因看板（0 投流、5 位付费用户、归因收入 ¥899.40） | **Post-launch 第二档 + Loop 的第一个实例**。LaunchLoop 里的采样规则（prompt 固定、只接受真实联网回答、每平台最多 3 会话）和归因表述边界（能说"做完 GEO 后出现订单"，不能说"GEO 带来收入"）都直接沿用它 |

一句话：**Agent Readiness 是 Found 门的 linter，bflabs-geo 是 Found 到 Loop 的执行器，BeefAPI 是第一个跑完整条回路的案例。** LaunchLoop 补的是它们前面的 Ready / Live / Paid 三道门，以及把 GEO 放回整个上线流程里的位置。

## 文件

| 文件 | 用途 |
|---|---|
| [`LAUNCHLOOP.md`](./LAUNCHLOOP.md) | 主清单。按 Pre-launch / Launch / Post-launch 三阶段、四道门展开 |
| [`templates/launch-record.md`](./templates/launch-record.md) | 每次上线复制一份，填 owner、go/no-go、烟测记录 |
| [`references.md`](./references.md) | 所有依据的来源与 2026 年调研结论，含哪些说法不可信 |

## 怎么用

1. 新产品或大版本上线前 14 天，复制 `templates/launch-record.md` 到 `records/<产品名>-<日期>.md`。
2. 按 `LAUNCHLOOP.md` 逐门过，硬门槛全部勾完才进下一门。
3. 上线日只做分发和盯盘，不临场改计费。
4. D30 复盘写回 record，把这次踩到的坑回流到 `LAUNCHLOOP.md`。
5. 后续小版本发布只需复用 Ready + Live 的支付 / 监控子集。

## 边界

- 这是**小团队自助 SaaS / Web 产品**的 SOP。销售驱动的 B2B 大客户、移动 App Store 上架、硬件生产不在范围。
- 清单是活文档，随每次上线复盘更新。来源与结论的时效见 `references.md`。
