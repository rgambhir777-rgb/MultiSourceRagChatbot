import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ChatInput from "./ChatInput.jsx";

const setup = (props = {}) => {
  const onSend = vi.fn();
  const onStop = vi.fn();
  render(<ChatInput onSend={onSend} onStop={onStop} busy={false} disabled={false} {...props} />);
  return { onSend, onStop, box: screen.getByLabelText(/ask a question/i) };
};

describe("ChatInput", () => {
  it("sends on Enter and clears the box", () => {
    const { onSend, box } = setup();
    fireEvent.change(box, { target: { value: "  What is E-207?  " } });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSend).toHaveBeenCalledWith("What is E-207?");
    expect(box).toHaveValue("");
  });

  it("does not send on Shift+Enter (that adds a new line)", () => {
    const { onSend, box } = setup();
    fireEvent.change(box, { target: { value: "line one" } });
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables Send for empty text", () => {
    setup();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });

  it("shows Stop while an answer is streaming", () => {
    const { onStop } = setup({ busy: true });
    fireEvent.click(screen.getByRole("button", { name: "Stop" }));
    expect(onStop).toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Send" })).not.toBeInTheDocument();
  });
});
