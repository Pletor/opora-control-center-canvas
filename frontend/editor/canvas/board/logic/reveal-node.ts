/** Focus one newly inserted card inside the visible part of the canvas. */
export function revealNodeCenter(board: { left: number; top: number; width: number; height: number },
  visible: { left: number; right: number; top: number; bottom: number },
  node: { x: number; y: number; width: number; height: number }, currentZoom: number) {
  const width = visible.right - visible.left;
  const height = visible.bottom - visible.top;
  // A full-screen drawer must not collapse the canvas zoom to near zero.
  if (width < 120 || height < 120) return null;
  const zoom = Math.max(0.15, Math.min(currentZoom, (width - 48) / node.width, (height - 48) / node.height));
  return {
    x: node.x + node.width / 2 - ((visible.left + visible.right) / 2 - (board.left + board.width / 2)) / zoom,
    y: node.y + node.height / 2 - ((visible.top + visible.bottom) / 2 - (board.top + board.height / 2)) / zoom,
    zoom,
  };
}
