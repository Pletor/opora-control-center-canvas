# Detail karty

Drawer s cestou jedné karty: přijatý základ → změny zadání → převzetí → důkazy → PR → zápis do plánu. Zastaralé návrhy visí na větvi nad osou. `logic/card-timeline.ts` (test vedle) skládá kroky z agent-state, změnových sad (`usePlanChanges`) a běhů (`useExecutionReceipts`); rozpočet bere z `useExecutionBudgets` vybrané karty. Chybějící vazba je mezera (`◌`), nikdy „v pořádku“. Atributy `data-oh-node-id`, `data-oh-changeset`, `data-oh-parent`, `data-oh-stale`, `data-oh-execution`, `data-oh-epoch`, `data-oh-pr-link`, `data-oh-writeback`.
