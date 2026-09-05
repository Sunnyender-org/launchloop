# 限流与花费上限模板（S05）

两层缺一不可：**代码限流**挡住单个滥用者，**平台花费上限**挡住你没想到的滥用方式。vibe coded 站被刷额度的事故里，几乎都是两层都没有。

## 第一层：平台硬上限（人做，五分钟，M05）

| 平台 | 路径 |
|---|---|
| OpenAI | platform.openai.com → Settings → Organization → Limits → **Monthly budget**（设 hard limit，不只是 alert） |
| Anthropic | console.anthropic.com → Plans & billing → **Spend limit** |
| Google AI Studio / Vertex | Cloud Console → Billing → Budgets & alerts（Vertex 只能告警，不能硬停；配合下面的代码限流） |
| Resend / Postmark | 账户默认有日发送上限，确认数字 |
| Twilio | Console → Billing → Usage triggers |
| Replicate / fal | 账户 Spend limit |

金额定成"正常用量的 3 倍"，不是无限。撞上限宁可服务降级也别让账单飞。

## 第二层：代码限流

原则：按 IP 一条（挡匿名刷），按用户一条（挡登录后刷），匿名额度远低于登录用户；只对昂贵端点做，不对整站做。

### Next.js middleware + Upstash Ratelimit

```ts
// middleware.ts
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";
import { NextResponse, type NextRequest } from "next/server";

const redis = Redis.fromEnv(); // UPSTASH_REDIS_REST_URL / _TOKEN，服务端变量，不带 NEXT_PUBLIC_
const byIp = new Ratelimit({ redis, limiter: Ratelimit.slidingWindow(10, "1 m"), prefix: "rl:ip" });
const byUser = new Ratelimit({ redis, limiter: Ratelimit.slidingWindow(60, "1 h"), prefix: "rl:user" });

const EXPENSIVE = ["/api/generate", "/api/chat", "/api/upload"];

export async function middleware(req: NextRequest) {
  if (!EXPENSIVE.some((p) => req.nextUrl.pathname.startsWith(p))) return NextResponse.next();

  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  const ipRes = await byIp.limit(ip);
  if (!ipRes.success) return tooMany(ipRes.reset);

  const userId = req.cookies.get("uid")?.value; // 或从 session 解析
  if (userId) {
    const uRes = await byUser.limit(userId);
    if (!uRes.success) return tooMany(uRes.reset);
  }
  return NextResponse.next();
}

function tooMany(reset: number) {
  return new NextResponse(JSON.stringify({ error: "rate_limited" }), {
    status: 429,
    headers: { "Content-Type": "application/json", "Retry-After": String(Math.ceil((reset - Date.now()) / 1000)) },
  });
}

export const config = { matcher: ["/api/:path*"] };
```

### Cloudflare Worker（KV 计数，无外部依赖）

```js
async function limit(env, key, max, windowSec) {
  const now = Math.floor(Date.now() / 1000);
  const bucket = `${key}:${Math.floor(now / windowSec)}`;
  const n = Number((await env.RL.get(bucket)) ?? 0) + 1;
  await env.RL.put(bucket, String(n), { expirationTtl: windowSec * 2 });
  return n <= max;
}
// 在 fetch 里：if (!(await limit(env, `ip:${ip}`, 10, 60))) return new Response("rate_limited", { status: 429 });
```

KV 是最终一致，允许少量超发；要精确用 Durable Object。

### Python（FastAPI + slowapi）

```python
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/generate")
@limiter.limit("10/minute")
async def generate(request: Request): ...
```

## 还要做的三件小事

1. **匿名用户的免费额度用服务端计数**，不要用 localStorage——清一下缓存就重置了。
2. **AI 调用设 `max_tokens` 上限**并截断用户输入长度；一次请求的最坏花费要可算。
3. **超限时返回 429 并带 `Retry-After`**，前端显示"稍后再试"，不要静默失败。

## 验证

```bash
for i in $(seq 1 15); do curl -s -o /dev/null -w "%{http_code} " -X POST https://domain/api/generate -H "content-type: application/json" -d '{}'; done; echo
# 期望：前 10 个 200/400，之后 429
```
