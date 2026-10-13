export const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:9000";
export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(API + path, { ...options, headers: { "Content-Type": "application/json", ...options?.headers }, cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `Request failed (${response.status})`);
  }
  return response.json();
}
export type Prediction = { classification: string; score: number | null; error?: string; model_version?: string };
export type Point = { sample_index: number; [key: string]: number };
export type Asset = { id: string; name: string; zone: string; recording_id: string; cursor: number; status: string; total_samples: number; readings_count: number; history: Point[]; latest: { sample_index: number; received_at: string; values: Record<string, number>; prediction: Prediction | null } | null };
export type Diagnosis = { summary: string; evidence: string[]; observations: string[]; recommended_action: string; provider: string };
export type Incident = { id: string; asset_id: string; created_at: string; status: string; classification: string; priority: string; title: string; diagnosis: Diagnosis | null; error: string | null; snapshot: { sample_count: number; start_sample: number; end_sample: number } };
export type Order = { id: string; incident_id: string; asset_id: string; title: string; instructions: string; priority: string; crew_id: string | null; status: string; decision_note: string | null; created_at: string };
export type Activity = { id: number; agent: string; message: string; created_at: string; provider: string | null; incident_id: string | null };
export type Monitor = { connected: boolean; version: string | null; features: string[]; error: string | null; path: string };
export type Overview = { assets: Asset[]; incidents: Incident[]; work_orders: Order[]; crews: { id: string; name: string; skill: string; available: boolean }[]; activity: Activity[]; monitor: Monitor; replay: { running: boolean; interval: number; error: string | null }; stats: { zones: number; readings: number; open_incidents: number; pending_approval: number } };
export type Recording = { id: string; name: string; samples: number; channels: string[] };
export type Settings = { providers: { name: string; model: string; configured: boolean }[]; monitor: Monitor; dataset_recordings: number; database: string; mode: string; units: string; crew_mode: string };
export type Evaluation = { available: boolean; reason?: string; model_version?: string; split_description?: string; samples?: number; accuracy?: number; macro_f1?: number; class_names?: string[]; confusion_matrix?: number[][] };

