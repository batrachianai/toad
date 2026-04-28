# Contributing to Textual TUI Skill

Thank you for your interest in contributing to the Textual TUI Skill!

## How to Contribute

### Reporting Issues

- Check existing issues before creating a new one
- Provide clear description and steps to reproduce
- Include skill version and Claude Code version
- Add relevant code examples if applicable

### Improving Documentation

- Fix typos, clarify instructions, add examples
- Update reference files with new patterns
- Add missing widget documentation
- Improve code examples

### Adding Examples

- Create clear, focused examples
- Include comments explaining key concepts
- Follow existing code style
- Test examples thoroughly
- Update examples/README.md

### Enhancing the Skill

- Follow the skill structure in `skill/`
- Keep SKILL.md concise (core patterns only)
- Add detailed content to reference files
- Update official-guides-index.md with new URLs
- Test skill packaging after changes

## Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/textual-tui-skill.git
cd textual-tui-skill

# Install dependencies
pip install textual textual-dev psutil

# Test examples
python examples/todo_app.py
textual run --dev examples/dashboard_app.py

# Package the skill
python scripts/package.py
```

## File Structure

```
skill/
├── SKILL.md              # Core patterns (keep concise!)
├── references/           # Detailed documentation
│   ├── widgets.md
│   ├── layouts.md
│   ├── styling.md
│   └── official-guides-index.md
└── assets/              # Example applications
    ├── todo_app.py
    ├── dashboard_app.py
    ├── data_viewer.py
    └── worker_demo.py
```

## Guidelines

### Documentation

- **SKILL.md**: Core patterns only, keep under 500 lines
- **Reference files**: Detailed examples and comprehensive coverage
- **Examples**: Working, well-commented applications
- **No dates**: Avoid specific dates unless necessary
- **Active voice**: Use imperative mood ("Create a widget" not "You can create")

### Code Style

- Follow Textual conventions
- Use type hints
- Add docstrings to classes and methods
- Keep examples focused and clear
- Comment non-obvious patterns

### Skill Content

**Include:**
- Essential patterns and best practices
- Common use cases and examples
- Links to official documentation
- Working code examples

**Avoid:**
- Verbose explanations (put in references/)
- Exact API documentation (link to official docs)
- Deprecated patterns
- Unnecessary dependencies

## Packaging

After making changes to skill content:

```bash
# Validate and package
python scripts/package.py

# Test the packaged skill
# (Install in Claude Code and verify)
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test thoroughly
5. Commit with clear messages (`git commit -m "Add amazing feature"`)
6. Push to your fork (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### PR Guidelines

- Describe what and why (not how)
- Reference related issues
- Update documentation as needed
- Keep PRs focused (one feature/fix per PR)
- Be responsive to feedback

## Questions?

Open an issue for:
- Clarifications on contributing
- Feature proposals
- General questions

## Code of Conduct

- Be respectful and constructive
- Focus on the content, not the person
- Help others learn and improve
- Keep discussions on-topic

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for making the Textual TUI Skill better!
