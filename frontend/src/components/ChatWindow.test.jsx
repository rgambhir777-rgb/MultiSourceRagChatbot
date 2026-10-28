import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ChatWindow from "./ChatWindow.jsx";

const turn = {
  id: 1,
  question: "What is E-207?",
  answer: "Wi-Fi failed [1].",
  sources: [],
  grounded: true,
  route: "retrieve",
  steps: [],
  status: "done",
  error: null,
  latencyMs: 4200,
  costUsd: 0.0018,
};

const setup = (props = {}) =>
  render(
    <ChatWindow
      title="New chat"
      turns={[]}
      busy={false}
      loading={false}
      onSend={vi.fn()}
      onStop={vi.fn()}
      {...props}
    />,
  );

/** True if `a` comes before `b` in the page (top to bottom in reading order). */
const isBefore = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

describe("ChatWindow", () => {
  it("puts the input at the top, above the example questions", () => {
    setup();
    const box = screen.getByLabelText(/ask a question/i);
    const heading = screen.getByRole("heading", { name: "Ask your documents" });
    expect(isBefore(box, heading)).toBe(true);
  });

  it("puts the input above the conversation", () => {
    setup({ turns: [turn] });
    const box = screen.getByLabelText(/ask a question/i);
    expect(isBefore(box, screen.getByText("What is E-207?"))).toBe(true);
  });
});
