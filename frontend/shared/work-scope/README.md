# Working scope

A problem is identified by project ID and stable node ID; null selects the project root. A workspace is a working revision and remains part of API authorization, not part of problem identity.

`logic/work-scope.ts` projects explicit node references without cloning records. Root includes all project records. One record linked to multiple nodes appears once in each matching context. Research keeps workspace authorization on reads and derives this view locally; this projection does not grant permissions.
