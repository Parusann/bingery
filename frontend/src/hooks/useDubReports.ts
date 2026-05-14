import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DubReportStatus } from "@/types/models";
import type {
  CreateDubReportRequest,
  UpdateDubReportRequest,
} from "@/types/api";

export function useDubReports(status?: DubReportStatus, enabled = true) {
  return useQuery({
    queryKey: ["dub-reports", status ?? "all"],
    queryFn: () => api.listDubReports(status),
    enabled,
  });
}

export function useCreateDubReport() {
  return useMutation({
    mutationFn: (body: CreateDubReportRequest) => api.createDubReport(body),
  });
}

export function useUpdateDubReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: UpdateDubReportRequest }) =>
      api.updateDubReport(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dub-reports"] });
    },
  });
}
