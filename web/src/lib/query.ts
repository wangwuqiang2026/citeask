import { QueryClient } from "@tanstack/react-query";

import { shouldRetry } from "./retry";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: shouldRetry,
      staleTime: 15_000,
      refetchOnWindowFocus: false,
    },
  },
});

export const queryKeys = {
  me: ["me"] as const,
  meta: ["meta"] as const,
  conversations: ["conversations"] as const,
  conversation: (id: string) => ["conversation", id] as const,
  settings: ["settings"] as const,
  settingsSchema: ["settings", "schema"] as const,
  files: (indexId: string | number | undefined, query: string) =>
    ["files", String(indexId ?? "all"), query] as const,
  groups: (indexId: string | number | undefined) =>
    ["groups", String(indexId ?? "all")] as const,
  fileChunks: (fileId: string, type: string) =>
    ["file-chunks", fileId, type] as const,
  resources: ["resources"] as const,
  help: ["help"] as const,
  users: ["users"] as const,
};
