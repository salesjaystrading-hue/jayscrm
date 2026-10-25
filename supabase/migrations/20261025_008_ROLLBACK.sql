-- Rollback for 008: restore the original authenticated-only guard.
do $$
declare d text; nd text;
begin
  d := pg_get_functiondef('public.tender_ingest_batch(text,jsonb,text,text,boolean)'::regprocedure);
  nd := replace(d,
    $n$if not (coalesce(auth.role(),'') = 'service_role' or (auth.uid() is not null and public.has_permission('tenders'))) then$n$,
    $o$if auth.uid() is null or not public.has_permission('tenders') then$o$);
  if nd = d then raise exception 'rollback patch did not apply'; end if;
  execute nd;
end $$;
-- Kerala row: collection_method was 'import' before.
update public.tender_sources set collection_method='import' where portal_code='KERALA';
