import { z } from "zod";

import { getIdToken, signOut } from "@/lib/auth";

/** Browser code must reach the API through the published port; server components
 *  resolve the Compose service name instead. */
export function apiBaseUrl(): string {
  if (typeof window === "undefined") {
    return process.env.INTERNAL_API_URL ?? "http://backend:8000";
  }
  return (
    process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8000"
  ).replace(/\/+$/, "");
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  // Every API route needs a signed-in user; don't send what would bounce.
  const token = await getIdToken();
  if (!token) throw new ApiError(401, "You are signed out");

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(0, "Could not reach the API");
  }

  // The API no longer accepts this session (revoked, or the pool changed):
  // drop it, and the auth gate sends the user back to the login page.
  if (response.status === 401) signOut();

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => (typeof body?.detail === "string" ? body.detail : null))
      .catch(() => null);
    throw new ApiError(
      response.status,
      detail ?? `Request failed (${response.status})`,
    );
  }

  if (response.status === 204) {
    return schema.parse(undefined);
  }
  return schema.parse(await response.json());
}

/* --- schemas mirroring the API contract --- */

export const itemStatuses = ["todo", "in_progress", "done"] as const;
export const itemStatusSchema = z.enum(itemStatuses);

export const itemSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  status: itemStatusSchema,
  created_at: z.string(),
  updated_at: z.string(),
});

export const itemListSchema = z.object({
  items: z.array(itemSchema),
  total: z.number().int(),
});

export const healthSchema = z.object({
  status: z.string(),
  database: z.string(),
});

export const itemInputSchema = z.object({
  name: z.string().min(1, "Name is required").max(120, "Name is too long"),
  description: z.string().max(2000, "Description is too long").optional(),
  status: itemStatusSchema,
});

export type ItemStatus = z.infer<typeof itemStatusSchema>;
export type Item = z.infer<typeof itemSchema>;
export type ItemList = z.infer<typeof itemListSchema>;
export type Health = z.infer<typeof healthSchema>;
export type ItemInput = z.infer<typeof itemInputSchema>;

/* --- endpoints --- */

export const meetingSchema = z.object({
  id: z.string(),
  title: z.string(),
  starts_at: z.string(),
  duration_minutes: z.number().int(),
  participant_count: z.number().int(),
  created_at: z.string(),
});
export const meetingListSchema = z.object({
  items: z.array(meetingSchema),
  total: z.number().int(),
});
export const meetingStatsSchema = z.object({
  week_start: z.string(),
  week_end: z.string(),
  meeting_count: z.number(),
  total_hours: z.number(),
  previous_meeting_count: z.number(),
  previous_total_hours: z.number(),
});
export type Meeting = z.infer<typeof meetingSchema>;
export type MeetingInput = Pick<
  Meeting,
  "title" | "starts_at" | "duration_minutes" | "participant_count"
>;

export const api = {
  requestMeetingReport: () =>
    request(
      "/api/v1/meetings/report",
      z.object({
        request_id: z.string(),
        week: z.string(),
        status: z.literal("queued"),
      }),
      { method: "POST" },
    ),
  listMeetings: (offset = 0) =>
    request(`/api/v1/meetings?limit=20&offset=${offset}`, meetingListSchema),
  meetingStats: () => request("/api/v1/meetings/stats", meetingStatsSchema),
  createMeeting: (payload: MeetingInput) =>
    request("/api/v1/meetings", meetingSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteMeeting: (id: string) =>
    request(`/api/v1/meetings/${id}`, z.undefined(), { method: "DELETE" }),
  readiness: () => request("/api/v1/health/ready", healthSchema),

  listItems: (params: { limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    if (params.offset !== undefined) query.set("offset", String(params.offset));
    const suffix = query.size > 0 ? `?${query}` : "";
    return request(`/api/v1/items${suffix}`, itemListSchema);
  },

  createItem: (payload: ItemInput) =>
    request("/api/v1/items", itemSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateItem: (id: string, payload: Partial<ItemInput>) =>
    request(`/api/v1/items/${id}`, itemSchema, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteItem: (id: string) =>
    request(`/api/v1/items/${id}`, z.undefined(), { method: "DELETE" }),
};
