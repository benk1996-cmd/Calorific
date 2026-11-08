import { Meal, MealItem, MealType } from "../lib/api";
import { CalorieHero, LimitRow, MacroRow, SourceChip } from "../components";
import { formatDay, greeting, mealTime, needsCheck, roundKcal } from "../lib/format";
import { useLogging } from "../logging";
import { PageHeader } from "../shell";
import { Button, Card, Chip, Icon, IconName, Skeleton } from "../ui";

const MEAL_ICON: Record<MealType, IconName> = { breakfast: "sunrise", lunch: "sun", snack: "cup", dinner: "moon" };

function portion(i: MealItem): string {
  const parts: string[] = [];
  if (i.servings && i.servings > 0) parts.push(`${+i.servings.toFixed(2)} serving${i.servings === 1 ? "" : "s"}`);
  if (i.grams && i.grams > 0) parts.push(`${Math.round(i.grams)} g`);
  return parts.join(" · ");
}

function MealCard({ meal, tz, onEdit }: { meal: Meal; tz: string; onEdit: () => void }) {
  const kcal = meal.items.reduce((s, i) => s + i.kcal, 0);
  return (
    <Card padded={false}>
      <button onClick={onEdit} className="block w-full rounded-2xl p-4 text-left transition active:bg-line/40" aria-label={`Edit ${meal.meal_type}`}>
        <div className="mb-2 flex items-center justify-between">
          <span className="flex items-center gap-2 text-sm font-bold capitalize">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-soft text-brand"><Icon name={MEAL_ICON[meal.meal_type]} className="h-[18px] w-[18px]" /></span>
            {meal.meal_type}
            <span className="text-xs font-medium normal-case text-muted">{mealTime(meal.eaten_at_utc, tz)}</span>
          </span>
          <span className="num font-bold">{roundKcal(kcal)} <span className="text-xs font-medium text-muted">kcal</span></span>
        </div>
        <ul className="divide-y divide-line">
          {meal.items.map((i) => (
            <li key={i.id} className="flex items-start justify-between gap-3 py-2">
              <span className="min-w-0">
                <span className="block text-[15px] font-medium leading-snug">{i.name}</span>
                <span className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted">
                  {portion(i) && <span>{portion(i)}</span>}
                  <SourceChip source={i.source} />
                  {needsCheck(i) && <Chip tone="warn"><Icon name="alert" className="h-3 w-3" />Check</Chip>}
                </span>
              </span>
              <span className="num shrink-0 pt-0.5 text-sm font-semibold text-ink2">{roundKcal(i.kcal)}</span>
            </li>
          ))}
        </ul>
      </button>
    </Card>
  );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-line px-6 py-10 text-center">
      <svg viewBox="0 0 96 96" className="mb-3 h-20 w-20" aria-hidden>
        <circle cx="48" cy="48" r="34" fill="rgb(var(--brand-soft))" />
        <circle cx="48" cy="48" r="19" fill="rgb(var(--card))" stroke="rgb(var(--brand))" strokeWidth="3" />
        <path d="M14 24v12a6 6 0 0 0 12 0V24M20 24v48M76 24c-5 4-7 12-7 20h7v28" fill="none" stroke="rgb(var(--brand))" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <h3 className="text-lg font-bold">Log your first meal</h3>
      <p className="mt-1 max-w-[260px] text-sm text-muted">Snap a photo or describe what you ate. Your totals update instantly.</p>
      <Button className="mt-4" icon="plus" onClick={onAdd}>Add a meal</Button>
    </div>
  );
}

export default function Today({ onProfile, onAdd, onEdit }: { onProfile: () => void; onAdd: () => void; onEdit: (id: string) => void }) {
  const { profile, summary, loading, analyzing, notice, clearNotice, day } = useLogging();
  const t = summary?.totals ?? {};
  const tg = summary?.targets ?? {};
  const name = profile.display_name?.trim().split(/\s+/)[0] || null;
  // On an empty day lead with the call to action; the (all-zero) macro and limit cards follow it.
  const firstRun = !!summary && summary.meals.length === 0 && !analyzing;
  const nutrition = (
    <>
      <Card className="space-y-4">
          <h2 className="text-sm font-bold text-ink2">Macros</h2>
          <MacroRow label="Protein" value={t.protein_g ?? 0} target={tg.protein_g ?? null} color="bg-protein" />
          <MacroRow label="Carbs" value={t.carbs_g ?? 0} target={tg.carbs_g ?? null} color="bg-carbs" />
          <MacroRow label="Fat" value={t.fat_g ?? 0} target={tg.fat_g ?? null} color="bg-fat" />
      </Card>

      <Card className="space-y-4">
          <h2 className="text-sm font-bold text-ink2">Daily limits</h2>
          <LimitRow label="Sugar" value={t.sugar_g ?? 0} cap={tg.sugar_g ?? null} unit="g" />
          <LimitRow label="Sodium" value={t.sodium_mg ?? 0} cap={tg.sodium_mg ?? null} unit="mg" />
      </Card>

    </>
  );

  return (
    <>
      <PageHeader eyebrow={formatDay(day)} title={`${greeting(profile.timezone)}${name ? `, ${name}` : ""}`} name={profile.display_name} onProfile={onProfile} />
      <div className="space-y-4 px-5">
        {notice && (
          <div role={notice.kind === "error" ? "alert" : "status"}
            className={`flex animate-fade-in items-start gap-3 rounded-2xl p-3.5 text-sm font-medium ${notice.kind === "error" ? "bg-danger-soft text-danger" : "bg-brand-soft text-brand"}`}>
            <Icon name={notice.kind === "error" ? "alert" : "check"} className="mt-0.5 h-5 w-5" />
            <p className="flex-1">{notice.text}</p>
            <button onClick={clearNotice} aria-label="Dismiss message" className="-m-2 flex h-10 w-10 items-center justify-center"><Icon name="x" className="h-4 w-4" /></button>
          </div>
        )}

        <Card>
          {loading && !summary
            ? <div className="flex items-center gap-5"><Skeleton className="h-[132px] w-[132px] rounded-full" /><div className="flex-1 space-y-3"><Skeleton className="h-8" /><Skeleton className="h-8" /><Skeleton className="h-4 w-2/3" /></div></div>
            : <CalorieHero eaten={t.kcal ?? 0} target={tg.kcal ?? profile.target_kcal} />}
        </Card>

        {!firstRun && nutrition}

        <section aria-label="Today's meals" className="space-y-3 pt-1">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-bold">Today's meals</h2>
            {summary && summary.item_count > 0 && <span className="text-sm text-muted">{summary.item_count} item{summary.item_count === 1 ? "" : "s"}</span>}
          </div>
          {loading && !summary && <div className="space-y-3"><Skeleton className="h-28" /><Skeleton className="h-28" /></div>}
          {firstRun && <EmptyState onAdd={onAdd} />}
          {summary?.meals.map((m) => <MealCard key={m.id} meal={m} tz={profile.timezone} onEdit={() => onEdit(m.id)} />)}
        </section>
        {firstRun && nutrition}
      </div>
    </>
  );
}
