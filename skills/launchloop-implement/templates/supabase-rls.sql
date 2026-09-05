-- Supabase / Postgres RLS 模板（S04）
-- 对每张含用户数据的表重复下面这一段。生成后给人审，再在 Supabase SQL Editor 里执行。
-- 假设表有 user_id uuid 列指向 auth.users(id)。

-- 1. 开 RLS。开了之后没有 policy 的表对 anon / authenticated 角色是"全部拒绝"，这是想要的默认。
alter table public.{{TABLE}} enable row level security;

-- 2. 四条 policy：只允许当前用户操作自己的行。
create policy "{{TABLE}}: select own"
  on public.{{TABLE}} for select
  to authenticated
  using (user_id = auth.uid());

create policy "{{TABLE}}: insert own"
  on public.{{TABLE}} for insert
  to authenticated
  with check (user_id = auth.uid());

create policy "{{TABLE}}: update own"
  on public.{{TABLE}} for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy "{{TABLE}}: delete own"
  on public.{{TABLE}} for delete
  to authenticated
  using (user_id = auth.uid());

-- 3. 公开可读的表（比如定价、公告）单独放开 select，其他仍拒绝。
-- create policy "{{PUBLIC_TABLE}}: public read" on public.{{PUBLIC_TABLE}} for select to anon, authenticated using (true);

-- 4. 服务端用 service_role key 的操作绕过 RLS，这是预期的；所以 service_role 绝对不能进前端（见 S03）。

-- 5. 验证（M06）：用账号 A 的 JWT 查账号 B 的行，必须返回空。
--    在 SQL Editor 里模拟：
--    set local role authenticated;
--    set local request.jwt.claims = '{"sub":"<USER_A_UUID>"}';
--    select * from public.{{TABLE}} where user_id = '<USER_B_UUID>';   -- 期望 0 行

-- 6. 常见漏洞：
--    - 只写了 select 没写 insert 的 with check → 用户能给别人插数据。
--    - 用 (true) 做 using 想"先跑通再说" → 等于没开。
--    - 表通过 view 暴露而 view 没开 security_invoker → 绕过 RLS。给 view 加 `with (security_invoker = true)`。
