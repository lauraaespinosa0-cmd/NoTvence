import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import DateTimePicker from "@react-native-community/datetimepicker";
import { CameraView, useCameraPermissions } from "expo-camera";
import {
  extractTextFromImage,
  isSupported as isNativeTextExtractorSupported,
} from "expo-text-extractor";
import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from "expo-speech-recognition";
import { useRef } from "react";
import NfcManager, { Ndef, NfcTech } from "react-native-nfc-manager";

import { listAlertas } from "./api/alertas";
import { listPresentaciones, listSubcategorias } from "./api/categorias";
import { addShoppingItem, deleteShoppingItem, listShoppingItems, updateShoppingItem } from "./api/compras";
import { clearToken, getStoredUsername, getToken, setStoredUsername, setToken } from "./api/client";
import { getDashboard } from "./api/dashboard";
import { login, register } from "./api/auth";
import { createMovement, listMovements } from "./api/movimientos";
import { createProduct, deleteProduct, getProduct, listProducts, updateProduct } from "./api/productos";
import { loginWithNfc, listNfcTags, provisionNfcTag, revokeNfcTag } from "./api/nfc";
import { CATEGORIAS } from "./api/types";
import { colors, statusColor } from "./theme/colors";

const NAV_ITEMS = [
  ["dashboard", "Inicio"],
  ["inventory", "Inventario"],
  ["alerts", "Alertas"],
  ["shopping", "Compras"],
  ["movements", "Movimientos"],
  ["account", "Cuenta"],
];

const MOVEMENT_TYPES = ["Entrada", "Consumo", "Descarte"];

function messageOf(error) {
  return error instanceof Error ? error.message : "Ocurrió un error inesperado.";
}

function confirmAction(title, message) {
  if (Platform.OS === "web") return Promise.resolve(window.confirm(`${title}\n\n${message}`));
  return new Promise((resolve) => {
    Alert.alert(title, message, [
      { text: "Cancelar", style: "cancel", onPress: () => resolve(false) },
      { text: "Confirmar", style: "destructive", onPress: () => resolve(true) },
    ]);
  });
}

function AppButton({ title, onPress, variant = "primary", disabled = false, compact = false }) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        styles[`button_${variant}`],
        compact && styles.buttonCompact,
        disabled && styles.buttonDisabled,
        pressed && !disabled && styles.buttonPressed,
      ]}
    >
      <Text style={[styles.buttonText, variant === "quiet" && styles.quietButtonText]}>
        {title}
      </Text>
    </Pressable>
  );
}

function Panel({ children, style }) {
  return <View style={[styles.panel, style]}>{children}</View>;
}

function Field({ label, value, onChangeText, placeholder, secureTextEntry, keyboardType, multiline }) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder || label}
        placeholderTextColor={colors.muted}
        secureTextEntry={secureTextEntry}
        keyboardType={keyboardType}
        multiline={multiline}
        style={[styles.input, multiline && styles.multilineInput]}
      />
    </View>
  );
}

function formatDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") resolve(reader.result);
      else reject(new Error("No se pudo cargar la fotografía."));
    };
    reader.onerror = () => reject(reader.error || new Error("No se pudo cargar la fotografía."));
    reader.readAsDataURL(file);
  });
}

function getVoiceField(text, labels) {
  const escaped = labels.map((label) =>
    label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  );

  const nextLabels = [
    "nombre",
    "categoría",
    "categoria",
    "subcategoría",
    "subcategoria",
    "presentación",
    "presentacion",
    "cantidad",
    "stock mínimo",
    "stock minimo",
    "ubicación",
    "ubicacion",
    "vencimiento",
  ];

  const next = nextLabels
    .map((label) => label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");

  const expression = new RegExp(
    `(?:${escaped.join("|")})\\s*[:,-]?\\s*(.*?)(?=\\s*(?:${next})\\s*[:,-]?|$)`,
    "i"
  );

  return text.match(expression)?.[1]?.trim() || "";
}

function extractExpiryDate(texts) {
  const monthNumbers = {
    ene: 1, enero: 1, jan: 1, january: 1,
    feb: 2, febrero: 2, february: 2,
    mar: 3, marzo: 3, march: 3,
    abr: 4, abril: 4, apr: 4, april: 4,
    may: 5, mayo: 5,
    jun: 6, junio: 6, june: 6,
    jul: 7, julio: 7, july: 7,
    ago: 8, agosto: 8, aug: 8, august: 8,
    sep: 9, sept: 9, septiembre: 9, setiembre: 9, september: 9,
    oct: 10, octubre: 10, october: 10,
    nov: 11, noviembre: 11, november: 11,
    dic: 12, diciembre: 12, dec: 12, december: 12,
  };
  const monthPattern = Object.keys(monthNumbers)
    .sort((a, b) => b.length - a.length)
    .join("|");
  const text = texts
    .join(" ")
    .normalize("NFKC")
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .replace(/\s*([-/\.])\s*/g, "$1")
    .replace(
      /\b(0?[1-9]|[12]\d|3[01])\s+0(?=[A-Z]{2,}\.?\s*\d{2,4}\b)/gi,
      "$1 O"
    );
  const labelledNamedDate = text.match(
    new RegExp(
      `\\b(?:vence|vencimiento|caducidad|exp(?:iry|iration)?|best\\s+before|use\\s+by|consumir\\s+antes(?:\\s+de)?)\\b[\\s:,-]{0,12}(\\d{1,2})\\s+(${monthPattern})\\.?\\s*(\\d{2,4})\\b`,
      "i"
    )
  );
  
if (labelledNamedDate) {
    const day = Number(labelledNamedDate[1]);
    const month = monthNumbers[labelledNamedDate[2].toLowerCase()];
    let year = Number(labelledNamedDate[3]);
    if (year < 100) year += 2000;
    const date = new Date(year, month - 1, day);
    if (
      date.getFullYear() === year &&
      date.getMonth() === month - 1 &&
      date.getDate() === day
    ) {
      return formatDate(date);
    }
  }

  const fullDatePattern =
    /\b(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b/g;
  const fullDates = [...text.matchAll(fullDatePattern)].map((match) => ({
    value: match[0],
    index: match.index,
  }));
  const withoutFullDates = text.replace(fullDatePattern, (match) => " ".repeat(match.length));
  const monthYearPattern =
  /\b(?:0?[1-9]|1[0-2])[-/.](?:\d{2}|(?:19|20)\d{2})\b|\b(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])\b/g;
  const monthYearDates = [...withoutFullDates.matchAll(monthYearPattern)].map((match) => ({
    value: match[0],
    index: match.index,
  }));
  const namedDatePattern = new RegExp(
    `\\b(\\d{1,2})\\s+(${monthPattern})\\.?\\s*(\\d{2,4})\\b|\\b(${monthPattern})\\.?\\s+(\\d{1,2}),?\\s+(\\d{2,4})\\b`,
    "gi"
  );
  const namedDates = [...text.matchAll(namedDatePattern)].map((match) => {
    const day = Number(match[1] || match[5]);
    const monthName = (match[2] || match[4]).toLowerCase();
    const year = Number(match[3] || match[6]);
    return {
      value: `${day}/${monthNumbers[monthName]}/${year}`,
      index: match.index,
    };
  });
  const candidates = [...fullDates, ...monthYearDates, ...namedDates].sort(
    (a, b) => a.index - b.index
  );
  const expiryLabels = [
    ...text.matchAll(
      /\b(?:exp(?:iry|iration)?|vence|vencimiento|caducidad|best\s+before|use\s+by|consumir\s+antes(?:\s+de)?)\b/gi
    ),
  ];
  const labelledDates = candidates.filter((candidate) => {
    const previousDate = candidates.filter((item) => item.index < candidate.index).pop();
    const previousLabel = expiryLabels.filter((item) => item.index < candidate.index).pop();
    return (
      previousLabel &&
      (!previousDate || previousLabel.index > previousDate.index) &&
      candidate.index - previousLabel.index <= 60
    );
  });
  const dates = [
    ...new Set((labelledDates.length ? labelledDates : candidates).map((item) => item.value)),
  ];

  if (dates.length !== 1) {
    return null;
  }

  const parts = dates[0].split(/[-/.]/).map(Number);
  let year;
  let month;
  let day;

  if (parts.length === 2) {
    if (parts[0] > 31) {
      [year, month] = parts;
    } else {
      [month, year] = parts;
    }
    if (year < 100) year += 2000;
    day = new Date(year, month, 0).getDate();
  } else if (parts[0] > 31) {
    [year, month, day] = parts;
  } else {
    [day, month, year] = parts;
    if (year < 100) year += 2000;
  }

  const date = new Date(year, month - 1, day);

  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null;
  }

  return formatDate(date);
}

