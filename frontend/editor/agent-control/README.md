# Agent control

Hook is the third tab in the single right-side Agent Navbar mount. It calls the Hook, LSP, and semantic-search HTTP contracts directly; it never stores policy locally or starts an external process.

Components receive scope/read-only state from `AgentNavbar`. `AgentControlPanel` applies scope tickets before accepting asynchronous Hook/LSP/event results. The binding form stays mounted after a failed POST so a conflict cannot erase the operator's draft.
