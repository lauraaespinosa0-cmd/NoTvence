import { apiRequest } from "./client";
import { DashboardData } from "./types";

export function getDashboard() {
  return apiRequest<DashboardData>("/dashboard");
}
