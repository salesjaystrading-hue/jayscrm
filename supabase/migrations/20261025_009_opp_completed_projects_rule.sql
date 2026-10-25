-- 009: Project Opportunity rule - projects with Expenditure Completed >= 70% are not stored.
-- "Expenditure completed %" = Expenditure / FundTotal * 100 (the source sheets have no percentage column);
-- an explicit percentage column ("Expenditure Completed %" etc.) wins if a future file has one.
-- Missing / non-numeric / FundTotal <= 0  => percentage is NULL => kept for review, never deleted or skipped.

create or replace function public.opp_exp_pct(elem jsonb) returns numeric
language plpgsql immutable set search_path = public as $$
declare k text; v text; e numeric; f numeric;
begin
  foreach k in array array['Expenditure Completed %','Expenditure %','Expenditure Percentage','Expenditure Completed','Expenditure Completed Percentage'] loop
    v := nullif(btrim(elem->>k), '');
    if v is not null then
      v := replace(replace(v, '%', ''), ',', '');
      if v ~ '^[0-9]+(\.[0-9]+)?$' then return v::numeric; else return null; end if;
    end if;
  end loop;
  v := replace(btrim(coalesce(elem->>'Expenditure', '')), ',', '');
  if v !~ '^[0-9]+(\.[0-9]+)?$' then return null; end if;
  e := v::numeric;
  v := replace(btrim(coalesce(elem->>'FundTotal', '')), ',', '');
  if v !~ '^[0-9]+(\.[0-9]+)?$' then return null; end if;
  f := v::numeric;
  if f <= 0 then return null; end if;
  return e * 100 / f;            -- deliberately NOT rounded: 69.996 must stay below 70
end $$;

-- Every import path (paste, Excel, CSV, retry) goes through this one function.
create or replace function public.opp_merge_batch(p_batch jsonb) returns jsonb
language plpgsql security definer set search_path to 'public' set statement_timeout to '40000' as $$
declare v_new int := 0; v_upd int := 0; v_total int := 0; v_skipped int := 0; v_review int := 0;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if p_batch is null or jsonb_typeof(p_batch) <> 'array' or jsonb_array_length(p_batch) = 0 then
    return jsonb_build_object('newCount', 0, 'updatedCount', 0, 'total', 0, 'skippedCompleted', 0, 'reviewCount', 0);
  end if;
  select count(*) filter (where public.opp_exp_pct(e) >= 70), count(*) filter (where public.opp_exp_pct(e) is null)
    into v_skipped, v_review from jsonb_array_elements(p_batch) e;
  with incoming as (
    select opp_key_of(elem) as k, elem, row_number() over () as rn
    from jsonb_array_elements(p_batch) elem
    where coalesce(public.opp_exp_pct(elem), 0) < 70          -- >=70% completed: skipped; unknown: kept for review
  ),
  incoming_deduped as (select distinct on (k) k, elem from incoming order by k, rn desc),
  upserted as (
    insert into opp_projects_rows (key, data, updated_at)
    select k, elem, now() from incoming_deduped
    on conflict (key) do update set data = opp_projects_rows.data || excluded.data, updated_at = now()
    returning (xmax = 0) as was_insert
  )
  select count(*) filter (where was_insert), count(*) filter (where not was_insert) into v_new, v_upd from upserted;
  select coalesce(reltuples, 0)::int into v_total from pg_class where oid = 'public.opp_projects_rows'::regclass;
  return jsonb_build_object('newCount', v_new, 'updatedCount', v_upd, 'total', v_total, 'skippedCompleted', v_skipped, 'reviewCount', v_review);
end $$;

-- Audit log for cleanups (no policies: only the SECURITY DEFINER functions below can write it).
create table if not exists public.opp_cleanup_log (
  id bigserial primary key, at timestamptz not null default now(), by_user uuid, action text not null,
  deleted int, remaining int, note text);
alter table public.opp_cleanup_log enable row level security;
revoke all on public.opp_cleanup_log from anon, authenticated;

