-- Food search used by the resolver and the /api/foods/search endpoint.
-- Exact name/alias matches rank first, then trigram similarity. SG FoodID outranks USDA on ties
-- (enum order: sgfoodid < usda < estimated). Aliases are matched through immutable_join().
create or replace function search_foods(p_q text, p_source food_source, p_min real, p_limit int)
returns table (
  id bigint, source food_source, source_id text, name text, aliases text[], food_group text,
  serving_desc text, serving_g numeric, per_serving jsonb, per_100g jsonb, score real, is_exact boolean
) language sql stable as $$
  select * from (
    select f.id, f.source, f.source_id, f.name, f.aliases, f.food_group, f.serving_desc, f.serving_g,
           f.per_serving, f.per_100g,
           greatest(similarity(f.name, p_q), similarity(immutable_join(f.aliases), p_q))::real as score,
           (lower(f.name) = lower(p_q)
            or lower(p_q) = any (array(select lower(a) from unnest(f.aliases) a))) as is_exact
    from food_reference f
    where p_source is null or f.source = p_source
  ) t
  where t.is_exact or t.score >= p_min
  order by t.is_exact desc, t.score desc, t.source asc
  limit p_limit
$$;

create or replace function db_size_mb() returns numeric language sql stable as $$
  select round(pg_database_size(current_database()) / 1048576.0, 1)
$$;

revoke all on function search_foods, db_size_mb from public, anon, authenticated;
