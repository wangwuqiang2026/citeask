import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query";
import type { ChunksResponse, FileListResponse, GroupListResponse } from "@/lib/types";

/** Delay a value so typing in a search box does not fire one request per key. */
export function useDebouncedValue<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

const filePrefix = (indexId: string | number | undefined) =>
  ["files", String(indexId ?? "all")] as const;
const groupPrefix = (indexId: string | number | undefined) =>
  ["groups", String(indexId ?? "all")] as const;

export function useFiles(indexId: string | number | undefined, query: string) {
  return useQuery<FileListResponse>({
    queryKey: queryKeys.files(indexId, query),
    queryFn: () => api.listFiles(indexId, query),
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });
}

export function useGroups(indexId: string | number | undefined, enabled = true) {
  return useQuery<GroupListResponse>({
    queryKey: queryKeys.groups(indexId),
    queryFn: () => api.listGroups(indexId),
    enabled,
    staleTime: 15_000,
  });
}

export function useFileChunks(
  fileId: string | null,
  type: string,
) {
  return useQuery<ChunksResponse>({
    queryKey: queryKeys.fileChunks(fileId ?? "none", type),
    queryFn: () => api.fileChunks(fileId as string, type),
    enabled: Boolean(fileId),
    retry: false,
    placeholderData: keepPreviousData,
  });
}

export function useDeleteFile(indexId: string | number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fileId: string) => api.deleteFile(fileId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: filePrefix(indexId) });
      void queryClient.invalidateQueries({ queryKey: groupPrefix(indexId) });
    },
  });
}

export function useCreateGroup(indexId: string | number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, files }: { name: string; files: string[] }) =>
      api.createGroup(name, files),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: groupPrefix(indexId) });
    },
  });
}

export function useUpdateGroup(indexId: string | number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      name,
      files,
    }: {
      id: string;
      name: string;
      files: string[];
    }) => api.updateGroup(id, { name, files }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: groupPrefix(indexId) });
    },
  });
}

export function useDeleteGroup(indexId: string | number | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) => api.deleteGroup(groupId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: groupPrefix(indexId) });
    },
  });
}
