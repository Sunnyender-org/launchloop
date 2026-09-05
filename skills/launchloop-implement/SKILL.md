---
name: launchloop-implement
description: Fix the failures reported by launchloop-check inside the user's own repository, one check ID at a time, using the recipes in references/fixes.md and the files in templates/. Use when the user has a launchloop-check report (or names a check ID such as F08, S03, R02) and asks to fix, implement, add, or repair it before launch. Not for diagnosis (use launchloop-check), for writing legal text or choosing a payment provider on the user's behalf, for rotating leaked secrets, for GEO content strategy (use bflabs-agent-readiness geo-content), or for commit / push / deploy.
metadata:
  short-description: Apply LaunchLoop fixes in the repo, one check ID at a time
  sunny_skill_type: contract
---

# LaunchLoop Implement

把 `launchloop-check` 报告里的 FAIL 变成 PASS。每个检查 ID 对应 `references/fixes.md` 里的一条修法和 `templates/` 里的一个模板。改动只发生在用户自己的仓库里，最小、可验证、可回滚。

## 输入

任一：
- `launchloop-check` 产出的 JSON（`records/*-check.json`）或 Markdown 报告；
- 用户直接点名的检查 ID（如 "修 F08 和 S03"）；
- 用户描述的症状（"AI 爬虫读不到我的定价页"）→ 先对应到 ID 再修。

没有报告就先让用户跑 `launchloop-check`。不要凭空猜哪里坏了。

## 工作流

1. 读最近的项目指令（AGENTS.md / CLAUDE.md / .cursor/rules）和仓库现状：框架、路由方式、部署平台、是否已有 `robots.txt` / `llms.txt` / 安全头配置。保留无关的未提交改动。
2. 按 **ID 顺序**修，一个 ID 一个改动，不合并。顺序建议：先安全（S 系列、R02），再 Found（F 系列），再 Live（L 系列）。
3. 打开 `references/fixes.md` 找到该 ID，读它指向的模板，**按检测到的框架适配**（Next.js / Astro / Vite SPA / Nuxt / Django / Rails / Cloudflare Worker），不要把 Next.js 的 `headers()` 塞进 Astro 项目。
4. 需要业务事实的地方（产品一句话描述、定价、公司名、联系邮箱、退款天数）**停下来问**，或从仓库里已有的权威来源取；不编造。
5. 改完立刻用真实接口验证：能跑就 `npm run build` / `pytest`；能起本地服务就 `curl` 一下 `/llms.txt`、`/robots.txt`、响应头。文件存在不等于线上生效。
6. 全部修完后提示用户重跑 `launchloop-check`，前后报告都留在 `records/`。

## 三类不同性质的修

| 类型 | 例子 | 本 Skill 能做到什么 |
|---|---|---|
| 纯技术 | F08 llms.txt、R01 安全头、F07 JSON-LD 骨架、S06 webhook 去重、S05 限流中间件 | 直接改到能过检查 |
| 需要业务事实 | F07 里的产品描述与价格、L03 法务页正文、F05 title 文案 | 出骨架和占位符，**事实由人填**；法务文本明确标注"非法律意见，上线前请人审" |
| 只能人做 | S02 已泄露的密钥轮换、M07 MoR 决策、M10 真卡烟测、S04 在 Supabase Dashboard 里开 RLS | 给出精确步骤和 SQL / 命令，**不代做**。密钥泄露时第一句话就是"先去轮换" |

## 硬边界

- 永不 `git commit` / `push` / 开 PR / 部署 / 改 DNS / 提交 sitemap 到搜索平台 / 联系任何人。
- 永不放宽认证、授权、CORS、CSP、支付校验，或去掉针对敏感路径的 robots 限制来"让检查过"。检查是手段，安全是目的。
- 永不把 `service_role` / secret key 挪到前端来"修" S03 报错——正确修法是把读取移到服务端。
- 修 S04 RLS 时只生成 policy SQL 供人审，不直接对生产库执行。
- 修 F02 放行 AI 爬虫时，`GPTBot`（训练用）保持用户原有决策；只在用户明确说放行时才加。
- 法务页模板只是结构骨架。写清楚：这不是法律意见。

## 输出契约

每修一个 ID，返回：

1. ID、改了哪些文件（路径）、为什么这样改（一句）。
2. 验证方式与结果（命令 + 输出摘要）。
3. 需要人补的事实或决定（如果有）。
4. 修完所有 ID 后：一句"请重跑 `launchloop-check --url ... --repo ...` 复测"。

## 邻居

- `launchloop-check`：产出本 Skill 的输入。
- `bflabs-agent-readiness` 的 `geo-optimize` / `geo-content`：Found 门 GEO 部分的深度实施（H2 下直接回答的段落、可引用一页纸的内容）。本 Skill 只负责让机器检查过线。
- `CHINA.md`：中国路径下 L03 法务页要加《个人信息保护法》与生成式 AI 标识条款，模板里有对应占位段。
