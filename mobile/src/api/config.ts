import { Platform } from "react-native";

// Web uses the browser's host; Android emulators reach the host machine at 10.0.2.2.
const host =
  Platform.OS === "web" && typeof window !== "undefined"
    ? window.location.hostname
    : Platform.OS === "android"
      ? "10.0.2.2"
      : "localhost";

const configuredApiUrl = process.env.EXPO_PUBLIC_API_URL?.trim();

export const API_BASE_URL = (
  configuredApiUrl || `http://${host}:8000/api`
).replace(/\/+$/, "");
