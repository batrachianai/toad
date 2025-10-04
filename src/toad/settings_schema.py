from toad.settings import SchemaDict

import llm

MODEL_CHOICES = sorted([model.model_id for model in llm.get_models()])


SCHEMA: list[SchemaDict] = [
    {
        "key": "llm",
        "title": "LLM Model",
        "help": "Configure the model used in chat. Note that this is temporary until the project feature is implemented",
        "type": "object",
        "fields": [
            {
                "key": "model",
                "type": "choices",
                "title": "Model name",
                "help": "The model to use.",
                "choices": MODEL_CHOICES,
                "default": "gpt-3.5-turbo",
            }
        ],
    },
    {
        "key": "ui",
        "title": "User interface settings",
        "help": "The following settings allow you to customize the look and feel of the User Interface.",
        "type": "object",
        "fields": [
            {
                "key": "footer",
                "title": "Enabled footer?",
                "help": "Disable the footer if you want additional room.",
                "type": "boolean",
                "default": True,
            },
            {
                "key": "column",
                "title": "Enable column?",
                "help": "Enable for a fixed column size. Disable to use the full screen width.",
                "type": "boolean",
                "default": True,
            },
            {
                "key": "column-width",
                "title": "Width of the column",
                "help": "Width of the column if enabled. Minimum 40 characters.",
                "type": "integer",
                "default": 100,
                "validate": [{"type": "minimum", "value": 40}],
            },
            {
                "key": "scrollbar",
                "title": "Scrollbar size",
                "type": "choices",
                "default": "normal",
                "choices": ["normal", "thin", "hidden"],
            },
            {
                "key": "theme",
                "title": "Theme",
                "help": "One of the builtin Textual themes.",
                "type": "choices",
                "default": "dracula",
                "choices": [
                    "catppuccin-latte",
                    "catppuccin-mocha",
                    "dracula",
                    "flexoki",
                    "gruvbox",
                    "monokai",
                    "nord",
                    "solarized-light",
                    "textual-dark",
                    "textual-light",
                    "tokyo-night",
                ],
            },
            {
                "key": "throbber",
                "title": "Thinking animation",
                "help": "Animation to show while the agent is busy",
                "type": "choices",
                "default": "quotes",
                "choices": [
                    "pulse",
                    "quotes",
                ],
            },
        ],
    },
    {
        "key": "agent",
        "title": "Agent settings",
        "help": "Customize how you interact with agents",
        "type": "object",
        "fields": [
            {
                "key": "thoughts",
                "title": "Agent thoughts",
                "help": "Show agent's 'thoughts' in the conversation?",
                "type": "boolean",
            }
        ],
    },
    {
        "key": "diff",
        "title": "Diff view settings",
        "help": "Customize how diffs are displayed.",
        "type": "object",
        "fields": [
            {
                "key": "view",
                "title": "Display preference",
                "default": "auto",
                "type": "choices",
                "choices": ["unified", "split", "auto"],
            }
        ],
    },
    {
        "key": "user",
        "title": "User information",
        "help": "Your details.",
        "type": "object",
        "fields": [
            {
                "key": "name",
                "title": "Your name",
                "type": "string",
                "default": "$USER",
            },
            {
                "key": "email",
                "title": "Your email",
                "type": "string",
                "validate": [{"type": "is_email"}],
                "default": "",
            },
        ],
    },
    {
        "key": "accounts",
        "title": "User accounts",
        "help": "Account details here",
        "type": "object",
        "fields": [
            {
                "key": "anthropic",
                "type": "object",
                "title": "Anthropic account",
                "help": "Instructions how to get an API Key",
                "fields": [
                    {
                        "key": "apikey",
                        "help": "Your API Key goes here",
                        "title": "API Key",
                        "type": "string",
                        "default": "$ANTHROPIC_API_KEY",
                    }
                ],
            },
            {
                "key": "openai",
                "type": "object",
                "title": "OpenAI account",
                "help": "Instructions how to get an OpenAPI API key",
                "fields": [
                    {
                        "key": "apikey",
                        "help": "Your API key goes here",
                        "title": "API Key",
                        "type": "string",
                        "default": "$OPENAI_API_KEY",
                    }
                ],
            },
        ],
    },
]