function parseDate(value) {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date();
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return Number.isNaN(date.getTime()) ? new Date() : date;
}

function ExpiryDateField({ value, onChangeText }) {
  const [open, setOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState(() => parseDate(value));

  useEffect(() => {
    setSelectedDate(parseDate(value));
  }, [value]);

  function handleChange(event, date) {
    if (event.type === "dismissed") {
      setOpen(false);
      return;
    }
    if (date) {
      setSelectedDate(date);
      onChangeText(formatDate(date));
      if (Platform.OS === "android") setOpen(false);
    }
  }

  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>Vencimiento</Text>
      {Platform.OS === "web" ? (
        React.createElement("input", {
          type: "date",
          "aria-label": "Vencimiento",
          value: value || "",
          onChange: (event) => onChangeText(event.target.value),
          style: {
            boxSizing: "border-box",
            width: "100%",
            minHeight: 46,
            border: `1px solid ${colors.border}`,
            borderRadius: 11,
            color: colors.text,
            backgroundColor: colors.bgDeep,
            padding: "10px 13px",
            fontSize: 15,
            colorScheme: "dark",
          },
        })
      ) : (
        <>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Seleccionar fecha de vencimiento"
            onPress={() => {
              setSelectedDate(parseDate(value));
              setOpen(true);
            }}
            style={styles.input}
          >
            <Text style={value ? styles.dateValue : styles.datePlaceholder}>
              {value || "Seleccionar fecha"}
            </Text>
          </Pressable>
          {Platform.OS === "android" && open ? (
            <DateTimePicker
              value={selectedDate}
              mode="date"
              display="calendar"
              onChange={handleChange}
            />
          ) : null}
          {Platform.OS === "ios" ? (
            <Modal
              visible={open}
              transparent
              animationType="slide"
              onRequestClose={() => setOpen(false)}
            >
              <View style={styles.dateModalBackdrop}>
                <View style={styles.dateModal}>
                  <View style={styles.dateModalActions}>
                    <Pressable onPress={() => setOpen(false)}>
                      <Text style={styles.dateModalCancel}>Cancelar</Text>
                    </Pressable>
                    <Pressable onPress={() => setOpen(false)}>
                      <Text style={styles.dateModalDone}>Listo</Text>
                    </Pressable>
                  </View>
                  <DateTimePicker
                    value={selectedDate}
                    mode="date"
                    display="spinner"
                    onChange={handleChange}
                  />
                </View>
              </View>
            </Modal>
          ) : null}
        </>
      )}
      <Text style={styles.dateHint}>Opcional · formato AAAA-MM-DD</Text>
    </View>
  );
}
function ChoiceRow({ options, selected, onSelect, scrollable = true }) {
  const contents = options.map((option) => {
    const value = Array.isArray(option) ? option[0] : option;
    const label = Array.isArray(option) ? option[1] : option;
    const active = value === selected;
    return (
      <Pressable
        key={value}
        accessibilityRole="button"
        onPress={() => onSelect(value)}
        style={[styles.choice, active && styles.choiceActive]}
      >
        <Text style={[styles.choiceText, active && styles.choiceTextActive]}>{label}</Text>
      </Pressable>
    );
  });
  return (
    <View style={[styles.choiceRow, scrollable && styles.choiceRowWrap]}>
      {contents}
    </View>
  );
}

function ScreenHeading({ title, subtitle, action, onBack }) {
  return (
    <View style={styles.screenHeading}>
      <View style={styles.headingText}>
        {onBack ? (
          <Pressable onPress={onBack} accessibilityRole="button" style={styles.backLink}>
            <Text style={styles.backLinkText}>‹ Volver</Text>
          </Pressable>
        ) : null}
        <Text style={styles.screenTitle}>{title}</Text>
        {subtitle ? <Text style={styles.screenSubtitle}>{subtitle}</Text> : null}
      </View>
      {action ? <View style={styles.headingAction}>{action}</View> : null}
    </View>
  );
}

function Notice({ text, tone = "danger" }) {
  if (!text) return null;
  return (
    <View style={[styles.notice, styles[`notice_${tone}`]]}>
      <Text style={styles.noticeText}>{text}</Text>
    </View>
  );
}

function Loading() {
  return (
    <View style={styles.loading}>
      <ActivityIndicator color={colors.accent} size="large" />
      <Text style={styles.mutedText}>Cargando...</Text>
    </View>
  );
}

function EmptyState({ title, description, action }) {
  return (
    <Panel style={styles.emptyState}>
      <Text style={styles.emptyTitle}>{title}</Text>
      {description ? <Text style={styles.mutedText}>{description}</Text> : null}
      {action}
    </Panel>
  );
}

function Screen({ children }) {
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.screenContent}
      keyboardShouldPersistTaps="handled"
    >
      {children}
    </ScrollView>
  );
}

function ProductCard({ product, onPress }) {
  const alerts = product.alertas?.length ? product.alertas : [product.estado];
  return (
    <Pressable onPress={onPress} accessibilityRole="button" style={styles.productCard}>
      <View style={styles.productCardTop}>
        <Text style={styles.productName}>{product.nombre}</Text>
      </View>
      <View style={styles.alertBadges}>
        {alerts.map((alert) => {
          const tint = alert === "Por vencer" ? colors.warning : alert === "Activo" ? colors.success : colors.danger;
          return (
            <View key={alert} style={[styles.statusBadge, { borderColor: tint }]}>
              <Text style={[styles.statusText, { color: tint }]}>{alert}</Text>
            </View>
          );
        })}
      </View>
      <Text style={styles.productMeta}>{product.categoria}{product.subcategoria ? ` · ${product.subcategoria}` : ""}</Text>
      <View style={styles.productCardBottom}>
        <Text style={styles.productMeta}>{product.cantidad} {product.presentacion}</Text>
        <Text style={styles.productMeta}>{product.ubicacion}</Text>
      </View>
    </Pressable>
  );
}

function LoginScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(action) {
    setBusy(true);
    setError("");
    try {
      const response = await action();
      await setToken(response.access_token);
      await setStoredUsername(response.username);
      onAuthenticated(response.username);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView style={styles.authRoot}>
      <StatusBar barStyle="light-content" />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.authCenter}>
        <Panel style={styles.authPanel}>
          <View style={styles.brandMark}><Text style={styles.brandMarkText}>N</Text></View>
          <Text style={styles.brandTitle}>NotVence</Text>
          <Text style={styles.brandSubtitle}>Tu inventario, siempre bajo control</Text>
          <ChoiceRow
            scrollable={false}
            options={[["login", "Ingresar"], ["register", "Crear cuenta"]]}
            selected={mode}
            onSelect={(value) => { setMode(value); setError(""); }}
          />
          <Field label="Usuario" value={username} onChangeText={setUsername} placeholder="Tu usuario" />
          {mode === "register" ? (
            <Field label="Correo electrónico" value={email} onChangeText={setEmail} placeholder="correo@ejemplo.com" keyboardType="email-address" />
          ) : null}
          <Field label="Contraseña" value={password} onChangeText={setPassword} placeholder="Tu contraseña" secureTextEntry />
          <Notice text={error} />
          <AppButton
            title={busy ? "Un momento..." : mode === "login" ? "Ingresar" : "Crear cuenta"}
            disabled={busy || !username.trim() || !password}
            onPress={() => submit(() => mode === "login"
              ? login(username, password)
              : register(username, email, password))}
          />
          {Platform.OS !== "web" ? (
            <AppButton
              title="Ingresar con NFC"
              variant="secondary"
              disabled={busy}
              onPress={() => submit(async () => {
                await NfcManager.start();
                await NfcManager.requestTechnology(NfcTech.Ndef);
                try {
                  const tag = await NfcManager.getTag();
                  const message = await NfcManager.ndefHandler.getNdefMessage();
                  const record = message?.ndefMessage?.find(
                    (item) => item.tnf === Ndef.TNF_WELL_KNOWN && item.type?.[0] === 84,
                  );
                  if (!tag?.id || !record?.payload) throw new Error("El tag no contiene una credencial NotVence.");
                  const statusLength = record.payload[0] & 0x3f;
                  const data = JSON.parse(String.fromCharCode(...record.payload.slice(statusLength + 1)));
                  const uid = Array.from(tag.id).map((item) => item.toString(16).padStart(2, "0")).join("").toUpperCase();
                  return loginWithNfc(uid, data.tag_secret);
                } finally {
                  await NfcManager.cancelTechnologyRequest();
                }
              })}
            />
          ) : null}
          <Text style={styles.authFootnote}>Inventario doméstico simple, ordenado y seguro.</Text>
        </Panel>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function DashboardScreen({ username, navigate }) {
  const [data, setData] = useState(null);
  const [recentMovements, setRecentMovements] = useState([]);
  const [movementCount, setMovementCount] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    Promise.all([getDashboard(), listMovements()])
      .then(([dashboard, movements]) => {
        setData(dashboard);
        setMovementCount(movements.length);
        setRecentMovements(movements.slice(0, 4));
      })
      .catch((caught) => setError(messageOf(caught)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Screen>
      <ScreenHeading title={`Hola, ${username}`} subtitle="Este es el estado de tu hogar." />
      {error ? <Notice text={error} /> : null}
      {loading ? <Loading /> : data ? (
        <>
          <View style={styles.statsGrid}>
            <StatCard label="Productos" value={data.products_count} tint={colors.accent} onPress={() => navigate("inventory")} />
            <StatCard label="Unidades" value={data.units_count} tint={colors.info} onPress={() => navigate("inventory")} />
            <StatCard label="Alertas" value={data.alerts_count} tint={colors.warning} onPress={() => navigate("alerts")} />
            <StatCard label="Movimientos" value={movementCount} tint={colors.success} onPress={() => navigate("movements")} />
          </View>
          <Panel>
            <SectionTitle title="Vencimientos próximos" action="Ver alertas" onAction={() => navigate("alerts")} />
            {data.expiring_products.length ? data.expiring_products.slice(0, 4).map((product) => (
              <ProductCard key={product.codigo} product={product} onPress={() => navigate("product", { product })} />
            )) : <Text style={styles.mutedText}>No tienes productos próximos a vencer.</Text>}
          </Panel>
          <Panel>
            <SectionTitle title="Agregados recientemente" action="Ver inventario" onAction={() => navigate("inventory")} />
            {data.recent_products.length ? data.recent_products.slice(0, 5).map((product) => (
              <ProductCard key={product.codigo} product={product} onPress={() => navigate("product", { product })} />
            )) : <Text style={styles.mutedText}>Tu inventario todavía está vacío.</Text>}
          </Panel>
          <Panel>
            <SectionTitle title="Actividad reciente" action="Ver movimientos" onAction={() => navigate("movements")} />
            {recentMovements.length ? recentMovements.map((movement) => (
              <View key={movement.id_movimiento} style={styles.recentMovement}>
                <Text style={styles.productName}>{movement.producto}</Text>
                <Text style={styles.productMeta}>{movement.tipo} · {movement.cantidad} unidades</Text>
              </View>
            )) : <Text style={styles.mutedText}>Todavía no hay movimientos registrados.</Text>}
          </Panel>
        </>
      ) : null}
      <View style={styles.quickActions}>
        <AppButton title="+ Agregar producto" onPress={() => navigate("productForm")} />
        <AppButton title="Registrar movimiento" variant="secondary" onPress={() => navigate("movementForm")} />
      </View>
    </Screen>
  );
}

function StatCard({ label, value, tint, onPress }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${label}: ${value}`}
      onPress={onPress}
      style={({ pressed }) => [styles.panel, styles.statCard, pressed && styles.buttonPressed]}
    >
      <View style={[styles.statIndicator, { backgroundColor: tint }]} />
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </Pressable>
  );
}

function SectionTitle({ title, action, onAction }) {
  return (
    <View style={styles.sectionTitleRow}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {action ? <Pressable onPress={onAction}><Text style={styles.inlineAction}>{action}</Text></Pressable> : null}
    </View>
  );
}

function InventoryScreen({ navigate }) {
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    listProducts({ q: search.trim() || undefined, estado: stateFilter || undefined })
      .then((result) => { if (active) { setProducts(result); setError(""); } })
      .catch((caught) => { if (active) setError(messageOf(caught)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [search, stateFilter]);

  const visibleProducts = category ? products.filter((product) => product.categoria === category) : products;
  const stateOptions = ["", "Activo", "Stock bajo", "Por vencer", "Vencido"];

  return (
    <Screen>
      <ScreenHeading
        title="Inventario"
        subtitle={`${visibleProducts.length} productos en tu hogar`}
        action={<AppButton title="+ Agregar" compact onPress={() => navigate("productForm")} />}
      />
      <Field label="Buscar" value={search} onChangeText={setSearch} placeholder="Nombre o código" />
      <Text style={styles.filterLabel}>Categoría</Text>
      <ChoiceRow options={["", ...CATEGORIAS].map((item) => [item, item || "Todas"])} selected={category} onSelect={setCategory} />
      <Text style={styles.filterLabel}>Estado</Text>
      <ChoiceRow options={stateOptions.map((item) => [item, item || "Todos"])} selected={stateFilter} onSelect={setStateFilter} />
      <Notice text={error} />
      {loading ? <Loading /> : visibleProducts.length ? visibleProducts.map((product) => (
        <ProductCard key={product.codigo} product={product} onPress={() => navigate("product", { product })} />
      )) : (
        <EmptyState
          title="No hay productos"
          description={search || category || stateFilter ? "Prueba a cambiar los filtros." : "Agrega el primer producto a tu inventario."}
          action={!search && !category && !stateFilter ? <AppButton title="Agregar producto" onPress={() => navigate("productForm")} /> : null}
        />
      )}
    </Screen>
  );
}

function ProductDetailScreen({ product, navigate, goBack }) {
  const [detail, setDetail] = useState(product);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    getProduct(product.codigo)
      .then(setDetail)
      .catch((caught) => setError(messageOf(caught)));
  }, [product.codigo]);

  async function remove() {
    if (!(await confirmAction("Eliminar producto", `¿Quieres eliminar "${detail.nombre}" del inventario?`))) return;
    setBusy(true);
    try {
      await deleteProduct(detail.codigo);
      goBack();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <ScreenHeading title={detail.nombre} subtitle={`Código ${detail.codigo}`} onBack={goBack} />
      <Notice text={error} />
      <Panel>
        <Text style={styles.filterLabel}>Alertas del producto</Text>
        <View style={styles.alertBadges}>
          {(detail.alertas?.length ? detail.alertas : [detail.estado]).map((alert) => {
            const tint = alert === "Por vencer" ? colors.warning : alert === "Activo" ? colors.success : colors.danger;
            return (
              <View key={alert} style={[styles.statusBadge, styles.detailStatus, { borderColor: tint }]}>
                <Text style={[styles.statusText, { color: tint }]}>{alert}</Text>
              </View>
            );
          })}
        </View>
        <DetailRow label="Categoría" value={detail.categoria} />
        {detail.subcategoria ? <DetailRow label="Subcategoría" value={detail.subcategoria} /> : null}
        <DetailRow label="Presentación" value={detail.presentacion} />
        <DetailRow label="Cantidad disponible" value={`${detail.cantidad} ${detail.presentacion}`} />
        <DetailRow label="Umbral de stock bajo" value={`${detail.stock_minimo ?? 3} unidades`} />
        <DetailRow label="Ubicación" value={detail.ubicacion} />
        <DetailRow label="Vencimiento" value={detail.vence || "Sin fecha"} />
      </Panel>
      <View style={styles.quickActions}>
        <AppButton title="Editar producto" onPress={() => navigate("productForm", { product: detail })} />
        <AppButton title="Registrar movimiento" variant="secondary" onPress={() => navigate("movementForm", { product: detail })} />
        <AppButton title={busy ? "Eliminando..." : "Eliminar producto"} variant="danger" onPress={remove} disabled={busy} />
      </View>
    </Screen>
  );
}

function DetailRow({ label, value }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={styles.detailValue}>{value || "—"}</Text>
    </View>
  );
}

function ProductFormScreen({ product, goBack }) {
  const editing = Boolean(product);
  const [name, setName] = useState(product?.nombre || "");
  const [category, setCategory] = useState(product?.categoria || CATEGORIAS[0]);
  const [subcategory, setSubcategory] = useState(product?.subcategoria || "");
  const [presentation, setPresentation] = useState(product?.presentacion || "");
  const [quantity, setQuantity] = useState(product ? String(product.cantidad) : "1");
  const [stockThreshold, setStockThreshold] = useState(product ? String(product.stock_minimo ?? 3) : "3");
  const [location, setLocation] = useState(product?.ubicacion || "");
  const [expiry, setExpiry] = useState(product?.vence === "Sin fecha" ? "" : product?.vence || "");
  const [subcategories, setSubcategories] = useState([]);
  const [presentations, setPresentations] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const cameraRef = useRef(null);
  const webCameraInputRef = useRef(null);
const [cameraPermission, requestCameraPermission] = useCameraPermissions();
const [cameraOpen, setCameraOpen] = useState(false);
const [cameraReady, setCameraReady] = useState(false);
const [cameraBusy, setCameraBusy] = useState(false);
const [cameraMessage, setCameraMessage] = useState("");
const [voiceBusy, setVoiceBusy] = useState(false);
const [voiceMessage, setVoiceMessage] = useState("");

useSpeechRecognitionEvent("start", () => {
  setVoiceBusy(true);
  setVoiceMessage("Escuchando... habla con claridad.");
});

useSpeechRecognitionEvent("end", () => {
  setVoiceBusy(false);
});

useSpeechRecognitionEvent("error", (event) => {
  setVoiceBusy(false);
  setVoiceMessage(event.message || "No se pudo reconocer la voz.");
});

useSpeechRecognitionEvent("result", (event) => {
  if (!event.isFinal) return;

  const transcript = event.results?.[0]?.transcript || "";

  if (!transcript.trim()) {
    setVoiceMessage("No se reconoció ningún dato. Intenta nuevamente.");
    return;
  }

  applyVoiceData(transcript);
});

function applyVoiceData(transcript) {
  const text = transcript;

  const spokenName = getVoiceField(text, ["nombre"]);
  const spokenCategory = getVoiceField(text, ["categoría", "categoria"]);
  const spokenSubcategory = getVoiceField(text, ["subcategoría", "subcategoria"]);
  const spokenPresentation = getVoiceField(text, ["presentación", "presentacion"]);
  const spokenQuantity = getVoiceField(text, ["cantidad"]);
  const spokenStock = getVoiceField(text, ["stock mínimo", "stock minimo"]);
  const spokenLocation = getVoiceField(text, ["ubicación", "ubicacion"]);
  const spokenExpiry = getVoiceField(text, ["vencimiento"]);

  if (spokenName) setName(spokenName);

  if (spokenCategory) {
    const matchedCategory = CATEGORIAS.find(
      (item) => item.toLowerCase() === spokenCategory.toLowerCase()
    );

    if (matchedCategory) {
      setCategory(matchedCategory);
      setSubcategory("");
      setPresentation("");
    }
  }

  if (spokenSubcategory) setSubcategory(spokenSubcategory);
  if (spokenPresentation) setPresentation(spokenPresentation);

  if (spokenQuantity) {
    const number = spokenQuantity.match(/\d+/);
    if (number) setQuantity(number[0]);
  }

  if (spokenStock) {
    const number = spokenStock.match(/\d+/);
    if (number) setStockThreshold(number[0]);
  }

  if (spokenLocation) setLocation(spokenLocation);

  if (spokenExpiry) {
    const date = extractExpiryDate([spokenExpiry]);
    if (date) setExpiry(date);
  }

  setVoiceMessage("Datos reconocidos. Revisa el formulario antes de guardar.");
}
async function startVoice() {
  try {
    if (
      Platform.OS === "web" &&
      !ExpoSpeechRecognitionModule.isRecognitionAvailable()
    ) {
      setVoiceMessage(
        "Este navegador no ofrece reconocimiento de voz. Prueba en Safari actualizado y permite el acceso al micrófono."
      );
      return;
    }

    if (Platform.OS === "web") {
      setVoiceMessage("Escuchando... habla con claridad.");
      ExpoSpeechRecognitionModule.start({
        lang: "es-CO",
        interimResults: false,
        continuous: false,
        maxAlternatives: 1,
      });
      return;
    }

    setVoiceMessage("Solicitando permiso para usar el micrófono...");

    const permission = await ExpoSpeechRecognitionModule.requestPermissionsAsync();

    if (!permission.granted) {
      setVoiceMessage("Debes permitir el acceso al micrófono.");
      return;
    }

    ExpoSpeechRecognitionModule.start({
      lang: "es-CO",
      interimResults: false,
      continuous: false,
      maxAlternatives: 1,
    });
  } catch (caught) {
    setVoiceMessage(messageOf(caught));
  }
}
  
async function openExpiryCamera() {
  setCameraMessage("");
  setError("");

  try {
    const permission = await requestCameraPermission();

    if (!permission.granted) {
      setCameraMessage(
        "Debes permitir el acceso a la cámara para leer la fecha."
      );
      return;
    }

    setCameraReady(false);
    setCameraOpen(true);

  } catch (caught) {
    setCameraMessage(messageOf(caught));
  }
}


async function processExpiryImage(uri) {
  setCameraBusy(true);
  setError("");
  setCameraMessage("Leyendo la fotografía...");

  try {
    const recognizedTexts = await extractExpiryText(uri);
      const date = extractExpiryDate(recognizedTexts);

    if (!date) {
      const ocrPreview = recognizedTexts
        .join(" ")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 120);
      const message = ocrPreview
        ? `Texto detectado: ${ocrPreview}. No pude convertirlo en una fecha.`
        : "El OCR no detectó texto en la foto. Acerca la etiqueta, mejora la iluminación e inténtalo otra vez.";
      setCameraMessage(message);
      setError(message);
      return;
    }

    setExpiry(date);
    setCameraMessage(`Fecha detectada: ${date}`);
    setCameraOpen(false);
  } catch (caught) {
    const message = `No se pudo leer la foto. ${messageOf(caught)}`;
    setCameraMessage(message);
    setError(message);
  } finally {
    setCameraBusy(false);
  }
}

async function handleWebExpiryPhoto(event) {
  const input = event.currentTarget;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;

  try {
    await processExpiryImage(await readFileAsDataUrl(file));
  } catch (caught) {
    const message = `No se pudo cargar la fotografía. ${messageOf(caught)}`;
    setCameraMessage(message);
    setError(message);
  }
}

async function extractExpiryText(uri) {
  if (isNativeTextExtractorSupported) {
    return extractTextFromImage(uri);
  }

  const { createWorker } = await import("tesseract.js");
  const worker = await createWorker("eng");
  try {
    const {
      data: { text },
    } = await worker.recognize(uri);
    return [text];
  } finally {
    await worker.terminate();
  }
}


async function captureExpiryDate() {
  if (!cameraRef.current || !cameraReady || cameraBusy) {
    return;
  }

  try {
    const photo = await cameraRef.current.takePictureAsync({
      quality: 1,
      base64: Platform.OS === "web",
    });

    if (!photo?.uri) {
      throw new Error("No se pudo tomar la fotografía.");
    }

    const imageUri =
  Platform.OS === "web" && photo.base64
    ? `data:image/jpeg;base64,${photo.base64}`
    : photo.uri;

    await processExpiryImage(imageUri);

  } catch (caught) {
    setCameraMessage(messageOf(caught));
  }
}


  useEffect(() => {
    let active = true;
    Promise.all([listSubcategorias(category), listPresentaciones(category)])
      .then(([sub, pres]) => {
        if (active) {
          setSubcategories(sub.subcategorias || []);
          setPresentations(pres.presentaciones || []);
        }
      })
      .catch((caught) => { if (active) setError(messageOf(caught)); });
    return () => { active = false; };
  }, [category]);

  async function save() {
    setError("");
    const amount = Number.parseInt(quantity, 10);
    const threshold = Number.parseInt(stockThreshold, 10);
    if (!name.trim() || !location.trim() || !presentation.trim() || !Number.isInteger(amount) || amount < 0) {
      setError("Completa los campos obligatorios con valores válidos.");
      return;
    }
    if (!Number.isInteger(threshold) || threshold < 0) {
      setError("El límite para stock bajo debe ser un número entero igual o mayor que cero.");
      return;
    }
    if (expiry && !/^\d{4}-\d{2}-\d{2}$/.test(expiry)) {
      setError("La fecha debe tener formato AAAA-MM-DD.");
      return;
    }
    setBusy(true);
    try {
      const payload = {
        nombre: name.trim(),
        categoria: category,
        subcategoria: subcategory.trim() || null,
        presentacion: presentation.trim(),
        cantidad: amount,
        stock_minimo: threshold,
        ubicacion: location.trim(),
        vence: expiry || null,
      };
      if (editing) await updateProduct(product.codigo, payload);
      else await createProduct(payload);
      goBack();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen>
      <ScreenHeading title={editing ? "Editar producto" : "Nuevo producto"} subtitle="Completa la información del inventario." onBack={goBack} />
      <Panel>
        {editing ? <DetailRow label="Código" value={product.codigo} /> : null}
        <Field label="Nombre" value={name} onChangeText={setName} placeholder="Ej. Leche entera" />
        <Text style={styles.filterLabel}>Categoría *</Text>
        <ChoiceRow options={CATEGORIAS} selected={category} onSelect={(value) => { setCategory(value); setSubcategory(""); setPresentation(""); }} />
        <Text style={styles.filterLabel}>Subcategoría</Text>
        <ChoiceRow options={["", ...subcategories].map((item) => [item, item || "Ninguna"])} selected={subcategory} onSelect={setSubcategory} />
        <Field label="Presentación" value={presentation} onChangeText={setPresentation} placeholder="Ej. Unidad, litro, kg" />
        {presentations.length ? (
          <ChoiceRow options={presentations} selected={presentation} onSelect={setPresentation} />
        ) : null}
        <Field label="Cantidad" value={quantity} onChangeText={setQuantity} keyboardType="numeric" placeholder="0" />
        <Field label="Avisar cuando queden (unidades)" value={stockThreshold} onChangeText={setStockThreshold} keyboardType="numeric" placeholder="3" />
        <Text style={styles.dateHint}>Si la cantidad disponible es igual o menor, se mostrará la alerta de stock bajo.</Text>
        <Field label="Ubicación" value={location} onChangeText={setLocation} placeholder="Ej. Despensa" />
        <ExpiryDateField value={expiry} onChangeText={setExpiry} />
        {Platform.OS === "web"
          ? React.createElement("input", {
              ref: webCameraInputRef,
              type: "file",
              accept: "image/*",
              capture: "environment",
              onChange: handleWebExpiryPhoto,
              style: { display: "none" },
            })
          : null}
        <AppButton
          title={Platform.OS === "web" ? "📷 Tomar foto de vencimiento" : "📷 Leer fecha con cámara"}
          variant="secondary"
          onPress={openExpiryCamera}
          disabled={cameraBusy}
        />
        {Platform.OS === "web" && cameraMessage ? (
          <Text style={styles.mutedText}>{cameraMessage}</Text>
        ) : null}

<AppButton
  title={voiceBusy ? "Escuchando..." : "🎤 Completar formulario por voz"}
  variant="secondary"
  onPress={voiceBusy ? () => ExpoSpeechRecognitionModule.stop() : startVoice}
/>

{voiceMessage ? (
  <Text style={styles.mutedText}>{voiceMessage}</Text>
) : null}
<Modal
  visible={Platform.OS !== "web" && cameraOpen}
  animationType="slide"
  onRequestClose={() => setCameraOpen(false)}
>
  <View style={{ flex: 1, backgroundColor: "#000" }}>
    <Text style={{ color: "#fff", textAlign: "center", padding: 15 }}>
      Enfoca la fecha de vencimiento y pulsa “Tomar fotografía”
    </Text>

    <CameraView
      ref={cameraRef}
      style={{ flex: 1 }}
      facing="back"
      onCameraReady={() => setCameraReady(true)}
      onMountError={({ message }) => {
        setCameraOpen(false);
        setError(message || "No se pudo abrir la cámara.");
      }}
    />

    <View style={{ padding: 20, gap: 10 }}>
      {cameraMessage ? (
        <Text style={styles.cameraMessage}>{cameraMessage}</Text>
      ) : null}
      <AppButton
        title={cameraBusy ? "Leyendo fecha..." : "Tomar fotografía"}
        onPress={captureExpiryDate}
        disabled={!cameraReady || cameraBusy}
      />

      <AppButton
        title="Cancelar"
        variant="secondary"
        onPress={() => setCameraOpen(false)}
      />
    </View>
  </View>
</Modal>
        <Notice text={error} />
        <AppButton title={busy ? "Guardando..." : editing ? "Guardar cambios" : "Crear producto"} disabled={busy} onPress={save} />
      </Panel>
    </Screen>
  );
}

function AlertsScreen({ navigate }) {
  const [products, setProducts] = useState([]);
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    listAlertas().then(setProducts).catch((caught) => setError(messageOf(caught))).finally(() => setLoading(false));
  }, []);
  const states = ["", "Stock bajo", "Por vencer", "Vencido"];
  const visible = products.filter((product) =>
    (!filter || product.alertas?.includes(filter)) &&
    (!search || product.nombre.toLowerCase().includes(search.toLowerCase()) || product.codigo.toLowerCase().includes(search.toLowerCase()))
  );
  return (
    <Screen>
      <ScreenHeading title="Alertas" subtitle="Productos que necesitan atención." />
      <Field label="Buscar alerta" value={search} onChangeText={setSearch} placeholder="Nombre o código" />
      <ChoiceRow options={states.map((item) => [item, item || "Todas"])} selected={filter} onSelect={setFilter} />
      <Notice text={error} />
      {loading ? <Loading /> : visible.length ? visible.map((product) => (
        <ProductCard key={product.codigo} product={product} onPress={() => navigate("product", { product })} />
      )) : <EmptyState title="Todo al día" description="No hay alertas que coincidan con tu búsqueda." />}
      <AppButton title="Abrir lista de compras" variant="secondary" onPress={() => navigate("shopping")} />
    </Screen>
  );
}

function ShoppingScreen() {
  const [items, setItems] = useState([]);
  const [products, setProducts] = useState([]);
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busyCode, setBusyCode] = useState("");
  const [error, setError] = useState("");

  async function reload() {
    const [shopping, inventory] = await Promise.all([listShoppingItems(), listProducts()]);
    setItems(shopping);
    setProducts(inventory);
  }
  useEffect(() => {
    reload().catch((caught) => setError(messageOf(caught))).finally(() => setLoading(false));
  }, []);
  const productMap = useMemo(() => new Map(products.map((product) => [product.codigo, product])), [products]);
  const groups = useMemo(() => {
    const result = new Map();
    for (const item of items) {
      const category = item.personalizado ? "Personalizados" : productMap.get(item.codigo)?.categoria || "Otros";
      if (!result.has(category)) result.set(category, []);
      result.get(category).push(item);
    }
    return Array.from(result.entries());
  }, [items, productMap]);

  async function changeItem(item, update) {
    setBusyCode(item.codigo);
    setError("");
    try {
      await updateShoppingItem(item.codigo, update);
      await reload();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusyCode("");
    }
  }

  async function addItem() {
    const amount = Number.parseInt(quantity, 10);
    if (!name.trim() || !Number.isInteger(amount) || amount < 0) {
      setError("Escribe el artículo y una cantidad válida.");
      return;
    }
    setBusyCode("new");
    setError("");
    try {
      await addShoppingItem({ nombre: name.trim(), cantidad: amount });
      setName("");
      setQuantity("1");
      setShowForm(false);
      await reload();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusyCode("");
    }
  }

  async function removeItem(item) {
    if (!(await confirmAction("Quitar artículo", `¿Quitar "${item.nombre}" de la lista?`))) return;
    setBusyCode(item.codigo);
    try {
      await deleteShoppingItem(item.codigo);
      await reload();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusyCode("");
    }
  }

  return (
    <Screen>
      <ScreenHeading title="Lista de compras" subtitle={`${items.filter((item) => !item.comprado).length} pendientes`} action={<AppButton compact title="+ Agregar" onPress={() => setShowForm(!showForm)} />} />
      <Notice text={error} />
      {showForm ? (
        <Panel>
          <SectionTitle title="Agregar artículo" />
          <Field label="Artículo" value={name} onChangeText={setName} placeholder="Ej. Café" />
          <Field label="Cantidad" value={quantity} onChangeText={setQuantity} keyboardType="numeric" />
          <View style={styles.inlineButtons}>
            <AppButton compact title="Cancelar" variant="quiet" onPress={() => setShowForm(false)} />
            <AppButton compact title={busyCode === "new" ? "Agregando..." : "Agregar"} onPress={addItem} disabled={busyCode === "new"} />
          </View>
        </Panel>
      ) : null}
      {loading ? <Loading /> : groups.length ? groups.map(([categoryName, group]) => (
        <Panel key={categoryName}>
          <SectionTitle title={categoryName} />
          {group.map((item) => (
            <View key={item.codigo} style={[styles.shoppingItem, item.comprado && styles.shoppingItemDone]}>
              <Pressable onPress={() => changeItem(item, { comprado: !item.comprado })} style={styles.checkButton}>
                <Text style={[styles.checkMark, item.comprado && styles.checkMarkDone]}>{item.comprado ? "✓" : "○"}</Text>
              </Pressable>
              <View style={styles.shoppingInfo}>
                <Text style={[styles.productName, item.comprado && styles.crossedText]}>{item.nombre}</Text>
                <Text style={styles.productMeta}>{item.presentacion || "Artículo"}{item.cantidad_inventario !== null ? ` · En inventario: ${item.cantidad_inventario}` : ""}</Text>
              </View>
              <Pressable disabled={busyCode === item.codigo} onPress={() => changeItem(item, { cantidad_compra: Math.max(0, item.compra_cantidad - 1) })} style={styles.qtyButton}><Text style={styles.qtyText}>−</Text></Pressable>
              <Text style={styles.qtyValue}>{item.compra_cantidad}</Text>
              <Pressable disabled={busyCode === item.codigo} onPress={() => changeItem(item, { cantidad_compra: item.compra_cantidad + 1 })} style={styles.qtyButton}><Text style={styles.qtyText}>+</Text></Pressable>
              <Pressable onPress={() => removeItem(item)} style={styles.removeButton}><Text style={styles.removeText}>×</Text></Pressable>
            </View>
          ))}
        </Panel>
      )) : <EmptyState title="Tu lista está vacía" description="Agrega artículos para organizar tu próxima compra." />}
    </Screen>
  );
}

function MovementsScreen({ navigate }) {
  const [movements, setMovements] = useState([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    listMovements().then(setMovements).catch((caught) => setError(messageOf(caught))).finally(() => setLoading(false));
  }, []);
  const visible = filter ? movements.filter((movement) => movement.tipo === filter) : movements;
  return (
    <Screen>
      <ScreenHeading
        title="Movimientos"
        subtitle="Entradas, consumos y descartes del inventario."
        action={<AppButton compact title="+ Registrar" onPress={() => navigate("movementForm")} />}
      />
      <ChoiceRow options={["", ...MOVEMENT_TYPES].map((item) => [item, item || "Todos"])} selected={filter} onSelect={setFilter} />
      <Notice text={error} />
      {loading ? <Loading /> : visible.length ? visible.map((movement) => (
        <Panel key={movement.id_movimiento} style={styles.movementCard}>
          <View style={styles.productCardTop}>
            <Text style={styles.productName}>{movement.producto}</Text>
            <View style={[styles.statusBadge, { borderColor: movement.tipo === "Entrada" ? colors.success : movement.tipo === "Descarte" ? colors.danger : colors.info }]}>
              <Text style={[styles.statusText, { color: movement.tipo === "Entrada" ? colors.success : movement.tipo === "Descarte" ? colors.danger : colors.info }]}>{movement.tipo}</Text>
            </View>
          </View>
          <Text style={styles.productMeta}>{movement.cantidad} unidades · {movement.fecha || "Fecha no disponible"}</Text>
        </Panel>
      )) : <EmptyState title="Sin movimientos" description="Cuando registres entradas, consumos o descartes, aparecerán aquí." />}
      <AppButton title="Registrar movimiento" onPress={() => navigate("movementForm")} />
    </Screen>
  );
}

function MovementFormScreen({ product: initialProduct, goBack }) {
  const [products, setProducts] = useState([]);
  const [productCode, setProductCode] = useState(initialProduct?.codigo || "");
  const [type, setType] = useState("Entrada");
  const [quantity, setQuantity] = useState("1");
  const [loading, setLoading] = useState(!initialProduct);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    listProducts()
      .then((result) => {
        setProducts(result);
        if (!productCode && result.length) setProductCode(result[0].codigo);
      })
      .catch((caught) => setError(messageOf(caught)))
      .finally(() => setLoading(false));
  }, []);
  async function save() {
    const amount = Number.parseInt(quantity, 10);
    if (!productCode || !Number.isInteger(amount) || amount < 1) {
      setError("Selecciona un producto y escribe una cantidad mayor que cero.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createMovement({ codigo: productCode, tipo, cantidad: amount });
      goBack();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen>
      <ScreenHeading title="Nuevo movimiento" subtitle="El inventario se actualizará automáticamente." onBack={goBack} />
      <Panel>
        {loading ? <Loading /> : products.length ? (
          <>
            <Text style={styles.filterLabel}>Producto</Text>
            <ChoiceRow options={products.map((item) => [item.codigo, `${item.nombre} (${item.cantidad})`])} selected={productCode} onSelect={setProductCode} />
          </>
        ) : <Text style={styles.mutedText}>Primero agrega un producto al inventario.</Text>}
        <Text style={styles.filterLabel}>Tipo de movimiento</Text>
        <ChoiceRow options={MOVEMENT_TYPES} selected={type} onSelect={setType} />
        <Field label="Cantidad" value={quantity} onChangeText={setQuantity} keyboardType="numeric" />
        <Notice text={error} />
        <AppButton title={busy ? "Guardando..." : "Guardar movimiento"} disabled={busy || loading || !products.length} onPress={save} />
      </Panel>
    </Screen>
  );
}

async function scanUidOnly() {
  await NfcManager.start();
  await NfcManager.requestTechnology(NfcTech.Ndef);
  try {
    const tag = await NfcManager.getTag();
    if (!tag?.id) throw new Error("El teléfono no pudo leer el UID del tag.");
    return Array.from(tag.id).map((value) => value.toString(16).padStart(2, "0")).join("").toUpperCase();
  } finally {
    await NfcManager.cancelTechnologyRequest();
  }
}

async function writeCredential(provision) {
  const bytes = Ndef.encodeMessage([Ndef.textRecord(JSON.stringify({ tag_secret: provision.tag_secret }), "en")]);
  await NfcManager.requestTechnology(NfcTech.Ndef);
  try {
    await NfcManager.ndefHandler.writeNdefMessage(bytes);
  } finally {
    await NfcManager.cancelTechnologyRequest();
  }
}

function AccountScreen({ username, onLogout }) {
  const [tagName, setTagName] = useState("Tag principal");
  const [tags, setTags] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function reloadTags() {
    try {
      setTags(await listNfcTags());
    } catch (caught) {
      setError(messageOf(caught));
    }
  }
  useEffect(() => { reloadTags(); }, []);

  async function addTag() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const uid = await scanUidOnly();
      const provision = await provisionNfcTag(uid, tagName);
      await writeCredential(provision);
      setMessage("Tag registrado y credencial escrita correctamente.");
      await reloadTags();
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy(false);
    }
  }

  async function removeTag(tag) {
    if (!(await confirmAction("Revocar tag", `¿Revocar "${tag.nombre}"?`))) return;
    try {
      await revokeNfcTag(tag.id);
      await reloadTags();
    } catch (caught) {
      setError(messageOf(caught));
    }
  }

  return (
    <Screen>
      <ScreenHeading title="Cuenta" subtitle="Tu sesión y acceso NFC." />
      <Panel>
        <Text style={styles.filterLabel}>Sesión iniciada como</Text>
        <Text style={styles.accountName}>{username}</Text>
        <AppButton title="Cerrar sesión" variant="secondary" onPress={onLogout} />
      </Panel>
      <Panel>
        <SectionTitle title="Acceso NFC" />
        {Platform.OS === "web" ? (
          <Text style={styles.mutedText}>El registro NFC está disponible desde la app instalada en un dispositivo compatible.</Text>
        ) : (
          <>
            <Text style={styles.mutedText}>Registra un NTAG215 para iniciar sesión acercándolo al teléfono.</Text>
            <Field label="Nombre del tag" value={tagName} onChangeText={setTagName} />
            <AppButton title={busy ? "Acerca el tag al teléfono..." : "Registrar un NTAG215"} disabled={busy} onPress={addTag} />
          </>
        )}
        <Notice text={error} />
        <Notice text={message} tone="success" />
        {tags.map((tag) => (
          <View key={tag.id} style={styles.tagRow}>
            <View style={styles.shoppingInfo}>
              <Text style={styles.productName}>{tag.nombre}</Text>
              <Text style={styles.productMeta}>{tag.uid_tag} · {tag.activo ? "Activo" : "Revocado"}</Text>
            </View>
            {tag.activo ? <AppButton compact variant="danger" title="Revocar" onPress={() => removeTag(tag)} /> : null}
          </View>
        ))}
      </Panel>
    </Screen>
  );
}

export default function AppMobile() {
  const [username, setUsername] = useState(null);
  const [loadingSession, setLoadingSession] = useState(true);
  const [stack, setStack] = useState([{ name: "dashboard", params: {} }]);
  const route = stack[stack.length - 1];

  useEffect(() => {
    Promise.all([getToken(), getStoredUsername()])
      .then(([token, savedUsername]) => {
        if (token && savedUsername) setUsername(savedUsername);
      })
      .catch((caught) => console.error("No se pudo restaurar la sesión:", caught))
      .finally(() => setLoadingSession(false));
  }, []);

  function navigate(name, params = {}) {
    setStack((current) => [...current, { name, params }]);
  }
  function goBack() {
    setStack((current) => current.length > 1 ? current.slice(0, -1) : [{ name: "dashboard", params: {} }]);
  }
  function selectTab(name) {
    setStack([{ name, params: {} }]);
  }
  async function logout() {
    await clearToken();
    setUsername(null);
    setStack([{ name: "dashboard", params: {} }]);
  }

  if (loadingSession) {
    return <SafeAreaView style={styles.authRoot}><Loading /></SafeAreaView>;
  }
  if (!username) {
    return <LoginScreen onAuthenticated={(value) => { setUsername(value); setStack([{ name: "dashboard", params: {} }]); }} />;
  }

  let content;
  switch (route.name) {
    case "inventory":
      content = <InventoryScreen navigate={navigate} />;
      break;
    case "alerts":
      content = <AlertsScreen navigate={navigate} />;
      break;
    case "shopping":
      content = <ShoppingScreen />;
      break;
    case "movements":
      content = <MovementsScreen navigate={navigate} />;
      break;
    case "account":
      content = <AccountScreen username={username} onLogout={logout} />;
      break;
    case "product":
      content = <ProductDetailScreen product={route.params.product} navigate={navigate} goBack={goBack} />;
      break;
    case "productForm":
      content = <ProductFormScreen product={route.params.product} goBack={goBack} />;
      break;
    case "movementForm":
      content = <MovementFormScreen product={route.params.product} goBack={goBack} />;
      break;
    default:
      content = <DashboardScreen username={username} navigate={navigate} />;
  }

  return (
    <SafeAreaView style={styles.appRoot}>
      <StatusBar barStyle="light-content" />
      <View style={styles.topBar}>
        <Pressable accessibilityRole="button" onPress={() => selectTab("dashboard")} style={styles.brandInline}>
          <View style={styles.brandMini}><Text style={styles.brandMiniText}>N</Text></View>
          <Text style={styles.topBarTitle}>NotVence</Text>
        </Pressable>
        <Pressable accessibilityRole="button" onPress={() => selectTab("account")} style={styles.userChip}>
          <Text style={styles.userInitial}>{username.charAt(0).toUpperCase()}</Text>
          <Text numberOfLines={1} style={styles.userChipText}>{username}</Text>
        </Pressable>
      </View>
      <View style={styles.mainArea}>{content}</View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.bottomNav} contentContainerStyle={styles.bottomNavContent}>
        {NAV_ITEMS.map(([name, label]) => {
          const active = route.name === name || (["product", "productForm", "movementForm"].includes(route.name) && stack[stack.length - 2]?.name === name);
          return (
            <Pressable key={name} accessibilityRole="button" onPress={() => selectTab(name)} style={[styles.navItem, active && styles.navItemActive]}>
              <Text style={[styles.navLabel, active && styles.navLabelActive]}>{label}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  appRoot: { flex: 1, backgroundColor: colors.bgDeep },
  authRoot: { flex: 1, backgroundColor: colors.bgDeep, justifyContent: "center", padding: 20 },
  authCenter: { width: "100%", maxWidth: 480, alignSelf: "center" },
  authPanel: { alignItems: "stretch", padding: 28 },
  brandMark: { alignSelf: "center", width: 58, height: 58, borderRadius: 18, backgroundColor: colors.accent, alignItems: "center", justifyContent: "center", marginBottom: 14 },
  brandMarkText: { color: "#fff", fontSize: 34, fontWeight: "900" },
  brandTitle: { color: colors.text, textAlign: "center", fontSize: 30, fontWeight: "800" },
  brandSubtitle: { color: colors.muted, textAlign: "center", fontSize: 14, marginTop: 4, marginBottom: 24 },
  authFootnote: { color: colors.muted, textAlign: "center", marginTop: 18, fontSize: 12 },
  topBar: { height: 62, paddingHorizontal: 18, flexDirection: "row", alignItems: "center", justifyContent: "space-between", borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: colors.bgDeep },
  brandInline: { flexDirection: "row", alignItems: "center", gap: 10 },
  brandMini: { width: 34, height: 34, borderRadius: 11, alignItems: "center", justifyContent: "center", backgroundColor: colors.accent },
  brandMiniText: { color: "#fff", fontWeight: "900", fontSize: 21 },
  topBarTitle: { color: colors.text, fontSize: 17, fontWeight: "800" },
  userChip: { maxWidth: 155, flexDirection: "row", alignItems: "center", gap: 8, borderWidth: 1, borderColor: colors.border, borderRadius: 22, paddingVertical: 5, paddingHorizontal: 9 },
  userInitial: { width: 26, height: 26, overflow: "hidden", borderRadius: 13, textAlign: "center", textAlignVertical: "center", backgroundColor: colors.panelSoft, color: colors.text, fontWeight: "700", paddingTop: 4 },
  userChipText: { color: colors.text, fontSize: 12, maxWidth: 105 },
  mainArea: { flex: 1, width: "100%", maxWidth: 980, alignSelf: "center" },
  screen: { flex: 1 },
  screenContent: { width: "100%", maxWidth: 850, alignSelf: "center", padding: 18, paddingBottom: 32, gap: 14 },
  bottomNav: { flexGrow: 0, maxHeight: 60, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.panelSolid },
  bottomNavContent: { flexGrow: 1, flexDirection: "row", alignItems: "center", justifyContent: "space-around", paddingHorizontal: 8, gap: 4 },
  navItem: { minWidth: 94, alignItems: "center", justifyContent: "center", height: 42, borderRadius: 12, paddingHorizontal: 12 },
  navItemActive: { backgroundColor: "#6d5dfc22" },
  navLabel: { color: colors.muted, fontSize: 12, fontWeight: "600" },
  navLabelActive: { color: "#b8adff" },
  screenHeading: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 4 },
  headingText: { flex: 1 },
  headingAction: { flexShrink: 0 },
  screenTitle: { color: colors.text, fontSize: 26, fontWeight: "800" },
  screenSubtitle: { color: colors.muted, fontSize: 14, marginTop: 4 },
  backLink: { marginBottom: 4 },
  backLinkText: { color: "#b8adff", fontSize: 14, fontWeight: "700" },
  panel: { backgroundColor: colors.panel, borderWidth: 1, borderColor: colors.border, borderRadius: 18, padding: 16, gap: 12 },
  field: { gap: 6, width: "100%" },
  fieldLabel: { color: colors.muted, fontSize: 13, fontWeight: "600" },
  input: { width: "100%", minHeight: 46, borderWidth: 1, borderColor: colors.border, borderRadius: 11, color: colors.text, backgroundColor: colors.bgDeep, paddingHorizontal: 13, paddingVertical: 10, fontSize: 15, outlineStyle: "none" },
  dateValue: { color: colors.text, fontSize: 15 },
  datePlaceholder: { color: colors.muted, fontSize: 15 },
  dateHint: { color: colors.muted, fontSize: 11 },
  dateModalBackdrop: { flex: 1, justifyContent: "flex-end", backgroundColor: "#0009" },
  dateModal: { backgroundColor: colors.panel, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16 },
  dateModalActions: { flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 8, paddingVertical: 12 },
  dateModalCancel: { color: colors.muted, fontSize: 16 },
  dateModalDone: { color: "#b8adff", fontSize: 16, fontWeight: "700" },
  multilineInput: { minHeight: 92, textAlignVertical: "top" },
  button: { minHeight: 44, alignItems: "center", justifyContent: "center", borderRadius: 11, paddingHorizontal: 16, paddingVertical: 10, backgroundColor: colors.primary, marginTop: 3 },
  button_primary: { backgroundColor: colors.primary },
  button_secondary: { backgroundColor: colors.panelSoft, borderWidth: 1, borderColor: colors.border },
  button_danger: { backgroundColor: "#5b2028", borderWidth: 1, borderColor: "#8e3038" },
  button_quiet: { backgroundColor: "transparent" },
  buttonCompact: { minHeight: 36, paddingVertical: 7, paddingHorizontal: 12, marginTop: 0 },
  buttonDisabled: { opacity: 0.55 },
  buttonPressed: { opacity: 0.82 },
  buttonText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  quietButtonText: { color: colors.muted },
  choiceRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 2 },
  choiceRowWrap: { flexWrap: "wrap" },
  choice: { borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingVertical: 8, paddingHorizontal: 13, backgroundColor: colors.panelSolid },
  choiceActive: { borderColor: colors.accent, backgroundColor: "#6d5dfc2a" },
  choiceText: { color: colors.muted, fontSize: 12, fontWeight: "600" },
  choiceTextActive: { color: "#c7bdff" },
  statsGrid: { flexDirection: "row", flexWrap: "wrap", gap: 10 },
  statCard: { flexGrow: 1, flexBasis: "46%", minWidth: 145, gap: 5, position: "relative", overflow: "hidden" },
  statIndicator: { width: 28, height: 4, borderRadius: 2, marginBottom: 6 },
  statValue: { color: colors.text, fontSize: 27, fontWeight: "800" },
  statLabel: { color: colors.muted, fontSize: 13 },
  sectionTitleRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 },
  sectionTitle: { color: colors.text, fontWeight: "700", fontSize: 17 },
  inlineAction: { color: "#b8adff", fontSize: 13, fontWeight: "700" },
  productCard: { borderWidth: 1, borderColor: colors.border, borderRadius: 13, padding: 13, backgroundColor: colors.panelSolid, gap: 7, marginTop: 8 },
  productCardTop: { flexDirection: "row", alignItems: "flex-start", justifyContent: "space-between", gap: 8 },
  alertBadges: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  productName: { color: colors.text, fontSize: 15, fontWeight: "700", flexShrink: 1 },
  productMeta: { color: colors.muted, fontSize: 12 },
  productCardBottom: { flexDirection: "row", justifyContent: "space-between", gap: 10 },
  statusBadge: { borderWidth: 1, borderRadius: 20, paddingHorizontal: 9, paddingVertical: 4, flexShrink: 0 },
  detailStatus: { alignSelf: "flex-start", marginBottom: 4 },
  statusText: { fontSize: 11, fontWeight: "700" },
  filterLabel: { color: colors.muted, fontSize: 13, fontWeight: "700", marginTop: 4 },
  notice: { borderWidth: 1, borderRadius: 11, padding: 12, backgroundColor: "#351b23", borderColor: "#71323e" },
  notice_danger: { backgroundColor: "#351b23", borderColor: "#71323e" },
  notice_success: { backgroundColor: "#172f27", borderColor: "#286744" },
  noticeText: { color: "#ffb8bf", fontSize: 13, lineHeight: 18 },
  emptyState: { alignItems: "center", paddingVertical: 26 },
  emptyTitle: { color: colors.text, fontSize: 17, fontWeight: "700" },
  mutedText: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  cameraMessage: { color: "#fff", fontSize: 13, lineHeight: 18, textAlign: "center" },
  loading: { minHeight: 95, alignItems: "center", justifyContent: "center", gap: 8 },
  quickActions: { gap: 8 },
  detailRow: { minHeight: 44, flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 14, borderBottomWidth: 1, borderBottomColor: colors.border, paddingVertical: 8 },
  detailLabel: { color: colors.muted, fontSize: 13, flex: 1 },
  detailValue: { color: colors.text, fontSize: 14, fontWeight: "600", flex: 1, textAlign: "right" },
  inlineButtons: { flexDirection: "row", justifyContent: "flex-end", gap: 8 },
  shoppingItem: { minHeight: 62, flexDirection: "row", alignItems: "center", gap: 7, borderBottomWidth: 1, borderBottomColor: colors.border, paddingVertical: 9 },
  shoppingItemDone: { opacity: 0.62 },
  checkButton: { width: 28, alignItems: "center" },
  checkMark: { color: colors.muted, fontSize: 21 },
  checkMarkDone: { color: colors.success, fontWeight: "800" },
  shoppingInfo: { flex: 1, gap: 3 },
  crossedText: { textDecorationLine: "line-through", color: colors.muted },
  qtyButton: { width: 28, height: 28, alignItems: "center", justifyContent: "center", borderWidth: 1, borderColor: colors.border, borderRadius: 8, backgroundColor: colors.panelSoft },
  qtyText: { color: colors.text, fontSize: 18, lineHeight: 22 },
  qtyValue: { color: colors.text, minWidth: 19, textAlign: "center", fontWeight: "700" },
  removeButton: { width: 25, alignItems: "center" },
  removeText: { color: colors.danger, fontSize: 21 },
  movementCard: { gap: 8 },
  recentMovement: { borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 10, gap: 4 },
  accountName: { color: colors.text, fontSize: 21, fontWeight: "700" },
  tagRow: { minHeight: 55, flexDirection: "row", alignItems: "center", gap: 10, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: 10 },
});
