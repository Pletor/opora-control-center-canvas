"""Text karty (`node-text`) v balíčku pro model: `content: {text, revision}` nebo `null`.

Text karty je podklad, typicky doslovný výňatek zadání (`docs/davka-planu.md` §4), takže ho
agent musí dostat celý a bez otevírání chatu. Prázdný text i jen ke čtení prostor (main,
kde se text nevede) jsou `null`, stejně jako jiná chybějící pole balíčku. Volající drží
zámky plátna a rozsah už ověřil; redakci tajemství dělá balíček nad celým výsledkem.
"""


def card_content(canvas, project, workspace, node_id, read_only):
    if read_only:
        return None
    value = canvas.texts.read((project, workspace, node_id))
    if not value["text"].strip():
        return None
    return {"text": value["text"], "revision": value["revision"]}
