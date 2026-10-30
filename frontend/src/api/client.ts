// API 客户端封装 —— 所有后端请求收口在这里
import axios from "axios";

const api = axios.create({ baseURL: "http://localhost:8000/api", timeout: 60000 });

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

export interface Product {
  id: number;
  name: string;
  category: string;
  brand: string;
  price: number;
  stock: number;
  spec: string;
}

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

export async function agentChat(message: string): Promise<AgentResp> {
  const { data } = await api.post<AgentResp>("/agent/chat", { message });
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
