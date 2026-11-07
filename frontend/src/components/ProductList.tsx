import { useEffect, useState } from "react";
import {
  Button, Card, Input, List, Select, Spin, Tag, message,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import {
  listProducts, getCategories, addToCart, type Product,
} from "../api/client";

interface Props {
  onCartChanged: () => void;
}

export default function ProductList({ onCartChanged }: Props) {
  const [products, setProducts] = useState<Product[]>([]);
  const [cats, setCats] = useState<string[]>([]);
  const [cat, setCat] = useState("");
  const [kw, setKw] = useState("");
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<number | null>(null);

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

  const add = async (p: Product) => {
    setAdding(p.id);
    try {
      await addToCart(p.id, 1);
      message.success(`已加入购物车: ${p.name}`);
      onCartChanged();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "加入失败");
    } finally {
      setAdding(null);
    }
  };

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
              <div style={{ width: "100%" }}>
                <Card
                  size="small"
                  title={p.name}
                  extra={<Tag color="blue">{p.brand}</Tag>}
                >
                  <div style={{ fontSize: 12, color: "#888", marginBottom: 4 }}>
                    {p.category}
                  </div>
                  <div style={{ fontSize: 13, marginBottom: 8, color: "#555" }}>
                    {p.spec}
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ color: "#d4380d", fontWeight: 600 }}>¥{p.price}</span>
                    <Tag color={p.stock > 5 ? "green" : "orange"}>库存 {p.stock}</Tag>
                  </div>
                  <Button
                    type="primary"
                    size="small"
                    icon={<PlusOutlined />}
                    block
                    loading={adding === p.id}
                    onClick={() => add(p)}
                  >
                    加入购物车
                  </Button>
                </Card>
              </div>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}
