// API 客户端封装 —— 所有后端请求收口在这里
import axios from "axios";

// agentChat 需要等 LLM + 工具循环, 比常规接口慢很多, 单设更长超时
const api = axios.create({ baseURL: "http://localhost:8000/api", timeout: 60000 });

export interface Product {
  id: number;
  name: string;
  category: string;
  brand: string;
  price: number;
  stock: number;
  spec: string;
}

export interface CartItem {
  product_id: number;
  qty: number;
}

export interface CartResp {
  items: CartItem[];
  total: number;
}

// ---------------------------------------------------------------- 商品
export async function listProducts(params: {
  keyword?: string;
  category?: string;
  max_price?: number;
  limit?: number;
}): Promise<Product[]> {
  const { data } = await api.get<Product[]>("/products", { params });
  return data;
}

export async function getCategories(): Promise<string[]> {
  const { data } = await api.get<string[]>("/products/categories");
  return data;
}

// ---------------------------------------------------------------- 购物车
export async function getCart(): Promise<CartResp> {
  const { data } = await api.get<CartResp>("/cart");
  return data;
}

export async function addToCart(product_id: number, qty = 1): Promise<CartResp> {
  const { data } = await api.post<CartResp>("/cart/add", { product_id, qty });
  return data;
}

export async function updateCartQty(
  product_id: number,
  qty: number,
): Promise<CartResp> {
  const { data } = await api.post<CartResp>("/cart/qty", { product_id, qty });
  return data;
}

export interface CheckoutResp {
  order_id: number;
  total: number;
  status: string;
  msg: string;
}

export async function checkout(): Promise<CheckoutResp> {
  const { data } = await api.post<CheckoutResp>("/cart/checkout");
  return data;
}

// ---------------------------------------------------------------- Agent
export interface AgentResp {
  answer: string;
  tool_results: Record<string, unknown>;
  fallback_used: boolean;
  trace: Array<{ node: string; latency_ms: number; [k: string]: unknown }>;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
  session_id: string;
}

export async function agentChat(
  message: string,
  session_id = "",
): Promise<AgentResp> {
  const { data } = await api.post<AgentResp>(
    "/agent/chat",
    { message, session_id },
    { timeout: 180000 },
  );
  return data;
}

export async function listTraces(limit = 20): Promise<unknown[]> {
  const { data } = await api.get(`/traces?limit=${limit}`);
  return data;
}

export async function getEvalReport(): Promise<unknown> {
  const { data } = await api.get("/evals/report");
  return data;
}

export default api;
