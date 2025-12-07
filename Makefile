
run := uv run toad

.PHONY: run
run:
	$(run)

.PHONY: gemini-acp
gemini-acp:
	$(run) acp "gemini --experimental-acp" --project-dir ~/sandbox --title "Google Gemini"

.PHONY: claude-acp
claude-acp:
	$(run) acp "claude-code-acp" --project-dir ~/sandbox --title "Claude"


.PHONE: codex-acp
codex-acp:
	$(run) acp "codex-acp"  --project-dir ~/sandbox --title="OpenAI Codex"

.PHONY: replay
replay:
	ACP_INITIALIZE=0 $(run) acp "$(run) replay $(realpath replay.jsonl)" --project-dir ~/sandbox

.PHONY: echo
echo:
	$(run) acp "uv run echo_client.py"
