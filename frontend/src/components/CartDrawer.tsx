import { useEffect, useState } from "react";
import {
  Button, Card, Drawer, Empty, InputNumber, List, Popconfirm, Space, Tag,
  Typography, message,
} from "antd";
import { ShoppingCartOutlined } from "@ant-design/icons";
import {
  getCart, updateCartQty, checkout,
  type Product, type CartResp,
} from "../api/client";

interface Props {
  open: boolean;
  onClose: () => void;
  products: Product[];            // 用于把 cart item 的 product_id 换成商品详情
  onChanged: () => void;         // 购物车变化后通知父组件刷新
}

const { Text, Title } = Typography;

export default function CartDrawer({ open, onClose, products, onChanged }: Props) {
  const [cart, setCart] = useState<CartResp>({ items: [], total: 0 });
  const [placing, setPlacing] = useState(false);

  useEffect(() => {
    if (open) getCart().then(setCart).catch(() => {});
  }, [open]);

  const findProduct = (id: number) => products.find((p) => p.id === id);

  const changeQty = async (pid: number, qty: number) => {
    const r = await updateCartQty(pid, qty);
    setCart(r);
    onChanged();
  };

  const doCheckout = async () => {
    setPlacing(true);
    try {
      const r = await checkout();
      message.success(r.msg);
      setCart({ items: [], total: 0 });
      onChanged();
      onClose();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "下单失败");
    } finally {
      setPlacing(false);
    }
  };

  return (
    <Drawer
      title={
        <Space>
          <ShoppingCartOutlined />
          购物车
          {cart.items.length > 0 && (
            <Tag color="blue">{cart.items.length} 种商品</Tag>
          )}
        </Space>
      }
      open={open}
      onClose={onClose}
      size={420}
      footer={
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <Text type="secondary">合计</Text>{" "}
            <Text strong style={{ fontSize: 20, color: "#d4380d" }}>
              ¥{cart.total.toFixed(2)}
            </Text>
          </div>
          <Button
            type="primary"
            size="large"
            loading={placing}
            disabled={cart.items.length === 0}
            onClick={doCheckout}
          >
            结算下单
          </Button>
        </div>
      }
    >
      {cart.items.length === 0 ? (
        <Empty description="购物车是空的" style={{ marginTop: 80 }} />
      ) : (
        <List
          itemLayout="vertical"
          dataSource={cart.items}
          renderItem={(it) => {
            const p = findProduct(it.product_id);
            return (
              <List.Item
                key={it.product_id}
                actions={[
                  <Popconfirm
                    title="移除该商品?"
                    onConfirm={() => changeQty(it.product_id, 0)}
                  >
                    <Button danger size="small">移除</Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={p?.name ?? `#${it.product_id}`}
                  description={p ? `${p.category} · ${p.brand}` : ""}
                />
                <Space style={{ width: "100%", justifyContent: "space-between" }}>
                  <Text type="secondary">单价 ¥{(p?.price ?? 0).toFixed(0)}</Text>
                  <Space size={4}>
                    <Text type="secondary">数量</Text>
                    <InputNumber
                      min={0}
                      max={p?.stock ?? 99}
                      value={it.qty}
                      size="small"
                      style={{ width: 70 }}
                      onChange={(v) =>
                        v != null && changeQty(it.product_id, v)
                      }
                    />
                  </Space>
                  <Text strong>¥{((p?.price ?? 0) * it.qty).toFixed(0)}</Text>
                </Space>
              </List.Item>
            );
          }}
        />
      )}
    </Drawer>
  );
}
