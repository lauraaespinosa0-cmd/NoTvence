// Refleja app/schemas.py y las respuestas de app/api/*.py.

export type Categoria = "Alimentos" | "Bebidas" | "Aseo" | "Medicamentos" | "Otros";
export type EstadoClase = "success" | "warning" | "danger";

export const CATEGORIAS: Categoria[] = ["Alimentos", "Bebidas", "Aseo", "Medicamentos", "Otros"];

export interface Product {
  codigo: string;
  nombre: string;
  categoria: string;
  subcategoria: string | null;
  presentacion: string;
  cantidad: number;
  stock_minimo: number;
  ubicacion: string;
  vence: string;
  alertas: ("Stock bajo" | "Por vencer" | "Vencido")[];
  estado: string;
  estado_clase: EstadoClase;
}

export interface ProductInput {
  nombre: string;
  categoria: Categoria;
  subcategoria?: string | null;
  presentacion: string;
  cantidad: number;
  stock_minimo: number;
  ubicacion: string;
  vence?: string | null;
}

export interface DashboardData {
  products_count: number;
  units_count: number;
  alerts_count: number;
  categories_count: number;
  recent_products: Product[];
  expiring_products: Product[];
}

export interface ShoppingItem {
  codigo: string;
  nombre: string;
  presentacion: string | null;
  cantidad_inventario: number | null;
  compra_cantidad: number;
  comprado: boolean;
  personalizado: boolean;
}

export interface ShoppingItemInput {
  nombre: string;
  cantidad: number;
}

export interface ShoppingItemUpdate {
  cantidad_compra?: number;
  comprado?: boolean;
}

export interface MovementInput {
  codigo: string;
  tipo: Movement["tipo"];
  cantidad: number;
}

export interface Movement {
  id_movimiento: number;
  producto: string;
  tipo: "Entrada" | "Consumo" | "Descarte";
  cantidad: number;
  fecha: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  username: string;
}
