import { apiRequest } from "./client";
import { Product, ProductInput } from "./types";

export function listProducts(params?: { categoria?: string; estado?: string; q?: string }) {
  const query = new URLSearchParams();
  if (params?.categoria) query.set("categoria", params.categoria);
  if (params?.estado) query.set("estado", params.estado);
  if (params?.q) query.set("q", params.q);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiRequest<Product[]>(`/productos${suffix}`);
}

export function getProduct(codigo: string) {
  return apiRequest<Product>(`/productos/${encodeURIComponent(codigo)}`);
}

export function createProduct(payload: ProductInput) {
  return apiRequest<Product>("/productos", { method: "POST", body: payload });
}

export function updateProduct(codigo: string, payload: ProductInput) {
  return apiRequest<Product>(`/productos/${encodeURIComponent(codigo)}`, {
    method: "PUT",
    body: payload,
  });
}

export function deleteProduct(codigo: string) {
  return apiRequest<void>(`/productos/${encodeURIComponent(codigo)}`, { method: "DELETE" });
}
