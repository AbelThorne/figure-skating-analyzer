import { useQuery } from "@tanstack/react-query";
import { api, ProgramRulesData } from "../api/client";

export function useProgramRules() {
  return useQuery<ProgramRulesData>({
    queryKey: ["program-builder", "rules"],
    queryFn: api.programBuilder.rules,
    staleTime: Infinity,
  });
}
