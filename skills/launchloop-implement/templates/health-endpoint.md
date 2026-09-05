# 健康检查端点模板（R03）

只回答一个问题：这个实例现在能服务吗。查数据库连通和关键依赖，不返回任何内部信息（版本号可以，配置、环境变量、连接串不行）。

## Next.js

```ts
// app/api/health/route.ts
import { db } from "@/lib/db";
export const dynamic = "force-dynamic";

export async function GET() {
  const checks: Record<string, "up" | "down"> = {};
  try { await db.execute("select 1"); checks.db = "up"; } catch { checks.db = "down"; }
  const ok = Object.values(checks).every((v) => v === "up");
  return Response.json({ ok, checks, ts: new Date().toISOString() }, { status: ok ? 200 : 503 });
}
```

## FastAPI

```python
@app.get("/api/health")
async def health():
    try:
        await db.execute("select 1"); db_ok = True
    except Exception:
        db_ok = False
    status = 200 if db_ok else 503
    return JSONResponse({"ok": db_ok, "checks": {"db": "up" if db_ok else "down"}}, status_code=status)
```

## Cloudflare Worker

```js
if (url.pathname === "/health") {
  let db = "up";
  try { await env.DB.prepare("select 1").first(); } catch { db = "down"; }
  return Response.json({ ok: db === "up", checks: { db } }, { status: db === "up" ? 200 : 503 });
}
```

## 接入

- Docker：`HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://localhost:3000/api/health || exit 1`
- Railway / Render / Fly：在服务设置里填 `/api/health`
- Vercel：无内置 health check，用外部 uptime 监控（Better Stack / UptimeRobot / Cronitor 免费档）每分钟打一次，挂了发到手机

## 不要做的

- 不要在 health 里调 AI API（花钱且慢）。
- 不要把 health 放到需要登录的路径后面。
- 不要返回 `process.env` 的任何内容。
