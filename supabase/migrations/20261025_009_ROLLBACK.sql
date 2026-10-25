-- Rollback for 009: restore the previous opp_merge_batch (no 70% rule) and drop the cleanup helpers.
create or replace function public.opp_merge_batch(p_batch jsonb) returns jsonb
language plpgsql security definer set search_path to 'public' set statement_timeout to '40000' as $$
declare v_new_count int := 0; v_updated_count int := 0; v_total int := 0;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  if p_batch is null or jsonb_typeof(p_batch) <> 'array' or jsonb_array_length(p_batch) = 0 then
    return jsonb_build_object('newCount', 0, 'updatedCount', 0, 'total', 0);
  end if;
  with incoming as (select opp_key_of(elem) as k, elem, row_number() over () as rn from jsonb_array_elements(p_batch) elem),
  incoming_deduped as (select distinct on (k) k, elem from incoming order by k, rn desc),
  upserted as (insert into opp_projects_rows (key, data, updated_at) select k, elem, now() from incoming_deduped
    on conflict (key) do update set data = opp_projects_rows.data || excluded.data, updated_at = now() returning (xmax = 0) as was_insert)
  select count(*) filter (where was_insert), count(*) filter (where not was_insert) into v_new_count, v_updated_count from upserted;
  select coalesce(reltuples, 0)::int into v_total from pg_class where oid = 'public.opp_projects_rows'::regclass;
  return jsonb_build_object('newCount', v_new_count, 'updatedCount', v_updated_count, 'total', v_total);
end $$;
drop function if exists public.opp_cleanup_delete(int,int);
drop function if exists public.opp_cleanup_page(text,int);
drop function if exists public.opp_cleanup_preview();
drop function if exists public.opp_exp_pct(jsonb);
-- opp_cleanup_log is kept as an audit record (drop manually if wanted).
