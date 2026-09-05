# 安全响应头模板（R01）

四个头，按框架选一种加法。第一次加 HSTS 不要带 `preload`。

目标：

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY            # 或 CSP 的 frame-ancestors 'none'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

CSP 单独考虑：先用 `Content-Security-Policy-Report-Only` 跑两周，看 report 再切正式，否则会把第三方脚本（支付、分析）全弄坏。

## Next.js（next.config.js / .ts）

```js
const securityHeaders = [
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];
module.exports = {
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};
```

如果站点需要被嵌入（比如你提供 embed widget），对那条路由单独覆盖 `X-Frame-Options`，不要全站放开。

## 静态站（Astro / Vite）在 Cloudflare Pages / Netlify：`public/_headers`

```
/*
  Strict-Transport-Security: max-age=31536000; includeSubDomains
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
```

Vercel 静态站用 `vercel.json` 的 `headers` 字段，结构同 Next.js。

## Nginx

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

# 顺手修 R02：拒绝点开头路径，但放行 .well-known
location ~ /\.(?!well-known) { deny all; return 404; }
```

## Cloudflare Worker

```js
const SECURITY = {
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
};
export default {
  async fetch(req, env, ctx) {
    const res = await handle(req, env, ctx);
    const out = new Response(res.body, res);
    for (const [k, v] of Object.entries(SECURITY)) out.headers.set(k, v);
    return out;
  },
};
```

## 验证

```bash
curl -sI https://domain | grep -iE "strict-transport|x-content-type|x-frame|referrer-policy|content-security"
```
