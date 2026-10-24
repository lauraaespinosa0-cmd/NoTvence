import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

import { API_BASE_URL } from "./config";

const TOKEN_KEY = "notvence_token";
const USERNAME_KEY = "notvence_username";

export async function getToken(): Promise<string | null> {
  if (Platform.OS === "web") {
    return window.localStorage.getItem(TOKEN_KEY);
  }
  return SecureStore.getItemAsync(TOKEN_KEY);
}

export async function getStoredUsername(): Promise<string | null> {
  if (Platform.OS === "web") {
    return window.localStorage.getItem(USERNAME_KEY);
  }
  return SecureStore.getItemAsync(USERNAME_KEY);
}

export async function setToken(token: string): Promise<void> {
  if (Platform.OS === "web") {
    window.localStorage.setItem(TOKEN_KEY, token);
    return;
  }
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function setStoredUsername(username: string): Promise<void> {
  if (Platform.OS === "web") {
    window.localStorage.setItem(USERNAME_KEY, username);
    return;
  }
  await SecureStore.setItemAsync(USERNAME_KEY, username);
}

export async function clearToken(): Promise<void> {
  if (Platform.OS === "web") {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(USERNAME_KEY);
    return;
  }
  await Promise.all([
    SecureStore.deleteItemAsync(TOKEN_KEY),
    SecureStore.deleteItemAsync(USERNAME_KEY),
  ]);
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
  auth?: boolean;
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true } = options;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const apiHost = new URL(API_BASE_URL).hostname;
  if (/\.ngrok(?:-free)?\.(?:app|dev|io)$/i.test(apiHost)) {
    headers["ngrok-skip-browser-warning"] = "true";
  }

  if (auth) {
    const token = await getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new ApiError("El servidor tardó demasiado en responder. Comprueba que el backend esté iniciado.", 0);
    }
    if (error instanceof TypeError) {
      throw new ApiError("No se pudo conectar con el servidor. Comprueba que el backend esté iniciado y que la app use la dirección correcta.", 0);
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json() : undefined;

  if (!response.ok) {
    const detail = data?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg).join(", ")
      : detail || "Ocurrió un error al comunicarse con el servidor.";
    throw new ApiError(message, response.status);
  }

  return data as T;
}
