import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MessageBubble from "./MessageBubble.jsx";

const turn = (overrides = {}) => ({
  id: 1,
  question: "What is E-207?",
  answer: "Wi-Fi failed **badly** [1].",
  sources: [
    {
      number: 1,
      source: "guide.pdf",
      location: "guide.pdf, page 1",
      text: "E-207 ...",
      cited: true,
    },
    { number: 2, source: "faq.txt", location: "faq.txt", text: "Other", cited: false },
  ],
  grounded: true,
  route: "retrieve",
  steps: ["Searching your documents"],
  status: "done",
  error: null,
  latencyMs: 4200,
  costUsd: 0.0018,
  ...overrides,
});

describe("MessageBubble", () => {
  it("renders the question, Markdown answer, badge and stats", () => {
    render(<MessageBubble turn={turn()} />);
    expect(screen.getByText("What is E-207?")).toBeInTheDocument();
    expect(screen.getByText("badly").tagName).toBe("STRONG");
    expect(screen.getByText("Verified against sources")).toBeInTheDocument();
    expect(screen.getByText(/4\.2 s · \$0\.0018/)).toBeInTheDocument();
  });

  it("opens and highlights the source when a citation is clicked", () => {
    render(<MessageBubble turn={turn()} />);
    expect(screen.queryByText("guide.pdf, page 1")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show source 1" }));
    expect(screen.getByText("guide.pdf, page 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sources \(1 cited, 1 more\)/i })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
  });

  it("never executes HTML from the model", () => {
    const { container } = render(
      <MessageBubble
        turn={turn({ answer: "<img src=x onerror=alert(1)><script>bad()</script>" })}
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
  });

  it("opens normal links safely in a new tab", () => {
    render(<MessageBubble turn={turn({ answer: "See [docs](https://example.com)." })} />);
    const link = screen.getByRole("link", { name: "docs" });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows progress while streaming and errors when they happen", () => {
    const { rerender } = render(<MessageBubble turn={turn({ status: "streaming", answer: "" })} />);
    expect(screen.getByText("Searching your documents")).toBeInTheDocument();
    rerender(<MessageBubble turn={turn({ status: "error", error: "Server is down" })} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Server is down");
  });

  it("shows the unverified badge and no badge for direct replies", () => {
    const { rerender } = render(<MessageBubble turn={turn({ grounded: false })} />);
    expect(screen.getByText("Some claims couldn't be verified")).toBeInTheDocument();
    rerender(<MessageBubble turn={turn({ route: "direct", grounded: null, sources: [] })} />);
    expect(screen.queryByText(/verified/i)).not.toBeInTheDocument();
  });
});
