import { apiRequest } from "./client";
import { ShoppingItem, ShoppingItemInput, ShoppingItemUpdate } from "./types";

export function listShoppingItems() {
  return apiRequest<ShoppingItem[]>("/lista-compra");
}

export function addShoppingItem(payload: ShoppingItemInput) {
  return apiRequest<ShoppingItem>("/lista-compra", {
    method: "POST",
    body: payload,
  });
}

export function updateShoppingItem(codigo: string, payload: ShoppingItemUpdate) {
  return apiRequest<ShoppingItem>(`/lista-compra/${encodeURIComponent(codigo)}`, {
    method: "PUT",
    body: payload,
  });
}

export function deleteShoppingItem(codigo: string) {
  return apiRequest<void>(`/lista-compra/${encodeURIComponent(codigo)}`, {
    method: "DELETE",
  });
}
