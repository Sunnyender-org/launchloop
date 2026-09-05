# 按环境控制 noindex / robots（S07 / F01 / F04）

根因永远是同一个：预发布环境的 `noindex` 或 `Disallow: /` 被硬编码，然后跟着代码一起上了生产。修法是让这两样东西**由环境变量决定**，预发布全拦，生产全放。

## 定义一个变量

不要复用 `NODE_ENV`（预发布也是 `production` 构建）。用平台给的或自定义的：

- Vercel：`VERCEL_ENV` 为 `production` / `preview` / `development`
- Cloudflare Pages：`CF_PAGES_BRANCH === "main"`
- 其他：自定义 `SITE_ENV=production|staging`，在部署平台里分别设

```ts
// lib/site-env.ts
export const isProd =
  process.env.VERCEL_ENV === "production" ||
  process.env.SITE_ENV === "production";
```

## robots meta（Next.js Metadata API）

```ts
// app/layout.tsx
import { isProd } from "@/lib/site-env";
export const metadata = {
  robots: isProd
    ? { index: true, follow: true }
    : { index: false, follow: false, nocache: true },
};
```

## robots.txt 动态生成

```ts
// app/robots.ts
import type { MetadataRoute } from "next";
import { isProd } from "@/lib/site-env";

export default function robots(): MetadataRoute.Robots {
  if (!isProd) return { rules: { userAgent: "*", disallow: "/" } };
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: ["/api/", "/admin/", "/account/"] },
      { userAgent: ["OAI-SearchBot", "PerplexityBot", "ClaudeBot", "Google-Extended", "Bingbot"], allow: "/" },
    ],
    sitemap: "https://{{DOMAIN}}/sitemap.xml",
  };
}
```

## X-Robots-Tag 头（保险，双重控制）

```js
// next.config.js — 只在非生产加
async headers() {
  if (process.env.VERCEL_ENV === "production") return [];
  return [{ source: "/(.*)", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] }];
}
```

## 静态站（Astro / Vite）

构建脚本按 `SITE_ENV` 复制不同的 `robots.txt` 到 `public/`；预发布域名在 Cloudflare 用 Transform Rule 加 `X-Robots-Tag: noindex`。

## 验证

```bash
curl -s https://{{PROD_DOMAIN}}/robots.txt | head -3          # 期望 Allow: /
curl -s https://{{PROD_DOMAIN}} | grep -io '<meta name="robots"[^>]*>'
curl -s https://{{STAGING_DOMAIN}}/robots.txt | head -3       # 期望 Disallow: /
curl -sI https://{{STAGING_DOMAIN}} | grep -i x-robots
```

预发布如果用 Vercel Preview 且开了 Deployment Protection，本来就登录墙，noindex 是额外保险。
