# JSON-LD 模板（F07）

规则只有一条：**结构化数据里的每个事实，页面可见文本里必须有同样的事实。** 价格、名称、FAQ 从同一个数据源渲染两次，不手写第二份。

## 首页：Organization + WebSite + SoftwareApplication

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "{{BASE_URL}}/#org",
      "name": "{{COMPANY_OR_PRODUCT_NAME}}",
      "url": "{{BASE_URL}}/",
      "logo": "{{BASE_URL}}/logo.png",
      "email": "{{SUPPORT_EMAIL}}",
      "sameAs": [
        "https://x.com/{{HANDLE}}",
        "https://github.com/{{ORG}}"
      ]
    },
    {
      "@type": "WebSite",
      "@id": "{{BASE_URL}}/#website",
      "url": "{{BASE_URL}}/",
      "name": "{{PRODUCT_NAME}}",
      "publisher": { "@id": "{{BASE_URL}}/#org" },
      "inLanguage": "{{zh-CN | en}}"
    },
    {
      "@type": "SoftwareApplication",
      "@id": "{{BASE_URL}}/#app",
      "name": "{{PRODUCT_NAME}}",
      "url": "{{BASE_URL}}/",
      "applicationCategory": "{{BusinessApplication | DeveloperApplication | ...}}",
      "operatingSystem": "Web",
      "description": "{{SAME_SENTENCE_AS_META_DESCRIPTION}}",
      "offers": [
        {
          "@type": "Offer",
          "name": "{{PLAN_NAME}}",
          "price": "{{29}}",
          "priceCurrency": "{{USD | CNY}}",
          "url": "{{BASE_URL}}/pricing",
          "availability": "https://schema.org/InStock"
        }
      ],
      "publisher": { "@id": "{{BASE_URL}}/#org" }
    }
  ]
}
</script>
```

实体产品（非软件）用 `Product` 代替 `SoftwareApplication`，`offers` 结构相同。

## 有 FAQ 的页面：FAQPage

Google 2023 年起不再为 FAQPage 显示富摘要，但 ChatGPT / Perplexity / AI Overviews 仍在解析它。问答文本必须与页面上可见的 FAQ 逐字一致。

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "{{QUESTION_EXACTLY_AS_SHOWN}}",
      "acceptedAnswer": { "@type": "Answer", "text": "{{ANSWER_EXACTLY_AS_SHOWN_30_TO_90_WORDS}}" }
    }
  ]
}
</script>
```

## Next.js 里怎么放

```tsx
// app/layout.tsx 或 app/page.tsx
const jsonLd = { /* 上面的对象，从 site config 和 pricing 数据源构造 */ };
export default function Page() {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {/* ... */}
    </>
  );
}
```

Astro：直接在 `.astro` 文件里 `<script type="application/ld+json" set:html={JSON.stringify(jsonLd)} />`。

## 验证

- Google Rich Results Test：https://search.google.com/test/rich-results
- 本地：`curl -s URL | python3 -c "import sys,re,json; [json.loads(b) for b in re.findall(r'<script type=\"application/ld\+json\">(.*?)</script>', sys.stdin.read(), re.S)]; print('ok')"`
- 重跑 `launchloop-check`，F07 应列出 types。
