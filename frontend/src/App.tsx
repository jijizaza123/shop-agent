import { useState } from "react";
import { Badge, Button, ConfigProvider, Layout, Typography, Space } from "antd";
import { ShoppingCartOutlined } from "@ant-design/icons";
import ProductList from "./components/ProductList";
import AgentPanel from "./components/AgentPanel";
import CartDrawer from "./components/CartDrawer";
import { getCart, type CartResp, type Product } from "./api/client";

const { Header, Content } = Layout;
const { Title } = Typography;

export default function App() {
  const [cartOpen, setCartOpen] = useState(false);
  const [cart, setCart] = useState<CartResp>({ items: [], total: 0 });
  const [products, setProducts] = useState<Product[]>([]);

  // 轮询购物车数量(演示用, 真实项目用 websocket/事件)
  const refreshCart = () => {
    getCart().then(setCart).catch(() => {});
  };
  const refreshProducts = () => {
    // 结算后库存变化, 重拉商品列表
    import("./api/client").then(({ listProducts }) =>
      listProducts({ limit: 50 }).then(setProducts).catch(() => {}),
    );
  };
  const onCartChanged = () => {
    refreshCart();
    refreshProducts();
  };

  return (
    <ConfigProvider
      theme={{ token: { colorPrimary: "#1677ff", borderRadius: 6 } }}
    >
      <Layout style={{ minHeight: "100vh" }}>
        <Header
          style={{ display: "flex", alignItems: "center", gap: 16, justifyContent: "space-between" }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Title level={3} style={{ color: "#fff", margin: 0 }}>
              极客配单
            </Title>
            <Space size={4} style={{ color: "#fff", fontSize: 12 }}>
              <span>数码选购 Agent</span>
              <span>·</span>
              <span>LangGraph + FastAPI + React</span>
            </Space>
          </div>
          <Badge count={cart.items.length} size="small">
            <Button
              icon={<ShoppingCartOutlined />}
              style={{ background: "transparent", color: "#fff", border: "none" }}
              onClick={() => setCartOpen(true)}
            >
              购物车
            </Button>
          </Badge>
        </Header>

        <Content style={{ padding: 16 }}>
          <div
            style={{ display: "grid", gridTemplateColumns: "1fr 420px", gap: 16 }}
          >
            <ProductList onCartChanged={onCartChanged} />
            <AgentPanel />
          </div>
          <CartDrawer
            open={cartOpen}
            onClose={() => setCartOpen(false)}
            products={products}
            onChanged={onCartChanged}
          />
        </Content>
      </Layout>
    </ConfigProvider>
  );
}