create or replace function public.opp_cleanup_preview() returns jsonb
language plpgsql security definer set search_path to 'public' set statement_timeout to '30000' as $$
declare r jsonb;
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Admin role required'; end if;
  with trk as (select jsonb_object_keys(value) k from public.jays_crm_store where key = 'jays_opptracking' and jsonb_typeof(value) = 'object'),
  p as (select key, data, public.opp_exp_pct(data) pct, (key in (select k from trk)) tracked from public.opp_projects_rows)
  select jsonb_build_object(
    'total', count(*),
    'eligible', count(*) filter (where pct >= 70 and not tracked),
    'tracked_protected', count(*) filter (where pct >= 70 and tracked),
    'below_70', count(*) filter (where pct < 70),
    'review_blank_invalid', count(*) filter (where pct is null),
    'over_100', count(*) filter (where pct > 100 and not tracked),
    'eligible_bytes', coalesce(sum(pg_column_size(data)) filter (where pct >= 70 and not tracked), 0),
    'sample', (select coalesce(jsonb_agg(jsonb_build_object('key', key, 'project_no', data->>'Project No', 'name', coalesce(data->>'Project Name Eng', data->>'Project Name Mal'),
               'lb', data->>'LB Name', 'fund', data->>'FundTotal', 'expenditure', data->>'Expenditure', 'pct', round(pct, 2))), '[]'::jsonb)
               from (select * from p where pct >= 70 and not tracked order by pct desc, key limit 25) s)
  ) into r from p;
  return r;
end $$;

-- Backup export: eligible rows, paged by key (the browser downloads these as a file BEFORE any deletion).
create or replace function public.opp_cleanup_page(p_after_key text default null, p_limit int default 1000)
returns table(key text, data jsonb) language plpgsql security definer set search_path to 'public' set statement_timeout to '30000' as $$
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Admin role required'; end if;
  return query
    select r.key, r.data from public.opp_projects_rows r
    where public.opp_exp_pct(r.data) >= 70
      and r.key not in (select jsonb_object_keys(value) from public.jays_crm_store where key = 'jays_opptracking' and jsonb_typeof(value) = 'object')
      and (p_after_key is null or r.key > p_after_key)
    order by r.key limit greatest(1, least(coalesce(p_limit, 1000), 2000));
end $$;

-- Deletes eligible rows in chunks. p_expected must equal the current eligible count on the first call (guards against a stale preview).
create or replace function public.opp_cleanup_delete(p_expected int default null, p_limit int default 3000) returns jsonb
language plpgsql security definer set search_path to 'public' set statement_timeout to '28000' as $$
declare v_elig int; v_del int; v_left int;
begin
  if auth.uid() is null or not public.is_admin() then raise exception 'Admin role required'; end if;
  if p_expected is not null then
    select count(*) into v_elig from public.opp_projects_rows r where public.opp_exp_pct(r.data) >= 70
      and r.key not in (select jsonb_object_keys(value) from public.jays_crm_store where key = 'jays_opptracking' and jsonb_typeof(value) = 'object');
    if v_elig <> p_expected then raise exception 'Eligible count changed (expected %, found %). Nothing was deleted - run the preview again.', p_expected, v_elig; end if;
  end if;
  with victims as (
    select r.key from public.opp_projects_rows r where public.opp_exp_pct(r.data) >= 70
      and r.key not in (select jsonb_object_keys(value) from public.jays_crm_store where key = 'jays_opptracking' and jsonb_typeof(value) = 'object')
    order by r.key limit greatest(1, least(coalesce(p_limit, 3000), 5000)))
  delete from public.opp_projects_rows t using victims v where t.key = v.key;
  get diagnostics v_del = row_count;
  select count(*) into v_left from public.opp_projects_rows r where public.opp_exp_pct(r.data) >= 70
      and r.key not in (select jsonb_object_keys(value) from public.jays_crm_store where key = 'jays_opptracking' and jsonb_typeof(value) = 'object');
  insert into public.opp_cleanup_log(by_user, action, deleted, remaining, note) values (auth.uid(), 'delete_completed_70pct', v_del, v_left, 'Expenditure/FundTotal >= 70%');
  return jsonb_build_object('deleted', v_del, 'remaining_eligible', v_left);
end $$;

revoke all on function public.opp_exp_pct(jsonb), public.opp_cleanup_preview(), public.opp_cleanup_page(text,int), public.opp_cleanup_delete(int,int) from public, anon;
grant execute on function public.opp_exp_pct(jsonb), public.opp_cleanup_preview(), public.opp_cleanup_page(text,int), public.opp_cleanup_delete(int,int) to authenticated;
revoke all on function public.opp_merge_batch(jsonb) from public, anon;
grant execute on function public.opp_merge_batch(jsonb) to authenticated;
