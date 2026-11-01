// Floating scratch terminal, one persistent shell per Space.
//
// Alt+F runs `mod.open:scratch-terminal`, which opens this mod as an invisible
// 1px popup (the "launcher"). The launcher toggles a dialog holding a title bar
// (another copy of this mod, role "bar") and the shell, then closes itself.
// It works in every layout, no controller block needed.
//
// The launcher acts synchronously: commands sent from a later async step can
// sit in a queue until the app's next event, which made Alt+F feel random.
import { View, div } from "gpui-kit";
import { h_flex } from "gpui-base";
import {
  closeOverlay,
  exec,
  focused,
  hc,
  notify,
  openOverlay,
  props,
  run,
  setShared,
  shared,
  spaces,
  terminals,
  theme,
} from "herdr";

const OPEN = "scratch-terminal.open";
const TERMINALS_BY_SPACE = "scratch-terminal.terminals-by-space";
const SPACE_LABEL = "herdr-app.scratch-space";

function currentSpace() {
  const current = focused();
  return spaces().find((space) => space.id === current?.space)
    ?? spaces().find((space) => space.active)
    ?? null;
}

function liveScratch(space) {
  const address = shared(TERMINALS_BY_SPACE)?.[space.id];
  return terminals().find((terminal) =>
    terminal.state === "live" && (
      terminal.address === address || terminal.labels?.[SPACE_LABEL] === space.id
    )
  ) ?? null;
}

// Kill scratch shells whose Space is gone.
function dropOrphans() {
  const alive = new Set(spaces().map((space) => space.id));
  const map = { ...(shared(TERMINALS_BY_SPACE) ?? {}) };
  let changed = false;
  for (const spaceId of Object.keys(map)) {
    if (alive.has(spaceId)) continue;
    delete map[spaceId];
    changed = true;
  }
  for (const t of terminals()) {
    const owner = t.labels?.[SPACE_LABEL];
    if (owner && !alive.has(owner) && t.state === "live") run("terminal.kill", { terminal: t.address });
  }
  if (changed) setShared(TERMINALS_BY_SPACE, map);
}

async function createScratch(space, cwd) {
  const args = [
    "run", "--json", "--keep", "--bg", "--no-parent",
    "--label", `${SPACE_LABEL}=${space.id}`,
  ];
  if (space.machine) args.push("--on", space.machine);
  if (cwd) args.push("--cwd", cwd);

  const result = await hc(args);
  if (result.code !== 0) throw new Error(result.stderr.trim() || "hc run failed");

  const created = JSON.parse(result.stdout);
  const address = created.address ?? created.terminal?.address ?? created.result?.address;
  if (!address) throw new Error("herdr-core did not return a terminal address");
  setShared(TERMINALS_BY_SPACE, { ...(shared(TERMINALS_BY_SPACE) ?? {}), [space.id]: address });
  return address;
}

function closeSelf() {
  const self = props()?.overlay;
  if (self) closeOverlay(self);
}

function fail(error) {
  notify({
    title: "Scratch terminal",
    body: error instanceof Error ? error.message : String(error),
    level: "error",
  });
}

// Each time the dialog resizes the shell, fish redraws its prompt one row lower,
// so blank rows pile up above it. Once the dialog has closed and the shell has
// shrunk back, press Ctrl+L (bound in fish_user_key_bindings to clear + repaint,
// keeping any half-typed command). Done while hidden, so nothing flickers.
// Only for a shell: a running program gets no keys.
function tidy(terminal) {
  exec("sh", ["-c", 'sleep 0.3; hc keys "$1" ctrl+l >/dev/null', "tidy", terminal]).catch(() => {});
}

function showScratch(space, terminal) {
  const overlay = openOverlay({
    kind: "dialog",
    width: 0.8,
    height: 0.7,
    layout: {
      id: "scratch-terminal-root",
      type: "column",
      children: [
        {
          id: "scratch-terminal-title",
          type: "block",
          size: { px: 32 },
          content: { mod: "scratch-terminal", props: { role: "bar", space: space.id, terminal } },
        },
        { id: "scratch-terminal-shell", type: "block", content: { terminal } },
      ],
    },
  });
  setShared(OPEN, { overlay, space: space.id, terminal });
}

function launch(cx) {
  dropOrphans();
  const space = currentSpace();
  if (!space) return closeSelf();

  // The bar clears this when the dialog goes, however it's closed.
  const open = shared(OPEN);
  if (open) {
    closeSelf();
    closeOverlay(open.overlay);
    if (open.space === space.id) return;
  }

  const existing = liveScratch(space);
  if (existing) {
    closeSelf();
    showScratch(space, existing.address);
    return;
  }

  // First use in this Space: the shell has to be created first.
  const current = focused();
  const cwd = current?.space === space.id && current.cwd ? current.cwd : space.folder;
  cx.spawn(async (cx) => {
    try {
      const terminal = await createScratch(space, cwd);
      closeSelf();
      showScratch(space, terminal);
    } catch (error) {
      closeSelf();
      fail(error);
    }
    cx.notify();
  });
}

function closeButton(overlay) {
  const t = theme();
  return div()
    .id("scratch-terminal-close")
    .flex_none()
    .w(22)
    .h(22)
    .rounded(6)
    .flex()
    .items_center()
    .justify_center()
    .cursor_pointer()
    .text_color(t.muted)
    .hover((style) => style.bg(t.hover).text_color(t.foreground))
    .on_click(() => closeOverlay(overlay))
    .child("×");
}

function renderBar() {
  const t = theme();
  const { space: spaceId, terminal, overlay } = props() ?? {};
  const space = spaces().find((candidate) => candidate.id === spaceId);
  const shell = terminals().find((candidate) => candidate.address === terminal);

  return h_flex()
    .size_full()
    .px(12)
    .gap(8)
    .items_center()
    .bg(t.surface)
    .border_b(1)
    .border_color(t.border)
    .text_size(12)
    .child(div().flex_none().font_semibold().text_color(t.foreground).child("Scratch"))
    .child(div().flex_none().text_color(t.muted).child(space?.name ?? "Space"))
    .child(div().flex_1().min_w(0).truncate().text_color(t.dim).child(shell?.cwd ?? ""))
    .child(div().flex_none().text_size(11).text_color(t.dim).child("Alt+F"))
    .child(closeButton(overlay));
}

export default class ScratchTerminal extends View {
  init(initialProps, cx) {
    this.role = (props() ?? initialProps ?? {}).role ?? "launcher";
    if (this.role !== "launcher") return;
    try {
      launch(cx);
    } catch (error) {
      closeSelf();
      fail(error);
    }
  }

  close() {
    if (this.role !== "bar") return;
    const { overlay, terminal } = props() ?? {};
    if (shared(OPEN)?.overlay === overlay) setShared(OPEN, null);
    const shell = terminals().find((t) => t.address === terminal);
    if (shell?.program?.shell === true) tidy(terminal);
  }

  render() {
    return this.role === "bar" ? renderBar() : div().w(1).h(1);
  }
}
