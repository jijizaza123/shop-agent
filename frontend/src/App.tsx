import { ConfigProvider, Layout, Typography, Space } from "antd";
import ProductList from "./components/ProductList";
import AgentPanel from "./components/AgentPanel";

const { Header, Content } = Layout;
const { Title } = Typography;

export default function App() {
  return (
    <ConfigProvider
      theme={{
        token: { colorPrimary: "#1677ff", borderRadius: 6 },
      }}
    >
      <Layout style={{ minHeight: "100vh" }}>
        <Header style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Title level={3} style={{ color: "#fff", margin: 0 }}>
            极客配单
          </Title>
          <Space size={4} style={{ color: "#fff", fontSize: 12 }}>
            <span>数码选购 Agent</span>
            <span>·</span>
            <span>LangGraph + FastAPI + React</span>
          </Space>
        </Header>
        <Content style={{ padding: 16 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 420px",
              gap: 16,
            }}
          >
            <ProductList />
            <AgentPanel />
          </div>
        </Content>
      </Layout>
    </ConfigProvider>
  );
}
