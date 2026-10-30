import { useEffect, useState } from "react";
import { Card, List, Input, Select, Spin, Tag, Button } from "antd";
import { listProducts, getCategories, type Product } from "../api/client";

export default function ProductList() {
  const [products, setProducts] = useState<Product[]>([]);
  const [cats, setCats] = useState<string[]>([]);
  const [cat, setCat] = useState("");
  const [kw, setKw] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getCategories().then(setCats).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    listProducts({ keyword: kw, category: cat, limit: 50 })
      .then(setProducts)
      .catch(() => setProducts([]))
      .finally(() => setLoading(false));
  }, [kw, cat]);

  return (
    <Card title="商品列表">
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Input.Search
          placeholder="搜商品/参数关键词"
          allowClear
          onSearch={setKw}
          style={{ flex: 1 }}
        />
        <Select
          placeholder="全部类别"
          allowClear
          style={{ width: 140 }}
          value={cat || undefined}
          onChange={(v) => setCat(v ?? "")}
          options={cats.map((c) => ({ label: c, value: c }))}
        />
      </div>
      {loading ? (
        <Spin style={{ display: "block", textAlign: "center", padding: 40 }} />
      ) : (
        <List
          grid={{ gutter: 12, column: 2 }}
          dataSource={products}
          renderItem={(p) => (
            <List.Item>
              <Card size="small" title={`${p.name}`} extra={<Tag color="blue">{p.brand}</Tag>}>
                <div style={{ fontSize: 12, color: "#888", marginBottom: 4 }}>
                  {p.category}
                </div>
                <div style={{ fontSize: 13, marginBottom: 6, color: "#555" }}>
                  {p.spec}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: "#d4380d", fontWeight: 600 }}>¥{p.price}</span>
                  <Tag color={p.stock > 5 ? "green" : "orange"}>库存 {p.stock}</Tag>
                </div>
              </Card>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
