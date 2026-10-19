/**
 * React Query retry policy.
 *
 * A 4xx answer is final — retrying `401 Unauthorized`, `403`, `404` or `422`
 * sends the same request again and gets the same refusal. That matters most for
 * `/api/v1/meta`, which requires a session: without this rule the login page
 * retried it forever and never became usable (MODIFICATIONS §5.26).
 */

/** `true` when a failed query may be attempted again. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  const status = statusOf(error);
  if (status !== null && status >= 400 && status < 500) return false;
  return failureCount < 1;
}

function statusOf(error: unknown): number | null {
  if (typeof error !== "object" || error === null) return null;
  const value = (error as { status?: unknown }).status;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
