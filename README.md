# Toad

Welcome to the Toad repository!

This repository is currently private.
If you are here, it is because you had a personal invite from me, and I value your opinion.
I'm looking for early feedback, and potential collaboration in the near future.

Please use the Discussions tab for your feedback.
Avoid issues and PRs for now, unless we've agreed on them in the Discussions tab.
I am working quite fast, and chances are I am aware of most of the issues.



https://github.com/user-attachments/assets/502fbb70-b44e-416f-9daf-4e337cd75d5a

## What is Toad?

Toad is a universal interface to AI agents, which includes chat bots and agentic coding.
Here's a tounge-in-check write up on my blog: https://willmcgugan.github.io/announcing-toad/

## Talk about Toad!

Please **do** talk about Toad!
Generating a buzz ahead of the first open release will be very benefitial.
You may share your thoughts on social media if you wish, in addition to screenshots, and videos (but obviously no code from this repository).
But please only talk about features that have been implemented--I would like to keep some things under-wraps until the first public release.
Understood that is a big vague.
Feel free to ask if there is any doubt.

I intend to release a first public version when there is enough core functionality, under an Open Source license (probably MIT).

## Requirements

I'm developing this on macOS. I would expect it to work on Linux. Windows support may lag behind, but will catch up.

Any terminal will work, although if you are using the default terminal on macOS you will get a much reduced experience.
If you are on macOS I would recommend upgrading to [iTerm2](https://iterm2.com/), which is what I use.

Related: I have heard the next version of macOS will ship with a much improved terminal.

## Getting started

I'm using the awesome UV project.

Assuming you have UV installed, running toad should be as simple as cloning the repository and running the following:

```
uv run toad
```

You should also have a `OPENAI_API_KEY` environment variable with your OpenAI API key.


## State of play

This project is obviously very young, with plenty do do.
It is still mostly UI with a few experiements implemented with Simon Willison's `llm` library.
Ultimately all the API interactions will be moved to a back-end subprocess (see my [blog post](https://willmcgugan.github.io/streaming-markdown/)) for context.


The following is a list of expected ToDo items.
I will keep this up-to-date as I go.

In no particular order:

- [ ] Back-end protocol
- [ ] Back-end library for Python
- [ ] Various input prompts (multiple choice)
- [ ] ToDo lists for the agent to update.
- [ ] Animated code updates. Something that looks like a real user working. This is purely theatre, but I expect this to make an impact.
- [ ] Fancy input with auto-complete, and Markdown TextArea
- [ ] Slash commands (with auto complete)
- [ ] File selector with `@` syntax
- [ ] Agent selector
- [ ] Settings manager (Backed by JSON with a editor like VSCode)

## Thanks

Thanks for being a part of this!
