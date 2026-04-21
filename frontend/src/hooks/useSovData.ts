import { useQuery } from "@tanstack/react-query";
import { api, SovData } from "../api/client";

export function useSovData() {
  return useQuery<SovData>({
    queryKey: ["program-builder", "sov"],
    queryFn: api.programBuilder.sov,
    staleTime: Infinity,
  });
}
