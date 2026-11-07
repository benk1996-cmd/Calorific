import { supabase } from "./supabase";

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (data.session) headers.set("Authorization", `Bearer ${data.session.access_token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const r = await fetch(path, { ...init, headers });
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch { /* non-JSON error body */ }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export interface Profile {
  display_name: string | null;
  sex: "male" | "female";
  birth_year: number;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel;
  goal: Goal;
  timezone: string;
  target_kcal: number;
  target_protein_g: number;
  target_carbs_g: number;
  target_fat_g: number;
  cap_sugar_g: number;
  cap_sodium_mg: number;
  target_override: boolean;
}
export type ActivityLevel = "sedentary" | "light" | "moderate" | "active" | "very_active";
export type Goal = "lose" | "maintain" | "gain";

export interface MealItem {
  id: string; name: string; source: "sgfoodid" | "usda" | "estimated"; kcal: number; protein_g: number;
  carbs_g: number; fat_g: number; sugar_g: number; sodium_mg: number; fibre_g: number;
  grams: number | null; confidence: number | null;
}
export interface Meal { id: string; meal_type: string; local_date: string; input_type: string; items: MealItem[] }
export interface Summary {
  date: string;
  totals: Record<string, number>;
  targets: Record<string, number | null>;
  remaining: Record<string, number | null>;
  item_count: number;
}
export interface Usage { date: string; used: number; user_limit: number; remaining: number }
export interface AnalyzeResponse { not_food: boolean; meal: Meal | null; summary: Summary; usage: Usage }
