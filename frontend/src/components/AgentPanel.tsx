import { useEffect, useState } from "react";
import {
  Card, Input, List, Space, Tag, Typography, Spin, Empty, Collapse,
} from "antd";
import { RobotOutlined } from "@ant-design/icons";
import { agentChat, type AgentResp } from "../api/client";

const { Text } = Typography;

interface Msg {
  role: "user" | "agent";
  content: string;
  meta?: AgentResp;
}

export default function AgentPanel() {
  const [input, setInput] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string[]>([]);

  const send = async () => {
    const m = input.trim();
    if (!m || busy) return;
    setMsgs((prev) => [...prev, { role: "user", content: m }]);
    setInput("");
    setBusy(true);
    try {
      const r = await agentChat(m);
      setMsgs((prev) => [
        ...prev,
        { role: "agent", content: r.answer, meta: r },
      ]);
      // 自动展开最后一条 Agent 消息的工具调用
      setExpanded((prev) => [
        ...new Set([...prev, `agent-${prev.length + 1}`]),
      ]);
    } catch (e) {
      setMsgs((prev) => [
        ...prev,
        { role: "agent", content: `请求失败: ${e}` },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      title={
        <Space>
          <RobotOutlined /> Agent 对话
          {msgs.length > 0 && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {msgs.filter((m) => m.role === "agent").length} 轮
            </Text>
          )}
        </Space>
      }
    >
      <div style={{ height: 420, overflowY: "auto", padding: "0 4px" }}>
        {msgs.length === 0 ? (
          <Empty
            description="试试: 帮我配一套 5000 元以内的入门剪辑电脑"
            style={{ padding: "120px 0" }}
          />
        ) : (
          msgs.map((m, i) => (
            <div
              key={i}
              style={{
                marginBottom: 12,
                textAlign: m.role === "user" ? "right" : "left",
              }}
            >
              <div
                style={{
                  display: "inline-block",
                  maxWidth: "85%",
                  padding: "8px 12px",
                  borderRadius: 8,
                  background: m.role === "user" ? "#1677ff" : "#f5f5f5",
                  color: m.role === "user" ? "#fff" : "#333",
                  textAlign: "left",
                  whiteSpace: "pre-wrap",
                  fontSize: 14,
                }}
              >
                {m.content}
              </div>
              {m.role === "agent" && m.meta && (
                <div style={{ marginTop: 4 }}>
                  <Collapse
                    size="small"
                    defaultActiveKey={expanded}
                    items={[
                      {
                        key: `agent-${i}`,
                        label: (
                          <Space size={4}>
                            <Tag color={m.meta.fallback_used ? "orange" : "green"}>
                              {m.meta.fallback_used ? "降级" : "正常"}
                            </Tag>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              耗时 {m.meta.latency_ms}ms · token {m.meta.tokens_in}/
                              {m.meta.tokens_out} · 工具:
                              {Object.keys(m.meta.tool_results).join(", ") || "无"}
                            </Text>
                          </Space>
                        ),
                        children: (
                          <div style={{ fontSize: 12, color: "#888" }}>
                            {m.meta.trace.map((t, j) => (
                              <div key={j}>
                                [{t.node}] {String(t.latency_ms)}ms
                                {t.tools_called
                                  ? ` → ${JSON.stringify(t.tools_called)}`
                                  : ""}
                              </div>
                            ))}
                          </div>
                        ),
                      },
                    ]}
                  />
                </div>
              )}
            </div>
          ))
        )}
        {busy && <Spin style={{ display: "block", textAlign: "center", padding: 12 }} />}
      </div>

      <Space.Compact style={{ width: "100%", marginTop: 12 }}>
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="描述需求, 比如: 5000 元入门剪辑电脑, 重点 CPU 和内存"
          autoSize={{ minRows: 1, maxRows: 4 }}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
      </Space.Compact>
      <div style={{ marginTop: 8 }}>
        <Space>
          <button className="ant-btn ant-btn-primary" onClick={send} disabled={busy}>
            {busy ? "思考中…" : "发送"}
          </button>
          {msgs.length > 0 && (
            <button
              className="ant-btn"
              onClick={() => {
                setMsgs([]);
                setExpanded([]);
              }}
            >
              清空
            </button>
          )}
        </Space>
      </div>
    </Card>
  );
}
