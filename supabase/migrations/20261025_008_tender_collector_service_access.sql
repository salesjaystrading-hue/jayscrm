-- 008: allow the server-side collector (service_role, i.e. GitHub Actions) to call tender_ingest_batch().
-- Additive and narrow: browsers/anon still cannot write; signed-in users still need the 'tenders' permission.
-- The service-role key lives ONLY in GitHub Actions secrets.
do $$
declare d text; nd text;
begin
  d := pg_get_functiondef('public.tender_ingest_batch(text,jsonb,text,text,boolean)'::regprocedure);
  nd := replace(d,
    $o$if auth.uid() is null or not public.has_permission('tenders') then$o$,
    $n$if not (coalesce(auth.role(),'') = 'service_role' or (auth.uid() is not null and public.has_permission('tenders'))) then$n$);
  if nd = d then raise exception 'guard patch did not apply'; end if;
  execute nd;
end $$;

revoke all on function public.tender_ingest_batch(text,jsonb,text,text,boolean) from public, anon;
grant execute on function public.tender_ingest_batch(text,jsonb,text,text,boolean) to authenticated, service_role;

-- Kerala e-Tender is CAPTCHA-gated: never automated.
update public.tender_sources
   set collection_method = 'manual',
       last_run_message = coalesce(last_run_message, 'Unsupported by the scraper (CAPTCHA). Manual import only.')
 where portal_code = 'KERALA';
