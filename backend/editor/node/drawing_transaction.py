"""Caller-owned drawing revision writes shared by atomic content acceptance."""
from backend.editor.node.drawing_files import DrawingFileStore
from backend.editor.node.drawings import DrawingStore, image_file_ids, validate_scene


def save_in_transaction(canvas, db, scope, expected_revision, scene, saved_at):
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("Invalid drawing source revision.")
    encoded = validate_scene(scene)
    current = DrawingStore(canvas).read(scope)
    if current["revision"] != expected_revision:
        raise ValueError("Drawing source revision changed.")
    if DrawingFileStore(canvas).missing(db, scope[0], image_file_ids(scene)):
        raise ValueError("Drawing image is not uploaded.")
    revision = expected_revision + 1
    db.execute("INSERT INTO drawing_revisions VALUES(?,?,?,?,?,?)",
               (*scope, revision, encoded, saved_at))
    return {"scene": scene, "revision": revision, "saved_at": saved_at}
