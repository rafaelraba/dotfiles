import { View, div } from "gpui-kit";
import { run, props, closeOverlay, focused, agents, hc, nextCommand } from "herdr";

const BINDINGS = {
  c: ["tab.new"], r: ["tab.rename"],
  "shift-c": ["space.new"], "shift-r": ["space.rename"],
  "shift-k": ["space.close"], "shift-x": ["tab.close"],
  "-": ["pane.split", { direction: "down" }],
  v: ["pane.split", { direction: "right" }],
  x: ["pane.close"], z: ["pane.zoom"],
  h: ["pane.go", { direction: "left" }],
  j: ["pane.go", { direction: "down" }],
  k: ["pane.go", { direction: "up" }],
  l: ["pane.go", { direction: "right" }],
  p: ["tab.prev"], n: ["tab.next"],
  "shift-p": ["space.prev"], "shift-n": ["space.next"],
};
for (let n = 1; n <= 9; n++) BINDINGS[String(n)] = ["tab.select", { index: n }];

export default class TuiPrefix extends View {
  init(_props, cx) {
    this.handle = cx.focus_handle();
    this.handle.focus();
    cx.spawn(async cx => {
      for (;;) this.command(await nextCommand(), cx);
    });
  }

  command(command, cx) {
    // Resolve the terminal before dismissing the overlay; hc accepts remote addresses.
    const terminal = focused()?.terminal;
    closeOverlay(props().overlay);
    if (command === "literal" && terminal) {
      cx.spawn(async () => { await hc(["keys", terminal, "ctrl+a"]); });
    } else if (command.startsWith("agent-")) {
      const agent = agents()[Number(command.slice(6)) - 1];
      if (agent) run("agent.focus", { terminal: agent.address });
    }
  }

  key(event, cx) {
    cx.stop_propagation();
    let chord = event.keystroke;
    if (/^[A-Z]$/.test(event.key_char ?? "")) chord = "shift-" + event.key_char.toLowerCase();
    if (event.key_char === "?") chord = "?";
    if (chord === "ctrl-a") return this.command("literal", cx);
    if (/^alt-[1-9]$/.test(chord)) return this.command("agent-" + chord.slice(4), cx);
    closeOverlay(props().overlay);
    if (chord === "?") return run("app.help");
    const binding = BINDINGS[chord];
    if (binding) run(binding[0], binding[1] ?? {});
  }

  render() {
    return div().id("tui-prefix").w(1).h(1).track_focus(this.handle)
      .on_key_down((event, cx) => this.key(event, cx));
  }
}
