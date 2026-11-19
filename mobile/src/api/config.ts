import Constants from "expo-constants";
import { Platform } from "react-native";

const expoHostUri = Constants.expoConfig?.hostUri;
const expoServerUrl = expoHostUri ? new URL(`http://${expoHostUri}`) : null;
const expoHost = expoServerUrl?.hostname ?? null;
const expoApiUrl = expoServerUrl
  ? `${/\.ngrok(?:-free)?\.(?:app|dev|io)$|\.exp\.direct$/i.test(expoServerUrl.hostname) ? "https" : "http"}://${expoServerUrl.host}/api`
  : null;

const host =
  Platform.OS === "web" && typeof window !== "undefined"
    ? window.location.hostname
    : expoHost || (Platform.OS === "android" ? "10.0.2.2" : "localhost");

const configuredApiUrl = process.env.EXPO_PUBLIC_API_URL?.trim();
const apiUrl =
  Platform.OS === "web" &&
  typeof window !== "undefined" &&
  (/\.ngrok(?:-free)?\.(?:app|dev|io)$/i.test(window.location.hostname) ||
    /\.exp\.direct$/i.test(window.location.hostname))
    ? `${window.location.origin}/api`
    : Platform.OS !== "web" && expoApiUrl
      ? expoApiUrl
      : `http://${host}:8000/api`;

export const API_BASE_URL = (
  configuredApiUrl || apiUrl
).replace(/\/+$/, "");
