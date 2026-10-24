import { apiRequest } from "./client";
import { Product } from "./types";

export function listAlertas() {
  return apiRequest<Product[]>("/alertas");
}
