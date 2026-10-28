// Test setup for Vitest + React Testing Library.
import "@testing-library/jest-dom/vitest"; // adds matchers like toBeInTheDocument()
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup); // unmount rendered components between tests

// jsdom (the fake browser used in tests) doesn't implement scrolling.
Element.prototype.scrollIntoView = () => {};
