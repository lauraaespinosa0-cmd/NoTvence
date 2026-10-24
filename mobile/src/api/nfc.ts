import { apiRequest } from "./client";
import { AuthResponse } from "./types";

export interface NfcTag {
  id: number;
  uid_tag: string;
  nombre: string;
  activo: boolean;
  creado_en: string;
  ultimo_uso: string | null;
}

export interface NfcProvision extends NfcTag {
  tag_secret: string;
}

export function loginWithNfc(uid_tag: string, tag_secret: string) {
  return apiRequest<AuthResponse>("/auth/nfc-login", {
    method: "POST",
    body: { uid_tag, tag_secret },
    auth: false,
  });
}

export function listNfcTags() {
  return apiRequest<NfcTag[]>("/auth/nfc-tags");
}

export function provisionNfcTag(uid_tag: string, nombre = "Tag principal") {
  return apiRequest<NfcProvision>("/auth/nfc-tags", {
    method: "POST",
    body: { uid_tag, nombre },
  });
}

export function revokeNfcTag(tagId: number) {
  return apiRequest<void>(`/auth/nfc-tags/${tagId}`, { method: "DELETE" });
}
