-- Calorific initial schema
create extension if not exists pg_trgm;

create type activity_level as enum ('sedentary','light','moderate','active','very_active');
create type goal_type as enum ('lose','maintain','gain');
create type food_source as enum ('sgfoodid','usda','estimated');
create type meal_type as enum ('breakfast','lunch','snack','dinner');
create type input_type as enum ('photo','text');

create table profiles (
  user_id uuid primary key references auth.users on delete cascade,
  display_name text,
  sex text check (sex in ('male','female')),
  birth_year int,
  height_cm numeric,
  weight_kg numeric,
  activity_level activity_level default 'light',
  goal goal_type default 'maintain',
  timezone text not null default 'Asia/Singapore',
  target_kcal numeric,
  target_protein_g numeric,
  target_carbs_g numeric,
  target_fat_g numeric,
  cap_sugar_g numeric default 50,
  cap_sodium_mg numeric default 2000,
  target_override boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table food_reference (
  id bigserial primary key,
  source food_source not null,
  source_id text,
  name text not null,
  aliases text[] not null default '{}',
  food_group text,
  serving_desc text,
  serving_g numeric,
  per_serving jsonb,
  per_100g jsonb,
  updated_at timestamptz not null default now(),
  unique (source, source_id)
);
create index food_reference_name_trgm on food_reference using gin (name gin_trgm_ops);
-- array_to_string is only STABLE, so wrap it to use in an index. Queries must call this same function.
create or replace function immutable_join(arr text[]) returns text
  language sql immutable parallel safe as $$ select array_to_string(arr, ' ') $$;
create index food_reference_aliases_trgm on food_reference using gin (immutable_join(aliases) gin_trgm_ops);

create table meals (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users on delete cascade,
  eaten_at_utc timestamptz not null default now(),
  local_date date not null,
  meal_type meal_type not null,
  input_type input_type not null,
  note text,
  created_at timestamptz not null default now()
);
create index meals_user_date on meals (user_id, local_date);

create table meal_items (
  id uuid primary key default gen_random_uuid(),
  meal_id uuid not null references meals on delete cascade,
  name text not null,
  food_ref_id bigint references food_reference,
  source food_source not null,
  grams numeric,
  servings numeric,
  kcal numeric not null default 0,
  protein_g numeric not null default 0,
  carbs_g numeric not null default 0,
  fat_g numeric not null default 0,
  sugar_g numeric not null default 0,
  sodium_mg numeric not null default 0,
  fibre_g numeric not null default 0,
  confidence numeric,
  model_raw_json jsonb,
  user_edited boolean not null default false
);
create index meal_items_meal on meal_items (meal_id);

create table usage_counters (
  user_id uuid not null references auth.users on delete cascade,
  local_date date not null,
  analyze_count int not null default 0,
  primary key (user_id, local_date)
);

-- Atomic quota increment: returns false (and does not count) if a cap would be exceeded.
create or replace function try_consume_analyze(p_user uuid, p_date date, p_user_cap int, p_global_cap int)
returns boolean language plpgsql security definer as $$
declare g int; u int;
begin
  select coalesce(sum(analyze_count),0) into g from usage_counters where local_date = p_date;
  select coalesce(analyze_count,0) into u from usage_counters where user_id = p_user and local_date = p_date;
  if g >= p_global_cap or u >= p_user_cap then return false; end if;
  insert into usage_counters(user_id, local_date, analyze_count) values (p_user, p_date, 1)
    on conflict (user_id, local_date) do update set analyze_count = usage_counters.analyze_count + 1;
  return true;
end $$;
revoke all on function try_consume_analyze from public, anon, authenticated;

-- Row Level Security
alter table profiles enable row level security;
alter table food_reference enable row level security;
alter table meals enable row level security;
alter table meal_items enable row level security;
alter table usage_counters enable row level security;

create policy profiles_own on profiles for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy food_read on food_reference for select to authenticated using (true);
create policy meals_own on meals for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy items_own on meal_items for all
  using (exists (select 1 from meals m where m.id = meal_id and m.user_id = auth.uid()))
  with check (exists (select 1 from meals m where m.id = meal_id and m.user_id = auth.uid()));
create policy usage_read on usage_counters for select using (user_id = auth.uid());
