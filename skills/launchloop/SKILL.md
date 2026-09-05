---
name: launchloop
description: Entry point for launching a web product end to end through four gates (Ready, Live, Paid, Found) plus a post-launch loop. Use when the user wants to launch, ship, go live, or publish a website / SaaS / side project, asks what to do before or after launch, wants a launch checklist or record, or is a first-time vibe coder putting something online. Routes to launchloop-check (diagnose) and launchloop-implement (fix). Not for building the product, GEO content strategy (bflabs-agent-readiness), marketing copy, or legal / tax advice.
metadata:
  short-description: Launch a web product through Ready / Live / Paid / Found gates
  sunny_skill_type: micro
---

# LaunchLoop

Deploy 不等于 Launch。上线的终点是**有人付钱、有人搜到、AI 会引用**。本 Skill 是入口，负责问对问题、选对档、把你送到诊断或实施。

规格：仓库根目录 `LAUNCHLOOP.md`（主清单）、`CHINA.md`（中国开发者路径）、`templates/launch-record.md`（每次上线一份）。

## 先问三个问题，再做任何事

1. **收钱吗？** 不收 → Lite 档（14 项，半天）。收 → Standard 档（约 45 项，3–5 天）。第一次上线的人即使要收钱也先走 Lite。
2. **用户和服务器在哪？** 用户或服务器在中国大陆 → 同时读 `CHINA.md`，支付、备案、搜索、AI 平台都是另一条路。
3. **仓库在本机吗？** 在 → 诊断时带 `--repo`，安全检查才跑得起来。

## 路由

| 用户说的 | 去哪 |
|---|---|
| "能上线了吗" / "上线前检查" / "还缺什么" / "audit" / "复测" | `launchloop-check` |
| "修 F08" / "把 llms.txt 加上" / "帮我加限流" / "修报告里的 FAIL" | `launchloop-implement` |
| "开始一次上线" / "建 record" | 复制 `templates/launch-record.md` 到 `records/<产品>-<日期>.md`，填基本信息，然后跑 `launchloop-check` |
| "GEO 怎么做" / "AI 为什么不引用我" / 内容层面的问题 | `bflabs-agent-readiness`（`geo-discover` / `geo-content`），LaunchLoop 只管 Found 门的机器可查部分 |
| "上线当天做什么" / "上线后做什么" | 读 `LAUNCHLOOP.md` 阶段二、阶段三，不需要工具 |
| "选 Stripe 还是 Lemon Squeezy" / "个人怎么收钱" | 读 `LAUNCHLOOP.md` 门 2 的 MoR 表 + `CHINA.md` 支付一节，给对比，**决定由人做** |

## 标准流程（第一次完整走）

1. 建 record，写清产品、域名、tier、MoR 决策、四个 owner。
2. `launchloop-check --url --repo --tier` → 报告落 `records/`。
3. 硬门槛 FAIL 交给 `launchloop-implement`，一个 ID 一个改动。
4. MANUAL 项人做：真卡烟测、备份演练、花费上限、Agent Readiness 扫描。填进 record。
5. 重跑 check，前后报告都留着。
6. 上线日按 `LAUNCHLOOP.md` 阶段二：只做分发和盯盘，不改计费。
7. D1–D3 盯盘，D7 建 AI 可见度基线，D30 复盘写回 record，踩的坑回流到 `LAUNCHLOOP.md`。

## 第一次上线的 vibe coder 专用短路径

如果对方明显是第一次（一个人、Cursor/Lovable 做的、Supabase + Vercel、还没收过钱）：

1. 直接 `--tier lite`。不要先讲四道门的理论。
2. 报告出来先只看 S 系列（安全）：密钥进前端、RLS、限流。这三条不修，第二天就会出事。
3. 修完安全再修 Found 的 F 系列。
4. Lite 全绿后再谈收钱，从 Live 门补起。

## 边界

- 本 Skill 不改代码、不跑检查，只路由和解释。
- 不替人做 MoR / 主体 / GPTBot 决策，只给对比表。
- 不把"清单全绿"说成"会成功"。LaunchLoop 保证的是不死于已知死法，不保证有人买。

## 邻居

- `launchloop-check`、`launchloop-implement`：本 Skill 的两只手。
- `bflabs-agent-readiness`：Found 门 GEO 部分的深度诊断与实施。
- `bflabs-geo`（MCP）：Found 到 Loop 的执行闭环与 AI 来源归因。
