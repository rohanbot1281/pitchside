import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import React, { useEffect, useRef, useState } from "react";
import ToolCallCard from "./components/ToolCallCard.jsx";

const STARTERS = [
  "What matches are on today?",
  "Who wins the USMNT opener? Run the numbers.",
  "How do third-place teams advance?",
  "Simulate Spain vs Argentina",
];

let nextId = 0;
const uid = () => ++nextId;

export default function App() {
  const [turns, setTurns] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns]);

  async function send(text) {
    const question = text.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);

    const history = turns.map((t) =>
      t.role === "user"
        ? { role: "user", content: t.text }
        : {
            role: "assistant",
            content:
              t.items
                .filter((i) => i.kind === "text")
                .map((i) => i.content)
                .join("") || "(used tools)",
          }
    );

    const userTurn = { id: uid(), role: "user", text: question };
    const agentTurn = { id: uid(), role: "assistant", items: [] };
    setTurns((prev) => [...prev, userTurn, agentTurn]);

    const pushItem = (item) =>
      setTurns((prev) =>
        prev.map((t) =>
          t.id === agentTurn.id ? { ...t, items: [...t.items, item] } : t
        )
      );

    const updateItems = (fn) =>
      setTurns((prev) =>
        prev.map((t) =>
          t.id === agentTurn.id ? { ...t, items: fn(t.items) } : t
        )
      );

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: [...history, { role: "user", content: question }],
        }),
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const frames = buffer.split("\n\n");
        buffer = frames.pop();

        for (const frame of frames) {
          if (!frame.startsWith("data: ")) continue;
          const event = JSON.parse(frame.slice(6));

          if (event.type === "text") {
            updateItems((items) => {
              const last = items[items.length - 1];
              if (last?.kind === "text") {
                return [
                  ...items.slice(0, -1),
                  { ...last, content: last.content + event.delta },
                ];
              }
              return [...items, { kind: "text", content: event.delta }];
            });
          } else if (event.type === "tool_call") {
            pushItem({
              kind: "tool",
              callId: event.id,
              name: event.name,
              input: event.input,
              output: null,
            });
          } else if (event.type === "tool_result") {
            updateItems((items) =>
              items.map((i) =>
                i.kind === "tool" && i.callId === event.id
                  ? { ...i, output: event.output }
                  : i
              )
            );
          }
        }
      }
    } catch (err) {
      pushItem({
        kind: "text",
        content: `Connection problem: ${err.message}. Check that the backend is running on port 8000.`,
      });
    } finally {
      setBusy(false);
    }
  }

 return (
    <>
      <div className="backdrop" aria-hidden="true" />
      <div className="shell">
        <header className="masthead">
          <div className="badge">WC 2026</div>
          <h1>Pitchside</h1>
          <p className="tagline">Agentic match analyst — live data · simulations · knowledge base</p>
        </header>

        <main className="feed" ref={scrollRef}>
          {turns.length === 0 && (
            <div className="kickoff">
              <p>
                Ask about fixtures, advancement scenarios, history, or have the
                agent simulate any matchup between the 48 qualified teams. Tool
                calls appear in the trace as the agent works.
              </p>
              <div className="starters">
                {STARTERS.map((s) => (
                  <button key={s} onClick={() => send(s)} disabled={busy}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn) =>
            turn.role === "user" ? (
              <div key={turn.id} className="msg user">
                {turn.text}
              </div>
            ) : (
              <div key={turn.id} className="msg agent">
                {turn.items.map((item, i) =>
                  item.kind === "text" ? (
                    <div key={i} className="agent-text">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <ToolCallCard key={item.callId} {...item} />
                  )
                )}
                {busy &&
                  turn.id === turns[turns.length - 1].id &&
                  turn.items.length === 0 && (
                    <p className="agent-text thinking">analyzing…</p>
                  )}
              </div>
            )
          )}
        </main>

        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask the analyst…"
            disabled={busy}
          />
          <button type="submit" disabled={busy || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </>
  );
}