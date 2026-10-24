import { apiRequest } from "./client";
import { Movement, MovementInput } from "./types";

export function listMovements() {
  return apiRequest<Movement[]>("/movimientos");
}

export function createMovement(payload: MovementInput) {
  return apiRequest<Movement>("/movimientos", {
    method: "POST",
    body: payload,
  });
}
