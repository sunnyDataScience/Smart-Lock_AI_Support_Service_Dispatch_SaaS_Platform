"use client";

import { Command, Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  commandsForContext,
  filterCommands,
  nextCommandIndex,
  type CommandDefinition,
} from "@/lib/commandRegistry";
import { getCurrentSession } from "@/lib/api";
import { listSavedViews, type SavedView } from "@/lib/preferences";

export const OPEN_COMMAND_PALETTE_EVENT = "smartlock:command-palette:open";
const HISTORY_KEY = "smartlock.command_history";

export default function CommandPalette() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);

  useEffect(() => {
    const openPalette = () => setOpen(true);
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener(OPEN_COMMAND_PALETTE_EVENT, openPalette);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener(OPEN_COMMAND_PALETTE_EVENT, openPalette);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setSelected(0);
    requestAnimationFrame(() => inputRef.current?.focus());
    void listSavedViews().then(setSavedViews).catch(() => setSavedViews([]));
  }, [open]);

  const session = getCurrentSession();
  const commands = useMemo(
    () =>
      commandsForContext(
        { role: session?.role ?? null, tenantId: session?.tenantId ?? null },
        savedViews,
      ),
    [savedViews, session?.role, session?.tenantId],
  );
  const filtered = useMemo(
    () => filterCommands(commands, query),
    [commands, query],
  );

  const run = (command: CommandDefinition) => {
    const history = JSON.parse(
      window.localStorage.getItem(HISTORY_KEY) ?? "[]",
    ) as string[];
    window.localStorage.setItem(
      HISTORY_KEY,
      JSON.stringify(
        [command.command_id, ...history.filter((id) => id !== command.command_id)].slice(
          0,
          10,
        ),
      ),
    );
    window.dispatchEvent(
      new CustomEvent("smartlock:analytics", {
        detail: {
          event: command.analytics_event,
          command_id: command.command_id,
        },
      }),
    );
    setOpen(false);
    router.push(command.route);
  };

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-[100] flex justify-center bg-black/35 px-4 pt-[12vh]"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) setOpen(false);
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Command Palette"
        className="h-fit max-h-[70vh] w-full max-w-2xl overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--bg-surface)] shadow-2xl"
      >
        <div className="flex items-center gap-3 border-b border-[var(--border)] px-4">
          <Search className="h-5 w-5 text-[var(--text-secondary)]" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSelected(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setSelected((value) =>
                  nextCommandIndex(value, 1, filtered.length),
                );
              } else if (event.key === "ArrowUp") {
                event.preventDefault();
                setSelected((value) =>
                  nextCommandIndex(value, -1, filtered.length),
                );
              } else if (event.key === "Enter" && filtered[selected]) {
                event.preventDefault();
                run(filtered[selected]);
              }
            }}
            placeholder="搜尋工單、問題卡、佇列或已儲存檢視…"
            className="h-14 flex-1 bg-transparent text-sm outline-none"
          />
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="關閉"
            className="rounded-md p-2 hover:bg-[var(--bg-page)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[55vh] overflow-y-auto p-2" role="listbox">
          {filtered.length === 0 ? (
            <p className="px-3 py-10 text-center text-sm text-[var(--text-secondary)]">
              沒有符合目前權限與搜尋條件的命令
            </p>
          ) : (
            filtered.map((command, index) => (
              <button
                key={command.command_id}
                type="button"
                role="option"
                aria-selected={index === selected}
                onMouseEnter={() => setSelected(index)}
                onClick={() => run(command)}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm ${
                  index === selected
                    ? "bg-[var(--primary)]/10 text-[var(--primary)]"
                    : "hover:bg-[var(--bg-page)]"
                }`}
              >
                <Command className="h-4 w-4 shrink-0" />
                <span className="flex-1">{command.label}</span>
                <span className="text-xs text-[var(--text-disabled)]">
                  {command.required_capability}
                </span>
              </button>
            ))
          )}
        </div>
        <footer className="border-t border-[var(--border)] px-4 py-2 text-xs text-[var(--text-secondary)]">
          ↑↓ 選擇 · Enter 執行 · Esc 關閉
        </footer>
      </section>
    </div>
  );
}
