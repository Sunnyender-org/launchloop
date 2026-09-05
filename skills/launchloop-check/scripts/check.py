#!/usr/bin/env python3
"""LaunchLoop check: automated diagnosis for the Ready / Live / Found gates.

Zero dependencies. Python 3.9+.

    python3 check.py --url https://example.com [--repo /path/to/repo] [--tier lite|standard]
                     [--json out.json] [--report out.md] [--timeout 15]

Exit code 0 when every automatable hard gate in the selected tier passes,
1 when at least one hard gate fails, 2 on usage error.

Every check reports one of: pass / fail / warn / unknown / manual.
`unknown` means the check could not be run and must NOT be read as a fail.
`manual` lists gates that only a human can close (real-card smoke test, MoR decision...).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from html.parser import HTMLParser
from typing import Optional

UA = "LaunchLoopCheck/0.2 (+https://github.com/Sunnyender-org/launchloop)"
AI_SEARCH_BOTS = ["OAI-SearchBot", "PerplexityBot", "ClaudeBot", "Google-Extended", "Bingbot"]
TRAINING_BOT = "GPTBot"
SECRET_PATTERNS = {
    "stripe_live_secret": re.compile(r"sk_live_[0-9a-zA-Z]{10,}"),
    "stripe_test_secret": re.compile(r"sk_test_[0-9a-zA-Z]{10,}"),
    "stripe_webhook_secret": re.compile(r"whsec_[0-9a-zA-Z]{10,}"),
    "openai_key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}"),
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "supabase_service_role": re.compile(r"service_role", re.I),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
PUBLIC_PREFIXES = ("NEXT_PUBLIC_", "VITE_", "REACT_APP_", "EXPO_PUBLIC_", "NUXT_PUBLIC_", "PUBLIC_")
DANGEROUS_PUBLIC_NAMES = re.compile(r"SECRET|SERVICE_ROLE|PRIVATE|_SK\b|OPENAI|ANTHROPIC|STRIPE_SECRET|WEBHOOK", re.I)
SKIP_DIRS = {".git", "node_modules", ".next", "dist", "build", ".venv", "venv", "__pycache__", ".turbo", ".output", "vendor", "target"}
TEXT_EXT = {".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".py", ".rb", ".go", ".rs", ".php", ".java", ".kt", ".swift",
            ".json", ".yaml", ".yml", ".toml", ".env", ".md", ".sql", ".html", ".vue", ".svelte", ".astro", ".txt", ".cfg", ".ini"}


@dataclass
class Result:
    id: str
    gate: str
    title: str
    status: str  # pass | fail | warn | unknown | manual
    hard: bool
    tiers: list
    evidence: str = ""
    fix: str = ""


@dataclass
class Report:
    url: str
    repo: Optional[str]
    tier: str
    started_at: str
    results: list = field(default_factory=list)

    def add(self, r: Result) -> None:
        self.results.append(r)


# ---------- HTTP helpers ----------

class Resp:
    def __init__(self, status: int, headers: dict, body: bytes, final_url: str, redirects: list):
        self.status = status
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.body = body
        self.final_url = final_url
        self.redirects = redirects

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url: str, timeout: int, follow: bool = True, max_bytes: int = 2_000_000, method: str = "GET") -> Resp:
    redirects = []
    current = url
    for _ in range(8):
        req = urllib.request.Request(current, headers={"User-Agent": UA, "Accept": "*/*"}, method=method)
        opener = urllib.request.build_opener(_NoRedirect())
        try:
            with opener.open(req, timeout=timeout) as resp:
                body = resp.read(max_bytes)
                return Resp(resp.status, dict(resp.headers), body, current, redirects)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and follow:
                loc = e.headers.get("Location")
                if not loc:
                    return Resp(e.code, dict(e.headers), b"", current, redirects)
                nxt = urllib.parse.urljoin(current, loc)
                redirects.append((e.code, nxt))
                current = nxt
                continue
            body = b""
            try:
                body = e.read(max_bytes)
            except Exception:
                pass
            return Resp(e.code, dict(e.headers), body, current, redirects)
    return Resp(599, {}, b"", current, redirects)


def safe_fetch(url: str, timeout: int, **kw) -> Optional[Resp]:
    try:
        return fetch(url, timeout, **kw)
    except Exception:
        return None


# ---------- HTML parsing ----------

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.metas = []
        self.links = []  # (rel, href)
        self.anchors = []  # (href, text)
        self._anchor = None
        self.h1 = []
        self._in_h1 = False
        self.jsonld = []
        self._in_jsonld = False
        self.lang = None
        self.visible_text = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "link":
            self.links.append((a.get("rel", "").lower(), a.get("href", "")))
        elif tag == "a":
            self._anchor = [a.get("href", ""), ""]
        elif tag == "h1":
            self._in_h1 = True
            self.h1.append("")
        elif tag == "script":
            if (a.get("type") or "").lower() == "application/ld+json":
                self._in_jsonld = True
                self.jsonld.append("")
            else:
                self._skip_depth += 1
        elif tag in ("style", "noscript", "svg", "template"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "a" and self._anchor is not None:
            self.anchors.append((self._anchor[0], self._anchor[1].strip()))
            self._anchor = None
        elif tag == "h1":
            self._in_h1 = False
        elif tag == "script":
            if self._in_jsonld:
                self._in_jsonld = False
            elif self._skip_depth:
                self._skip_depth -= 1
        elif tag in ("style", "noscript", "svg", "template") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_jsonld:
            self.jsonld[-1] += data
            return
        if self._skip_depth:
            return
        if self._in_h1:
            self.h1[-1] += data
        if self._anchor is not None:
            self._anchor[1] += data
        t = data.strip()
        if t:
            self.visible_text.append(t)

    def meta(self, name: str) -> Optional[str]:
        for m in self.metas:
            if (m.get("name") or m.get("property") or "").lower() == name.lower():
                return m.get("content")
        return None


def parse_page(html: str) -> PageParser:
    p = PageParser()
    try:
        p.feed(html)
    except Exception:
        pass
    return p


# ---------- robots.txt ----------

def parse_robots(text: str) -> dict:
    """Return {agent_lower: {"allow": [...], "disallow": [...]}} plus sitemaps."""
    groups = {}
    sitemaps = []
    current = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        kl = k.lower()
        if kl == "user-agent":
            if current and (groups.get(current[-1], {}).get("allow") or groups.get(current[-1], {}).get("disallow")):
                current = []
            current.append(v.lower())
            groups.setdefault(v.lower(), {"allow": [], "disallow": []})
        elif kl in ("allow", "disallow"):
            for ag in current:
                groups.setdefault(ag, {"allow": [], "disallow": []})[kl].append(v)
        elif kl == "sitemap":
            sitemaps.append(v)
    return {"groups": groups, "sitemaps": sitemaps}


def bot_blocked(robots: dict, bot: str) -> Optional[bool]:
    g = robots["groups"]
    rules = g.get(bot.lower()) or g.get("*")
    if rules is None:
        return False
    dis = [d for d in rules["disallow"] if d.strip()]
    if any(d.strip() == "/" for d in dis) and not any(a.strip() == "/" for a in rules["allow"]):
        return True
    return False


# ---------- web checks ----------

def web_checks(rep: Report, base: str, timeout: int) -> None:
    u = urllib.parse.urlparse(base)
    origin = f"{u.scheme}://{u.netloc}"
    host = u.netloc

    home = safe_fetch(base, timeout)
    if home is None or home.status >= 500:
        rep.add(Result("F00", "Found", "首页可访问", "fail", True, ["lite", "standard"],
                       f"GET {base} 失败或 5xx", "先让首页返回 200 再跑其余检查"))
        return
    page = parse_page(home.text)
    rep.add(Result("F00", "Found", "首页可访问", "pass" if home.status == 200 else "fail", True, ["lite", "standard"],
                   f"HTTP {home.status}, final {home.final_url}"))

    # L01 https + canonical host
    http_url = base.replace("https://", "http://", 1) if base.startswith("https://") else None
    if http_url:
        r = safe_fetch(http_url, timeout, follow=True)
        if r and r.redirects and r.final_url.startswith("https://"):
            rep.add(Result("L01", "Live", "http → https 跳转", "pass", True, ["lite", "standard"],
                           f"{r.redirects[0][0]} → {r.final_url}"))
        elif r is None:
            rep.add(Result("L01", "Live", "http → https 跳转", "unknown", True, ["lite", "standard"], "http 端口不可达（可能已关闭，视为可接受）"))
        else:
            rep.add(Result("L01", "Live", "http → https 跳转", "fail", True, ["lite", "standard"],
                           f"http 未跳转到 https，status {r.status}", "在 CDN / 服务器上加 301 http→https"))
    alt_host = host[4:] if host.startswith("www.") else "www." + host
    alt = safe_fetch(f"{u.scheme}://{alt_host}/", timeout)
    if alt is None:
        rep.add(Result("L02", "Live", "www / 裸域单一 canonical 主机", "warn", False, ["lite", "standard"],
                       f"{alt_host} 不可达；如果你只用 {host} 也可以，但建议另一个 301 过来"))
    elif alt.redirects and urllib.parse.urlparse(alt.final_url).netloc == host:
        rep.add(Result("L02", "Live", "www / 裸域单一 canonical 主机", "pass", False, ["lite", "standard"], f"{alt_host} → {host}"))
    elif alt.status == 200:
        rep.add(Result("L02", "Live", "www / 裸域单一 canonical 主机", "fail", False, ["lite", "standard"],
                       f"{alt_host} 和 {host} 都直接 200，Google 会视为重复内容", "选一个主机名，另一个 301"))
    else:
        rep.add(Result("L02", "Live", "www / 裸域单一 canonical 主机", "warn", False, ["lite", "standard"], f"{alt_host} status {alt.status}"))

    # R01 security headers
    h = home.headers
    missing = [x for x in ("strict-transport-security", "x-content-type-options") if x not in h]
    if "x-frame-options" not in h and "frame-ancestors" not in (h.get("content-security-policy") or ""):
        missing.append("x-frame-options|csp frame-ancestors")
    if "referrer-policy" not in h:
        missing.append("referrer-policy")
    rep.add(Result("R01", "Ready", "安全响应头", "pass" if not missing else "warn", False, ["lite", "standard"],
                   "缺少: " + ", ".join(missing) if missing else "HSTS / nosniff / frame / referrer 齐",
                   "在 next.config headers() 或反向代理加上；模板见 launchloop-implement/templates/security-headers.md"))

    # R02 exposed sensitive files
    exposed = []
    for path in ("/.env", "/.env.local", "/.env.production", "/.git/config", "/.git/HEAD"):
        r = safe_fetch(origin + path, timeout, max_bytes=4096)
        if not (r and r.status == 200 and r.body):
            continue
        ct = (r.headers.get("content-type") or "").lower()
        head = r.body[:2048]
        if "text/html" in ct or head.lstrip().lower().startswith((b"<!doctype", b"<html")):
            continue  # SPA catch-all page, not a leaked file
        looks_env = bool(re.search(rb"^[A-Z_][A-Z0-9_]*=", head, re.M))
        looks_git = head.lstrip().startswith(b"[core]") or head.startswith(b"ref: refs/")
        if looks_env or looks_git:
            exposed.append(path)
    rep.add(Result("R02", "Ready", "生产 URL 不暴露 .env / .git", "fail" if exposed else "pass", True, ["lite", "standard"],
                   "暴露: " + ", ".join(exposed) if exposed else "均为 404/403 或非文件内容",
                   "立即轮换所有密钥，再修反向代理拒绝这些路径"))

    # R03 health endpoint
    found_health = None
    for path in ("/api/health", "/health", "/healthz", "/api/healthz", "/_health"):
        r = safe_fetch(origin + path, timeout, max_bytes=4096)
        if r and r.status == 200:
            found_health = path
            break
    rep.add(Result("R03", "Ready", "健康检查端点", "pass" if found_health else "unknown", True, ["standard"],
                   f"{found_health} 200" if found_health else "常见路径均无 200；如果你的端点在别处请手动确认",
                   "加一个只查 DB 连通的 /api/health 并接入部署平台"))

    # F01 robots
    robots_resp = safe_fetch(origin + "/robots.txt", timeout)
    robots = None
    if robots_resp and robots_resp.status == 200 and "text" in (robots_resp.headers.get("content-type") or "text"):
        robots = parse_robots(robots_resp.text)
        star_blocked = bot_blocked(robots, "*")
        gb = bot_blocked(robots, "Googlebot")
        if star_blocked and gb is not False:
            rep.add(Result("F01", "Found", "robots.txt 未误拦搜索引擎", "fail", True, ["lite", "standard"],
                           "User-agent: * Disallow: / 生效且 Googlebot 未单独放行", "删掉 Disallow: / 或为 Googlebot 单独 Allow: /"))
        else:
            rep.add(Result("F01", "Found", "robots.txt 未误拦搜索引擎", "pass", True, ["lite", "standard"], "无全站 Disallow"))
    elif robots_resp and robots_resp.status == 404:
        robots = {"groups": {}, "sitemaps": []}
        rep.add(Result("F01", "Found", "robots.txt 未误拦搜索引擎", "warn", True, ["lite", "standard"],
                       "robots.txt 404：不拦任何人，但也无法声明 sitemap 和 AI 爬虫策略", "加一个显式 robots.txt，模板见 launchloop-implement/templates/robots.txt"))
    else:
        rep.add(Result("F01", "Found", "robots.txt 未误拦搜索引擎", "unknown", True, ["lite", "standard"],
                       f"robots.txt 不可读 status={getattr(robots_resp, 'status', 'n/a')}"))

    # F02 AI bots
    if robots is not None:
        blocked = [b for b in AI_SEARCH_BOTS if bot_blocked(robots, b)]
        gpt = bot_blocked(robots, TRAINING_BOT)
        status = "fail" if blocked else "pass"
        ev = ("被拦: " + ", ".join(blocked) + "; ") if blocked else "AI 搜索爬虫均可访问; "
        ev += f"GPTBot(训练用) {'拦截' if gpt else '放行'} —— 这是独立决策，记录理由即可"
        rep.add(Result("F02", "Found", "AI 搜索爬虫放行", status, True, ["lite", "standard"], ev,
                       "robots.txt 为 OAI-SearchBot / PerplexityBot / ClaudeBot / Google-Extended / Bingbot 显式 Allow: /"))

    # F03 sitemap
    sm_urls = list(robots["sitemaps"]) if robots else []
    if not sm_urls:
        sm_urls = [origin + "/sitemap.xml"]
    sm = safe_fetch(sm_urls[0], timeout)
    if sm and sm.status == 200 and b"<" in sm.body:
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm.text)
        is_index = "<sitemapindex" in sm.text
        sample = locs[:5]
        bad = []
        if not is_index:
            for loc in sample:
                r = safe_fetch(loc, timeout, max_bytes=2048)
                if not r or r.status != 200:
                    bad.append(f"{loc} → {getattr(r, 'status', 'ERR')}")
        st = "fail" if bad else "pass"
        rep.add(Result("F03", "Found", "sitemap.xml 可访问且条目 200", st, True, ["lite", "standard"],
                       f"{sm_urls[0]}: {len(locs)} 条{'（索引文件）' if is_index else ''}" + ("; 抽样失败: " + "; ".join(bad) if bad else ""),
                       "sitemap 只放 200 的 canonical URL；提交到 Google Search Console 与 Bing Webmaster（这一步需人工确认）"))
    else:
        rep.add(Result("F03", "Found", "sitemap.xml 可访问且条目 200", "fail", True, ["lite", "standard"],
                       f"{sm_urls[0]} status={getattr(sm, 'status', 'ERR')}", "生成 sitemap.xml 并在 robots.txt 里声明"))
    rep.add(Result("F03m", "Found", "Search Console + Bing Webmaster 已验证并提交 sitemap", "manual", True, ["lite", "standard"],
                   "无法自动检测，需人工确认"))

    # F04 head basics + noindex
    noindex = False
    rob = page.meta("robots") or ""
    if "noindex" in rob.lower() or "noindex" in (h.get("x-robots-tag") or "").lower():
        noindex = True
    rep.add(Result("F04", "Found", "首页无 noindex", "fail" if noindex else "pass", True, ["lite", "standard"],
                   f"meta robots='{rob}' x-robots-tag='{h.get('x-robots-tag', '')}'",
                   "staging 的 noindex 带进生产了；按环境变量控制 robots meta"))
    problems = []
    if not page.title.strip():
        problems.append("无 <title>")
    if not page.meta("description"):
        problems.append("无 meta description")
    canon = [href for rel, href in page.links if "canonical" in rel]
    if not canon:
        problems.append("无 canonical")
    if len(page.h1) != 1:
        problems.append(f"h1 数量={len(page.h1)}")
    if not page.lang:
        problems.append("html 无 lang")
    rep.add(Result("F05", "Found", "title / description / canonical / 单 h1 / lang", "pass" if not problems else "fail", True, ["lite", "standard"],
                   "; ".join(problems) if problems else f"title='{page.title.strip()[:60]}' canonical={canon[0] if canon else ''}",
                   "用框架的 Metadata API 补齐；每页唯一 title 与 canonical"))

    # F06 SSR visible text
    text = " ".join(page.visible_text)
    n = len(text)
    st = "pass" if n >= 400 else ("warn" if n >= 120 else "fail")
    rep.add(Result("F06", "Found", "首页服务端渲染出可读文本（AI 爬虫不跑 JS）", st, True, ["lite", "standard"],
                   f"禁 JS 可见文本 {n} 字符" + ("" if n >= 400 else "；很可能是客户端渲染的空壳"),
                   "关键页改为 SSR / SSG；Next.js 去掉不必要的 'use client'，Vite SPA 换 Astro/Next 或做预渲染"))

    # F07 JSON-LD
    types = []
    invalid = 0
    for blob in page.jsonld:
        try:
            data = json.loads(blob)
        except Exception:
            invalid += 1
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict):
                if "@graph" in it and isinstance(it["@graph"], list):
                    items.extend(x for x in it["@graph"] if isinstance(x, dict))
                    continue
                t = it.get("@type")
                if isinstance(t, list):
                    types.extend(str(x) for x in t)
                elif t:
                    types.append(str(t))
    wanted = {"Organization", "SoftwareApplication", "Product", "WebSite", "FAQPage", "WebApplication"}
    hit = sorted(set(types) & wanted)
    if invalid:
        st = "fail"
    elif hit:
        st = "pass"
    elif types:
        st = "warn"
    else:
        st = "fail"
    rep.add(Result("F07", "Found", "JSON-LD 结构化数据", st, True, ["lite", "standard"],
                   f"types={sorted(set(types))} invalid_blocks={invalid}",
                   "首页至少 Organization + SoftwareApplication/Product；内容需与可见文本一致；模板见 launchloop-implement/templates/jsonld.md"))

    # F08 llms.txt
    llms = safe_fetch(origin + "/llms.txt", timeout)
    if llms and llms.status == 200:
        ct = (llms.headers.get("content-type") or "").lower()
        body = llms.text
        issues = []
        if not ("text/plain" in ct or "text/markdown" in ct):
            issues.append(f"content-type={ct or 'none'}（应为 text/plain 或 text/markdown）")
        if not body.lstrip().startswith("# "):
            issues.append("不以 H1 开头")
        if len(llms.body) > 100_000:
            issues.append(f"{len(llms.body)} bytes > 100KB")
        urls = list(dict.fromkeys(re.findall(r"https?://[^\s)>\]\"']+", body)))
        urls = [x.rstrip(".,;:") for x in urls]
        rel = re.findall(r"\]\((/[^)\s]*)\)", body)
        if rel:
            issues.append(f"{len(rel)} 个相对链接（应为绝对 URL）")
        if len(urls) < 3:
            issues.append(f"只有 {len(urls)} 个绝对链接")
        dead = []
        for link in urls[:5]:
            r = safe_fetch(link, timeout, max_bytes=1024)
            if not r or r.status != 200:
                dead.append(f"{link}→{getattr(r, 'status', 'ERR')}")
        if dead:
            issues.append("死链: " + "; ".join(dead))
        if robots is not None and bot_blocked(robots, "*"):
            issues.append("robots.txt 全站 Disallow 会连 llms.txt 一起拦")
        rep.add(Result("F08", "Found", "llms.txt", "pass" if not issues else "fail", True, ["lite", "standard"],
                       "; ".join(issues) if issues else f"{len(urls)} 个绝对链接, content-type={ct}",
                       "模板见 launchloop-implement/templates/llms.txt"))
    else:
        rep.add(Result("F08", "Found", "llms.txt", "fail", True, ["lite", "standard"],
                       f"/llms.txt status={getattr(llms, 'status', 'ERR')}", "模板见 launchloop-implement/templates/llms.txt"))

    # F09 Open Graph
    og = [page.meta(x) for x in ("og:title", "og:description", "og:image")]
    rep.add(Result("F09", "Found", "Open Graph 分享卡", "pass" if all(og) else "warn", False, ["lite", "standard"],
                   "缺 " + ", ".join(n for n, v in zip(("og:title", "og:description", "og:image"), og) if not v) if not all(og) else "齐"))

    # L03 legal pages (standard)
    def find_links(patterns):
        out = []
        for href, txt in page.anchors:
            blob = (href + " " + txt).lower()
            if any(p in blob for p in patterns):
                out.append(urllib.parse.urljoin(base, href))
        return list(dict.fromkeys(out))

    legal = {
        "terms": find_links(["terms", "tos", "条款", "协议", "legal"]),
        "privacy": find_links(["privacy", "隐私"]),
        "refund": find_links(["refund", "退款", "退货"]),
    }
    missing_legal = []
    for k, links in legal.items():
        ok = False
        for l in links[:2]:
            r = safe_fetch(l, timeout, max_bytes=4096)
            if r and r.status == 200:
                ok = True
                break
        if not ok:
            missing_legal.append(k)
    tiers = ["standard"]
    rep.add(Result("L03", "Live", "ToS / Privacy / Refund 页面可从首页到达", "pass" if not missing_legal else "fail", True, tiers,
                   "首页未找到可用链接: " + ", ".join(missing_legal) if missing_legal else "三页均可达",
                   "footer 加链接；模板见 launchloop-implement/templates/legal-pages.md"))

    pricing = find_links(["pricing", "价格", "定价", "plans", "购买", "buy"])
    pr_ok = None
    for l in pricing[:2]:
        r = safe_fetch(l, timeout)
        if r and r.status == 200:
            pp = parse_page(r.text)
            pr_ok = len(" ".join(pp.visible_text))
            break
    if pr_ok is None:
        rep.add(Result("L04", "Live", "定价页存在且 SSR 出文本", "fail", True, ["standard"], "首页未找到可用的 pricing 链接",
                       "加定价页并从首页链过去；价格与支付后台一致"))
    else:
        rep.add(Result("L04", "Live", "定价页存在且 SSR 出文本", "pass" if pr_ok >= 200 else "fail", True, ["standard"],
                       f"{pricing[0]} 可见文本 {pr_ok} 字符", "定价页必须 SSR，AI 才能引用价格"))


# ---------- repo checks ----------

def iter_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and (not d.startswith(".") or d == ".github")]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext in TEXT_EXT or fn.startswith(".env"):
                try:
                    if os.path.getsize(p) > 1_500_000:
                        continue
                except OSError:
                    continue
                yield p


def read_text(p: str) -> str:
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def git_tracked(root: str) -> Optional[list]:
    try:
        out = subprocess.run(["git", "-C", root, "ls-files"], capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            return None
        return out.stdout.splitlines()
    except Exception:
        return None


def repo_checks(rep: Report, root: str) -> None:
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        rep.add(Result("S00", "Ready", "仓库路径可读", "unknown", True, ["lite", "standard"], f"{root} 不存在"))
        return
    tracked = git_tracked(root)
    files = list(iter_files(root))

    # S01 .env tracked
    if tracked is not None:
        env_tracked = [f for f in tracked if os.path.basename(f).startswith(".env") and not f.endswith((".example", ".sample", ".template"))]
        rep.add(Result("S01", "Ready", ".env 不在 git 里", "fail" if env_tracked else "pass", True, ["lite", "standard"],
                       "已跟踪: " + ", ".join(env_tracked) if env_tracked else "仅 .env.example 或无",
                       "git rm --cached <file>; 加入 .gitignore; 轮换其中所有密钥（历史里已经泄露）"))
    else:
        rep.add(Result("S01", "Ready", ".env 不在 git 里", "unknown", True, ["lite", "standard"], "不是 git 仓库或 git 不可用"))

    # S02 hardcoded secrets in tracked source (excluding .env.* and examples)
    hits = []
    for p in files:
        rel = os.path.relpath(p, root)
        base = os.path.basename(p)
        if base.startswith(".env") or base.endswith((".example", ".sample", ".md")) or "test" in rel.lower() and "fixture" in rel.lower():
            continue
        if tracked is not None and rel not in tracked:
            continue
        txt = read_text(p)
        for name, pat in SECRET_PATTERNS.items():
            if name == "supabase_service_role":
                # only flag if a JWT-looking value sits next to it
                for m in re.finditer(r"service_role[^\n]{0,80}eyJ[A-Za-z0-9_\-]{20,}", txt, re.I):
                    hits.append(f"{rel}: service_role JWT 内联")
                    break
                continue
            m = pat.search(txt)
            if m:
                val = m.group(0)
                if name == "openai_key" and ("process.env" in txt[max(0, m.start() - 40):m.start()] or "os.environ" in txt[max(0, m.start() - 40):m.start()]):
                    continue
                if name == "openai_key" and re.fullmatch(r"sk-[a-z_\-]+", val):
                    continue  # e.g. sk-your-key placeholders
                hits.append(f"{rel}: {name} ({val[:8]}…)")
    rep.add(Result("S02", "Ready", "源码里无硬编码密钥", "fail" if hits else "pass", True, ["lite", "standard"],
                   "\n".join(hits[:10]) if hits else f"扫描 {len(files)} 个文件未见密钥模式",
                   "移到环境变量；已提交过的密钥视为泄露，立即轮换"))

    # S03 secrets exposed through public env prefixes
    pub_hits = []
    for p in files:
        txt = read_text(p)
        for m in re.finditer(r"\b(" + "|".join(PUBLIC_PREFIXES) + r")([A-Z0-9_]+)", txt):
            name = m.group(1) + m.group(2)
            if DANGEROUS_PUBLIC_NAMES.search(m.group(2)) and not re.search(r"ANON|PUBLISHABLE|PUBLIC_KEY|SITE_URL|APP_URL", m.group(2)):
                pub_hits.append(f"{os.path.relpath(p, root)}: {name}")
    pub_hits = sorted(set(pub_hits))
    rep.add(Result("S03", "Ready", "密钥不进前端 bundle（公开前缀变量名审查）", "fail" if pub_hits else "pass", True, ["lite", "standard"],
                   "\n".join(pub_hits[:10]) if pub_hits else "公开前缀变量名中无 SECRET / SERVICE_ROLE / OPENAI 等",
                   "去掉公开前缀，改为仅服务端读取；前端只允许 anon / publishable key"))

    # S04 Supabase / Postgres RLS — only meaningful when the app talks to Postgres through a client-facing API
    uses_pg_rls_stack = any(re.search(r"supabase|postgrest|@supabase/|nhost", read_text(p), re.I)
                            for p in files if not p.endswith((".md", ".lock")))
    sql_files = [p for p in files if p.endswith(".sql")] if uses_pg_rls_stack else []
    if not uses_pg_rls_stack:
        rep.add(Result("S04", "Ready", "每张表启用 RLS", "unknown", True, ["lite", "standard"],
                       "未检测到 Supabase / PostgREST；RLS 不适用。请确认应用层每个查询都按当前用户过滤（D1 / Prisma / Drizzle 等由代码负责隔离）"))
    elif sql_files:
        tables = set()
        rls = set()
        for p in sql_files:
            txt = read_text(p)
            for m in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?\"?([a-zA-Z_][a-zA-Z0-9_]*)\"?", txt, re.I):
                tables.add(m.group(1).lower())
            for m in re.finditer(r"alter\s+table\s+(?:only\s+)?(?:public\.)?\"?([a-zA-Z_][a-zA-Z0-9_]*)\"?\s+enable\s+row\s+level\s+security", txt, re.I):
                rls.add(m.group(1).lower())
        no_rls = sorted(tables - rls)
        if tables:
            rep.add(Result("S04", "Ready", "每张表启用 RLS（从 SQL 迁移推断）", "fail" if no_rls else "pass", True, ["lite", "standard"],
                           f"{len(tables)} 张表, 未见 RLS: {no_rls[:15]}" if no_rls else f"{len(tables)} 张表均有 enable row level security",
                           "为每张表 enable row level security 并写 policy；模板见 launchloop-implement/templates/supabase-rls.sql。注意：此检查只看迁移文件，Dashboard 里手动建的表要在 Supabase 后台确认"))
        else:
            rep.add(Result("S04", "Ready", "每张表启用 RLS", "unknown", True, ["lite", "standard"], "SQL 文件里未发现 create table；请在数据库后台确认"))
    else:
        rep.add(Result("S04", "Ready", "每张表启用 RLS", "manual", True, ["lite", "standard"],
                       "使用了 Supabase 但无 SQL 迁移文件；请在 Dashboard → Authentication → Policies 逐表确认"))

    # S05 rate limiting
    def is_app_code(p: str) -> bool:
        rel = os.path.relpath(p, root)
        if p.endswith((".md", ".json", ".lock", ".yml", ".yaml", ".toml", ".txt", ".sql")):
            return False
        top = rel.split(os.sep)[0]
        return top not in (".github", "scripts", "tests", "test", "__tests__", "docs", "evals")

    code_files = [p for p in files if is_app_code(p)]
    rl = [os.path.relpath(p, root) for p in code_files
          if re.search(r"ratelimit|rate-limit|rate_limit|@upstash/ratelimit|express-rate-limit|slowapi|RateLimiter|limiter\(", read_text(p), re.I)]
    ai_sdk = re.compile(r"from\s+openai\s+import|import\s+OpenAI|new\s+OpenAI\(|from\s+anthropic\s+import|new\s+Anthropic\(|@ai-sdk/|from\s+[\"']ai[\"']|generateText\(|streamText\(|chat\.completions\.create|messages\.create\(|replicate\.run|fal\.subscribe|GoogleGenerativeAI\(")
    ai_call = [os.path.relpath(p, root) for p in code_files if ai_sdk.search(read_text(p))]
    if ai_call and not rl:
        st, ev = "fail", f"检测到 AI/昂贵调用 ({len(ai_call)} 文件) 但无任何限流代码"
    elif ai_call:
        st, ev = "warn", f"有限流代码 ({rl[:3]})；请确认覆盖了这些 AI 调用点: {ai_call[:3]}，并在 AI 平台后台设了花费上限"
    else:
        st, ev = "unknown", "未检测到 AI 调用；若有其他昂贵接口（邮件/短信/图片）请手动确认"
    rep.add(Result("S05", "Ready", "昂贵接口有 rate limit + 花费上限", st, True, ["lite", "standard"], ev,
                   "按 IP + 用户限流；模板见 launchloop-implement/templates/rate-limit.md；OpenAI/Anthropic 后台设月度硬上限（人工）"))

    # S06 webhook idempotency (standard)
    wh = []
    for p in files:
        txt = read_text(p)
        if re.search(r"constructEvent|webhooks\.construct|x-signature|X-Signature|lemonsqueezy.*webhook|paddle.*webhook|creem.*webhook|stripe.*webhook", txt, re.I):
            has_dedupe = bool(re.search(r"event\.id|eventId|event_id|processed_events|webhook_events|idempoten|already.?processed|onConflict|ON CONFLICT", txt, re.I))
            wh.append((os.path.relpath(p, root), has_dedupe))
    if wh:
        bad = [f for f, ok in wh if not ok]
        rep.add(Result("S06", "Ready", "支付 webhook 幂等（去重）", "fail" if bad else "pass", True, ["standard"],
                       "未见去重逻辑: " + ", ".join(bad) if bad else f"{len(wh)} 个 handler 均有 event id 去重迹象",
                       "用 event.id 做唯一键先写入 processed_events 再处理；模板见 launchloop-implement/templates/webhook-idempotent.md"))
    else:
        rep.add(Result("S06", "Ready", "支付 webhook 幂等（去重）", "unknown", True, ["standard"], "未检测到支付 webhook handler"))

    # S07 noindex in code (should be env-gated)
    ni = [os.path.relpath(p, root) for p in files if re.search(r"noindex", read_text(p)) and not p.endswith(".md")]
    if ni:
        gated = any(re.search(r"process\.env|import\.meta\.env|os\.environ|VERCEL_ENV|NODE_ENV", read_text(os.path.join(root, f))) for f in ni)
        rep.add(Result("S07", "Ready", "noindex 受环境变量控制", "pass" if gated else "warn", True, ["lite", "standard"],
                       f"noindex 出现在 {ni[:3]}，" + ("同文件有环境判断" if gated else "未见环境判断，可能带进生产"),
                       "robots meta 按 VERCEL_ENV / NODE_ENV 切换"))

    # S08 .env.example
    has_example = any(os.path.basename(p) in (".env.example", ".env.sample", ".env.template") for p in files)
    rep.add(Result("S08", "Ready", ".env.example 存在", "pass" if has_example else "warn", False, ["lite", "standard"],
                   "有" if has_example else "无；新环境部署时容易漏变量"))


# ---------- manual gates ----------

def manual_gates(rep: Report, tier: str) -> None:
    items = [
        ("M01", "Ready", "数据库备份存在且做过一次真实恢复演练", ["standard"]),
        ("M02", "Ready", "可回滚：上一版镜像或 feature flag 可一键关", ["lite", "standard"]),
        ("M03", "Ready", "生产域名邮件进 Gmail / Outlook / QQ 收件箱（SPF/DKIM/DMARC）", ["standard"]),
        ("M04", "Ready", "错误追踪（Sentry 等）在生产已收到一次手动触发", ["lite", "standard"]),
        ("M05", "Ready", "AI / 邮件 / 短信平台后台已设月度花费硬上限", ["lite", "standard"]),
        ("M06", "Ready", "用第二个账号尝试读他人数据，失败", ["lite", "standard"]),
        ("M07", "Live", "MoR 决策已定并写入 record（发票上是谁）", ["standard"]),
        ("M08", "Live", "live 密钥已切换，live webhook 已注册并验签", ["standard"]),
        ("M09", "Live", "退款政策与支付平台实际行为一致", ["standard"]),
        ("M10", "Paid", "真卡走完：买 → 权益自动开 → 发票 → 退款 → 权益自动收 → 自助取消（有截图）", ["standard"]),
        ("M11", "Paid", "欧洲卡 / 3DS 挑战通过", ["standard"]),
        ("M12", "Found", "GPTBot 放行与否已做决策并记录理由", ["lite", "standard"]),
        ("M13", "Found", "Agent Readiness 扫描（readiness.bflabs.cn 或 geo-discover）三轴 pass", ["lite", "standard"]),
        ("M14", "Found", "signup → activate → pay 分析事件可打到", ["standard"]),
    ]
    for id_, gate, title, tiers in items:
        if tier in tiers:
            rep.add(Result(id_, gate, title, "manual", True, tiers, "只能人工确认；在 record 里勾"))


# ---------- output ----------

GATE_ORDER = ["Ready", "Live", "Paid", "Found"]
STATUS_MARK = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "unknown": "UNKNOWN", "manual": "MANUAL"}


def render_md(rep: Report) -> str:
    rs = [r for r in rep.results if rep.tier in r.tiers]
    hard_fail = [r for r in rs if r.hard and r.status == "fail"]
    counts = {k: sum(1 for r in rs if r.status == k) for k in STATUS_MARK}
    lines = [f"# LaunchLoop Check — {rep.url}", "",
             f"- 档: **{rep.tier}**  · 仓库: {rep.repo or '未提供'}  · 时间: {rep.started_at}",
             f"- 结果: {counts['pass']} pass · {counts['fail']} fail · {counts['warn']} warn · {counts['unknown']} unknown · {counts['manual']} manual",
             f"- **硬门槛失败: {len(hard_fail)}** → {'可以进下一门（人工项另勾）' if not hard_fail else '先修下面的 FAIL'}", ""]
    if hard_fail:
        lines.append("## 先修这些（硬门槛 FAIL）")
        lines.append("")
        for r in hard_fail:
            lines.append(f"- **{r.id} {r.title}** — {r.evidence.splitlines()[0]}")
            if r.fix:
                lines.append(f"  - 修法: {r.fix}")
        lines.append("")
    for gate in GATE_ORDER:
        gr = [r for r in rs if r.gate == gate]
        if not gr:
            continue
        lines.append(f"## 门 · {gate}")
        lines.append("")
        lines.append("| ID | 检查 | 状态 | 硬 | 证据 |")
        lines.append("|---|---|---|---|---|")
        for r in gr:
            ev = r.evidence.replace("\n", "<br>").replace("|", "\\|")
            lines.append(f"| {r.id} | {r.title} | {STATUS_MARK[r.status]} | {'H' if r.hard else 'S'} | {ev} |")
        lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("- UNKNOWN 表示无法自动判定，不是失败；MANUAL 表示只能人工确认。两者都要在 record 里补。")
    lines.append("- 此脚本只覆盖可自动化的部分。Paid 门几乎全部是人工项，这是设计使然。")
    lines.append("- 修复请用 `launchloop-implement`，每个 FAIL 的修法都对应其 templates/ 里的一个模板。")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="LaunchLoop automated checks")
    ap.add_argument("--url", required=True, help="production URL, e.g. https://example.com")
    ap.add_argument("--repo", help="local repository path for security scan")
    ap.add_argument("--tier", choices=["lite", "standard"], default="standard")
    ap.add_argument("--json", dest="json_out", help="write JSON results here")
    ap.add_argument("--report", help="write Markdown report here (default: stdout)")
    ap.add_argument("--timeout", type=int, default=15)
    args = ap.parse_args(argv)

    url = args.url if re.match(r"^https?://", args.url) else "https://" + args.url
    rep = Report(url=url, repo=args.repo, tier=args.tier, started_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    web_checks(rep, url, args.timeout)
    if args.repo:
        repo_checks(rep, args.repo)
    manual_gates(rep, args.tier)

    md = render_md(rep)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"report → {args.report}")
    else:
        print(md)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({**asdict(rep), "results": [asdict(r) for r in rep.results]}, f, ensure_ascii=False, indent=2)
        print(f"json → {args.json_out}")

    hard_fail = [r for r in rep.results if args.tier in r.tiers and r.hard and r.status == "fail"]
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
