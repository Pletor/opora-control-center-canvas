"""Symboly z rozdílu commitu: TS/TSX regex a testy (Python `ast` a routy kryje test_plan_reality.py nad gitem)."""
from backend.canvas import plan_reality_code as pr


def test_typescript_symbols_and_tests():
    lines = ["import x from 'y'", "export function Karta() {", "  return 1", "}", "export const pomoc = 2",
             "test('karta se vykreslí', () => {", "  expect(1).toBe(1)", "})"]
    assert pr.symbols_of("a.tsx", lines, {3}) == [("symbol", "Karta", 2)]
    assert pr.symbols_of("a.test.ts", lines, {7}) == [("test", "karta se vykreslí", 6)]
    assert pr.symbols_of("a.md", lines) == []
