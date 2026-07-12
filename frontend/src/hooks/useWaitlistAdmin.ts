import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useWaitlistAdmin(enabled = true) {
  return useQuery({
    queryKey: ["waitlist-admin"],
    queryFn: () => api.waitlistAdmin(),
    enabled,
  });
}

export function useApproveWaitlistEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.waitlistAdminApprove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["waitlist-admin"] });
    },
  });
}
