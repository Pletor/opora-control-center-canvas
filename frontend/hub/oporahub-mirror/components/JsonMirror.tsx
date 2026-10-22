import { mirrorText } from "../logic/hub-read";

/** Zrcadlo pro agenty: přesná data pohledu jako JSON v DOM (`id` začíná `oh-`). Nic tajného sem nepatří. */
export default function JsonMirror({ id, value }: { id: `oh-${string}`; value: unknown }) {
  return <script type="application/json" id={id} dangerouslySetInnerHTML={{ __html: mirrorText(value) }} />;
}
