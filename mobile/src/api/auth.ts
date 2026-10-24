import { apiRequest } from "./client";
import { AuthResponse } from "./types";

export function login(username: string, password: string) {
  return apiRequest<AuthResponse>("/auth/login", {
    method: "POST",
    body: { username, password },
    auth: false,
  });
}

export function register(username: string, email: string, password: string) {
  return apiRequest<AuthResponse>("/auth/register", {
    method: "POST",
    body: { username, email, password },
    auth: false,
  });
}
