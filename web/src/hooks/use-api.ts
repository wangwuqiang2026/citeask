import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query";
import { shouldRetry } from "@/lib/retry";

export function useMe() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: () => api.me(),
    retry: false,
    staleTime: 60_000,
  });
}

/**
 * `/api/v1/meta` needs a session, so it is only requested once the user is
 * signed in — otherwise the login page would fight a 401 it cannot pass
 * (MODIFICATIONS §5.26).
 */
export function useMeta(enabled = true) {
  return useQuery({
    queryKey: queryKeys.meta,
    queryFn: () => api.meta(),
    enabled,
    staleTime: Infinity,
    retry: shouldRetry,
  });
}

export function useConversations(enabled = true) {
  return useQuery({
    queryKey: queryKeys.conversations,
    queryFn: () => api.listConversations(),
    enabled,
  });
}

export function useConversation(id: string | undefined) {
  return useQuery({
    queryKey: id ? queryKeys.conversation(id) : ["conversation", "none"],
    queryFn: () => api.getConversation(id as string),
    enabled: Boolean(id),
    retry: false,
  });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name?: string) => api.createConversation(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
    },
  });
}

export function useRenameConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      api.updateConversation(id, { name }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.conversation(variables.id),
      });
    },
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteConversation(id),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: queryKeys.conversation(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
    },
  });
}

export function useFeedback() {
  return useMutation({
    mutationFn: ({
      conversationId,
      messageIndex,
      liked,
      value,
    }: {
      conversationId: string;
      messageIndex: number;
      liked: boolean;
      value: string;
    }) => api.feedback(conversationId, messageIndex, liked, value),
  });
}
