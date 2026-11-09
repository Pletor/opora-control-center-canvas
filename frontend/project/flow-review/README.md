# Posouzení workflow

Scoped `flowReview` + `flowOperation` opens one native immutable version or node run. The projection shows selected versus active version and read-only graph; missing IDs never fall back to another version. Human actions use existing native routes with `expectedReviewDigest` checked under the registry lock. A stale review requires refresh. This UI creates no parallel approval record and does not make agent requests human decisions.
