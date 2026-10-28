// End-to-end UI flow with the API faked: open the app, ask, watch it stream, click a citation.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App.jsx";

vi.mock("./api/client.js", () => ({
  listSessions: vi.fn(),
  createSession: vi.fn(),
  deleteSession: vi.fn(),
  getHistory: vi.fn(),
  listJobs: vi.fn(),
  listDocuments: vi.fn(),
  getJob: vi.fn(),
  uploadFiles: vi.fn(),
  ingestGithub: vi.fn(),
}));
vi.mock("./api/sse.js", () => ({ streamChat: vi.fn() }));

const client = await import("./api/client.js");
const { streamChat } = await import("./api/sse.js");

const SESSION = {
  id: "s1",
  title: "New chat",
  turn_count: 0,
  created_at: "2026-10-27T10:00:00Z",
  updated_at: "2026-10-27T10:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  client.listSessions.mockResolvedValue([]);
  client.createSession.mockResolvedValue(SESSION);
  client.getHistory.mockResolvedValue({ session: SESSION, turns: [] });
});

describe("App", () => {
  it("creates a conversation on the first message and streams the answer", async () => {
    streamChat.mockImplementation(async ({ onEvent }) => {
      onEvent({ event: "status", data: { step: "Searching your documents" } });
      onEvent({ event: "token", data: { text: "E-207 means " } });
      onEvent({ event: "token", data: { text: "Wi-Fi failed [1]." } });
      onEvent({
        event: "sources",
        data: {
          sources: [
            { number: 1, source: "g.pdf", location: "g.pdf, page 1", text: "E-207", cited: true },
          ],
        },
      });
      onEvent({
        event: "done",
        data: { answer: "E-207 means Wi-Fi failed [1].", grounded: true, route: "retrieve" },
      });
    });

    render(<App />);
    const box = await screen.findByLabelText(/ask a question/i);
    fireEvent.change(box, { target: { value: "What is E-207?" } });
    fireEvent.keyDown(box, { key: "Enter" });

    expect(await screen.findByText("Verified against sources")).toBeInTheDocument();
    expect(client.createSession).toHaveBeenCalledTimes(1);
    expect(streamChat).toHaveBeenCalledWith(
      expect.objectContaining({ sessionId: "s1", message: "What is E-207?" }),
    );
    expect(screen.getByText(/E-207 means Wi-Fi failed/)).toBeInTheDocument();
    // The first message must not be wiped by the new conversation's (empty) history load.
    expect(screen.getByText("What is E-207?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show source 1" }));
    expect(screen.getByText("g.pdf, page 1")).toBeInTheDocument();
  });

  it("New chat does not create an empty conversation on the server", async () => {
    client.listSessions.mockResolvedValue([{ ...SESSION, title: "Old chat", turn_count: 1 }]);
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "+ New chat" }));
    expect(await screen.findByRole("heading", { name: "Ask your documents" })).toBeVisible();
    expect(client.createSession).not.toHaveBeenCalled();
  });

  it("shows a friendly error when the stream fails", async () => {
    client.listSessions.mockResolvedValue([SESSION]);
    streamChat.mockImplementation(async ({ onEvent }) => {
      onEvent({ event: "error", data: { message: "The language model is busy right now." } });
    });

    render(<App />);
    const box = await screen.findByLabelText(/ask a question/i);
    await waitFor(() => expect(client.getHistory).toHaveBeenCalledWith("s1"));
    fireEvent.change(box, { target: { value: "hi" } });
    fireEvent.keyDown(box, { key: "Enter" });

    expect(await screen.findByRole("alert")).toHaveTextContent("busy right now");
    expect(client.createSession).not.toHaveBeenCalled();
  });

  it("reopens a saved conversation from its history", async () => {
    client.listSessions.mockResolvedValue([{ ...SESSION, title: "Warranty", turn_count: 1 }]);
    client.getHistory.mockResolvedValue({
      session: SESSION,
      turns: [
        {
          question: "How long is the warranty?",
          answer: "Two years [1].",
          sources: [],
          grounded: true,
          route: "retrieve",
        },
      ],
    });
    render(<App />);
    expect(await screen.findByText(/Two years/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Warranty" })).toBeInTheDocument();
  });
});

describe("App in React StrictMode (development double-run of effects)", () => {
  it("still loads the open conversation", async () => {
    const { StrictMode } = await import("react");
    // As after a page reload: the last open conversation is remembered, so its history load
    // starts at mount, exactly when StrictMode runs effects twice.
    window.localStorage.setItem("ragchat.activeSession", SESSION.id);
    client.listSessions.mockResolvedValue([{ ...SESSION, title: "Warranty", turn_count: 1 }]);
    client.getHistory.mockResolvedValue({
      session: SESSION,
      turns: [
        {
          question: "Q?",
          answer: "Two years [1].",
          sources: [],
          grounded: true,
          route: "retrieve",
        },
      ],
    });
    render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
    expect(await screen.findByText(/Two years/)).toBeInTheDocument();
    expect(screen.queryByText("Loading conversation…")).not.toBeInTheDocument();
  });
});
