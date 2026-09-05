# 支付 webhook 幂等模板（S06）

所有支付平台（Stripe / Lemon Squeezy / Paddle / Creem）都会：**重发**同一事件、**乱序**送达、**延迟**几分钟到几天。Stripe 的 go-live checklist 明文要求 handler 处理这三种情况。做法只有一种：先验签，再用事件 ID 去重，再处理，处理逻辑本身也要能接受任何顺序。

## 1. 表

```sql
create table if not exists processed_events (
  id          text primary key,          -- 平台的 event id
  provider    text not null,             -- 'stripe' | 'lemonsqueezy' | 'paddle' | 'creem'
  type        text not null,
  received_at timestamptz not null default now()
);
```

## 2. Handler 骨架（Next.js Route Handler，Stripe）

```ts
// app/api/webhooks/stripe/route.ts
import Stripe from "stripe";
import { db } from "@/lib/db";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
export const runtime = "nodejs"; // 验签需要原始 body，不能用 edge 的 json()

export async function POST(req: Request) {
  const sig = req.headers.get("stripe-signature");
  const raw = await req.text();                       // 原始字符串，不能先 json()
  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(raw, sig!, process.env.STRIPE_WEBHOOK_SECRET!);
  } catch (e) {
    return new Response("bad signature", { status: 400 });
  }

  // 去重：插入 0 行说明处理过，直接 200
  const inserted = await db.execute(
    `insert into processed_events (id, provider, type) values ($1, 'stripe', $2) on conflict (id) do nothing`,
    [event.id, event.type]
  );
  if (inserted.rowCount === 0) return new Response("duplicate", { status: 200 });

  try {
    await handle(event);
  } catch (e) {
    // 处理失败要让平台重试：删掉去重记录再返回 5xx
    await db.execute(`delete from processed_events where id = $1`, [event.id]);
    return new Response("retry", { status: 500 });
  }
  return new Response("ok", { status: 200 });
}

async function handle(event: Stripe.Event) {
  switch (event.type) {
    case "checkout.session.completed":
    case "customer.subscription.updated":
    case "customer.subscription.deleted":
    case "invoice.payment_failed": {
      // 不要按事件内容"加减"权益。以 Stripe 为账本：
      // 拉最新的 subscription，把本地状态整体覆盖成它。这样乱序也不会错。
      const sub = await stripe.subscriptions.retrieve(subscriptionIdFrom(event));
      await upsertEntitlement(sub.customer as string, {
        status: sub.status,                        // active | past_due | canceled ...
        plan: sub.items.data[0]?.price.id,
        currentPeriodEnd: new Date(sub.current_period_end * 1000),
      });
      break;
    }
    case "charge.refunded": {
      // 按你的退款策略：立即回收，或保留到期末
      break;
    }
  }
}
```

要点：

- **以平台为账本**。本地表只是缓存；每次事件都拉最新对象整体覆盖，而不是"收到 created 就 +1、收到 deleted 就 -1"。这一条同时解决乱序和重复。
- 去重记录在处理失败时要删掉，否则平台重试会被当成重复而永久丢事件。
- 验签要用**原始 body**。Next.js 里不能先 `req.json()`。
- live 与 test 的 endpoint 和 `whsec_` 是两套；部署时用 live 的。

## 3. Lemon Squeezy 差异

```ts
import crypto from "node:crypto";
const raw = await req.text();
const sig = req.headers.get("x-signature") ?? "";
const digest = crypto.createHmac("sha256", process.env.LEMONSQUEEZY_WEBHOOK_SECRET!).update(raw).digest("hex");
if (!crypto.timingSafeEqual(Buffer.from(digest), Buffer.from(sig))) return new Response("bad signature", { status: 400 });
const event = JSON.parse(raw);
const eventId = event.meta?.webhook_id ?? `${event.meta.event_name}:${event.data.id}:${event.data.attributes.updated_at}`;
```

Lemon Squeezy 的事件没有像 Stripe 那样稳定的顶层 `id`，用 `meta.webhook_id`；没有就拼 `event_name + data.id + updated_at`。

## 4. Paddle / Creem

- Paddle Billing：`Paddle-Signature` 头，SDK `paddle.webhooks.unmarshal(raw, secret, sig)`；事件有 `event_id`。
- Creem：`creem-signature` 头（HMAC-SHA256），事件有 `id`。

## 5. 验证

```bash
stripe listen --forward-to localhost:3000/api/webhooks/stripe
stripe trigger checkout.session.completed
stripe trigger checkout.session.completed   # 第二次：日志应显示 duplicate，权益只开一次
```

Dashboard 里对任一事件点 **Resend**，本地状态不应变化。这就是 `LAUNCHLOOP.md` 门 3 里"权益自动开通"与"退款自动回收"的技术前提。
