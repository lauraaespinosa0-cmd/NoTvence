import { apiRequest } from "./client";

export function listSubcategorias(categoria: string) {
  return apiRequest<{ categoria: string; subcategorias: string[] }>(
    `/categorias/${encodeURIComponent(categoria)}/subcategorias`,
  );
}

export function listPresentaciones(categoria: string) {
  return apiRequest<{ categoria: string; presentaciones: string[] }>(
    `/categorias/${encodeURIComponent(categoria)}/presentaciones`,
  );
}
