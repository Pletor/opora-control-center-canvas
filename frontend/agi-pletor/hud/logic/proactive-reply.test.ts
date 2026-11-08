import { describe, expect, it } from "vitest";
import type { PletorMessage } from "./pletor-client";
import { proactiveReply } from "./proactive-reply";

const human = (text: string, at = "t1"): PletorMessage => ({ role: "human", text, at });
const pletor = (text: string, at = "t2"): PletorMessage => ({ role: "pletor", text, at });
const heart = (text: string, at = "t2"): PletorMessage => ({ role: "heart", text, at });

describe("proactiveReply", () => {
  it("první načtení historie nic nečte, jen si zapamatuje poslední zprávu", () => {
    expect(proactiveReply([human("Ahoj"), heart("Srdce odpovědělo", "t3"), pletor("Jste připravený?", "t4")], undefined))
      .toEqual({ key: "t4\nJste připravený?", speak: null });
  });

  it("nová zpráva Pletora po řádku deníku srdce se přečte", () => {
    const answer = pletor("Srdce má hotovou odpověď. Jste připravený?", "t4");
    const messages = [human("Jak přihlášení?"), pletor("Ptám se srdce."), heart("Srdce odpovědělo na pq_1", "t3"), answer];
    expect(proactiveReply(messages, "t2\nPtám se srdce.").speak).toBe(answer);
    expect(proactiveReply(messages, "t4\nSrdce má hotovou odpověď. Jste připravený?").speak).toBeNull(); // už zaznělo
  });

  it("odpověď na zprávu člověka (i s řádkem deníku mezi nimi) nečte: tu přečte cesta odeslání", () => {
    expect(proactiveReply([human("Zeptej se srdce"), heart("Pletor se ptá srdce pq_1"), pletor("Ptám se.", "t3")], "t1\nZeptej se srdce").speak).toBeNull();
    expect(proactiveReply([pletor("Dřív.", "t0"), human("Ano"), pletor("Výklad.", "t3")], "t1\nAno").speak).toBeNull();
  });

  it("řádky deníku a zprávy člověka nahlas nikdy", () => {
    expect(proactiveReply([pletor("Dřív.", "t0"), heart("Srdce se ptá člověka gt_1", "t3")], "t0\nDřív.").speak).toBeNull();
    expect(proactiveReply([pletor("Dřív.", "t0"), human("Ano", "t3")], "t0\nDřív.").speak).toBeNull();
  });

  it("proaktivní zpráva v prázdném rozhovoru se přečte", () => {
    const first = pletor("Srdce se ptá.", "t1");
    expect(proactiveReply([heart("Srdce se ptá člověka gt_1", "t0"), first], null).speak).toBe(first);
  });
});
