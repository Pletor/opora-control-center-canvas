import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import App from "./App";

afterEach(cleanup);

test("hlavní stránka ukazuje rozpracovaný stav", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { name: "Rozpracováno" })).toBeTruthy();
});
