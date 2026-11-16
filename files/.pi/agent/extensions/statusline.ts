/**
 * Status line for pi, in the spirit of Claude Code's.
 *
 * Renders into pi's footer:
 *    ~/code/app · claude-opus-5 · high · ███░░░░░░░ 28% (57k/200k) · $0.42
 *
 * Updates when the model changes, when the reasoning effort changes, and at
 * the end of every turn. Toggle with /statusline.
 */

import { homedir } from "node:os";
import { sep } from "node:path";
import type { AssistantMessage } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const KEY = "statusline";
const BAR_WIDTH = 10;
/** Nerd Font folder glyph (nf-fa-folder); the terminal font ships it. */
const FOLDER_ICON = "";
/** Trailing path segments to keep before eliding the middle of a long path. */
const PATH_SEGMENTS = 3;

/** Reasoning effort -> theme color role. */
const EFFORT_COLOR: Record<string, string> = {
	off: "dim",
	minimal: "dim",
	low: "success",
	medium: "accent",
	high: "accent",
	xhigh: "warning",
	max: "error",
};

function contextColor(percent: number): string {
	if (percent >= 85) return "error";
	if (percent >= 65) return "warning";
	return "success";
}

function meter(percent: number): string {
	const clamped = Math.max(0, Math.min(100, percent));
	const filled = Math.round((clamped / 100) * BAR_WIDTH);
	return "█".repeat(filled) + "░".repeat(BAR_WIDTH - filled);
}

function tokens(n: number): string {
	if (n < 1000) return `${n}`;
	if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10_000 ? 1 : 0)}k`;
	return `${(n / 1_000_000).toFixed(1)}M`;
}

/** Working directory, shortened the way a shell prompt shortens it. */
function shortPath(cwd: string): string {
	const home = homedir();
	const withTilde = cwd === home ? "~" : cwd.startsWith(home + sep) ? `~${cwd.slice(home.length)}` : cwd;

	const segments = withTilde.split(sep).filter((s) => s !== "");
	if (segments.length <= PATH_SEGMENTS) return withTilde;
	return `…${sep}${segments.slice(-PATH_SEGMENTS).join(sep)}`;
}

/** Session cost so far, summed off the assistant messages on this branch. */
function sessionCost(ctx: ExtensionContext): number {
	let total = 0;
	for (const entry of ctx.sessionManager.getBranch()) {
		if (entry.type === "message" && entry.message.role === "assistant") {
			total += (entry.message as AssistantMessage).usage.cost.total;
		}
	}
	return total;
}

export default function (pi: ExtensionAPI) {
	let enabled = true;

	function render(
		ctx: ExtensionContext,
		model?: { provider?: string; id?: string },
		effort?: string,
	): void {
		if (!enabled) {
			ctx.ui.setStatus(KEY, undefined);
			return;
		}

		const theme = ctx.ui.theme;
		const active = model ?? ctx.model;
		const level = effort ?? ctx.thinkingLevel ?? "off";

		const parts: string[] = [
			`${theme.fg("dim", `${FOLDER_ICON} `)}${theme.fg("accent", shortPath(ctx.cwd))}`,
			theme.fg("accent", active?.id ?? "no-model"),
			theme.fg(EFFORT_COLOR[level] ?? "dim", level),
		];

		const usage = ctx.getContextUsage?.();
		if (usage?.percent != null) {
			const color = contextColor(usage.percent);
			const detail =
				usage.tokens != null && usage.contextWindow > 0
					? ` (${tokens(usage.tokens)}/${tokens(usage.contextWindow)})`
					: "";
			parts.push(
				`${theme.fg(color, meter(usage.percent))} ${theme.fg(color, `${usage.percent.toFixed(0)}%`)}${theme.fg("dim", detail)}`,
			);
		}

		const cost = sessionCost(ctx);
		if (cost > 0) parts.push(theme.fg("dim", `$${cost.toFixed(2)}`));

		ctx.ui.setStatus(KEY, parts.join(theme.fg("dim", " · ")));
	}

	// Resuming a session does not fire model_select, so seed it at startup.
	pi.on("session_start", async (_event, ctx) => render(ctx));
	pi.on("model_select", async (event, ctx) => render(ctx, event.model));
	pi.on("thinking_level_select", async (event, ctx) => render(ctx, undefined, event.level));
	// Context and cost only settle once the turn is done.
	pi.on("turn_end", async (_event, ctx) => render(ctx));

	pi.registerCommand("statusline", {
		description: "Toggle the pi status line (model, effort, context, cost)",
		handler: async (_args, ctx) => {
			enabled = !enabled;
			render(ctx);
			ctx.ui.notify(`Status line ${enabled ? "shown" : "hidden"}`, "info");
		},
	});
}
