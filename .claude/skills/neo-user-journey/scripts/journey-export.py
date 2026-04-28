#!/usr/bin/env python3
"""
User Journey Export Utility

Converts user journey definitions to various output formats:
- Mermaid diagrams
- Markdown tables
- Interactive HTML
- Figma-compatible JSON

Usage:
    python journey-export.py journey.json --format mermaid
    python journey-export.py journey.json --format html --output journey.html
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class JourneyStep:
    """Represents a single step in a user journey."""
    name: str
    action: str
    touchpoint: str
    emotion: int  # -3 to +3
    emotion_label: str
    pain_points: List[str]
    opportunities: List[str]
    notes: str = ""


@dataclass
class UserJourney:
    """Represents a complete user journey."""
    name: str
    persona: str
    goal: str
    steps: List[JourneyStep]
    metadata: Dict[str, Any]


def emotion_to_emoji(emotion: int) -> str:
    """Convert emotion score to emoji."""
    emoji_map = {
        3: "😄",
        2: "🙂",
        1: "😊",
        0: "😐",
        -1: "😕",
        -2: "😟",
        -3: "😤",
    }
    return emoji_map.get(emotion, "😐")


def parse_journey(data: Dict) -> UserJourney:
    """Parse JSON data into UserJourney object."""
    steps = []
    for step_data in data.get("steps", []):
        steps.append(JourneyStep(
            name=step_data.get("name", ""),
            action=step_data.get("action", ""),
            touchpoint=step_data.get("touchpoint", ""),
            emotion=step_data.get("emotion", 0),
            emotion_label=step_data.get("emotion_label", "Neutral"),
            pain_points=step_data.get("pain_points", []),
            opportunities=step_data.get("opportunities", []),
            notes=step_data.get("notes", ""),
        ))

    return UserJourney(
        name=data.get("name", "Untitled Journey"),
        persona=data.get("persona", "Unknown User"),
        goal=data.get("goal", ""),
        steps=steps,
        metadata=data.get("metadata", {}),
    )


def export_mermaid(journey: UserJourney) -> str:
    """Export journey as Mermaid flowchart."""
    lines = [
        f"---",
        f"title: {journey.name}",
        f"---",
        f"flowchart TD",
    ]

    # Add nodes
    for i, step in enumerate(journey.steps):
        node_id = f"S{i}"
        emoji = emotion_to_emoji(step.emotion)

        # Style based on emotion
        if step.emotion >= 2:
            style = "fill:#d4edda,stroke:#28a745"
        elif step.emotion <= -2:
            style = "fill:#f8d7da,stroke:#dc3545"
        else:
            style = "fill:#fff,stroke:#6c757d"

        lines.append(f'    {node_id}["{emoji} {step.name}<br/>{step.action}"]')
        lines.append(f'    style {node_id} {style}')

    # Add connections
    for i in range(len(journey.steps) - 1):
        lines.append(f"    S{i} --> S{i+1}")

    # Add legend
    lines.extend([
        "",
        f"    subgraph Legend",
        f'        L1["😄 Positive"]',
        f'        L2["😐 Neutral"]',
        f'        L3["😤 Negative"]',
        f"    end",
    ])

    return "\n".join(lines)


def export_markdown(journey: UserJourney) -> str:
    """Export journey as Markdown table."""
    lines = [
        f"# {journey.name}",
        "",
        f"**Persona:** {journey.persona}",
        f"**Goal:** {journey.goal}",
        "",
        "## Journey Map",
        "",
        "| Step | Action | Touchpoint | Emotion | Pain Points | Opportunities |",
        "|------|--------|------------|---------|-------------|---------------|",
    ]

    for step in journey.steps:
        emoji = emotion_to_emoji(step.emotion)
        pain = ", ".join(step.pain_points) if step.pain_points else "-"
        opps = ", ".join(step.opportunities) if step.opportunities else "-"

        lines.append(
            f"| {step.name} | {step.action} | {step.touchpoint} | "
            f"{emoji} {step.emotion_label} | {pain} | {opps} |"
        )

    # Add emotional graph
    lines.extend([
        "",
        "## Emotional Journey",
        "",
        "```",
    ])

    # ASCII emotional graph
    graph_height = 7  # +3 to -3
    for level in range(3, -4, -1):
        row = f"{level:+d} |"
        for step in journey.steps:
            if step.emotion == level:
                row += " * "
            else:
                row += "   "
        lines.append(row)

    lines.append("   +" + "-" * (len(journey.steps) * 3))
    step_labels = "    " + "".join(f"{i+1:^3}" for i in range(len(journey.steps)))
    lines.append(step_labels)
    lines.append("```")

    return "\n".join(lines)


def export_html(journey: UserJourney) -> str:
    """Export journey as interactive HTML."""

    steps_html = ""
    for i, step in enumerate(journey.steps):
        emoji = emotion_to_emoji(step.emotion)

        # Determine card color based on emotion
        if step.emotion >= 2:
            color_class = "positive"
        elif step.emotion <= -2:
            color_class = "negative"
        else:
            color_class = "neutral"

        pain_html = "".join(f"<li>{p}</li>" for p in step.pain_points) if step.pain_points else "<li>None identified</li>"
        opp_html = "".join(f"<li>{o}</li>" for o in step.opportunities) if step.opportunities else "<li>None identified</li>"

        steps_html += f"""
        <div class="step-card {color_class}" data-step="{i+1}">
            <div class="step-number">{i+1}</div>
            <div class="step-content">
                <h3>{step.name} {emoji}</h3>
                <p class="action"><strong>Action:</strong> {step.action}</p>
                <p class="touchpoint"><strong>Touchpoint:</strong> {step.touchpoint}</p>
                <p class="emotion"><strong>Feeling:</strong> {step.emotion_label} ({step.emotion:+d})</p>
                <div class="details">
                    <div class="pain-points">
                        <h4>Pain Points</h4>
                        <ul>{pain_html}</ul>
                    </div>
                    <div class="opportunities">
                        <h4>Opportunities</h4>
                        <ul>{opp_html}</ul>
                    </div>
                </div>
            </div>
        </div>
        """

    # Generate emotion data for chart
    emotion_data = json.dumps([s.emotion for s in journey.steps])
    step_names = json.dumps([s.name for s in journey.steps])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{journey.name}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 2rem;
            line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{
            background: white;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #333; margin-bottom: 0.5rem; }}
        .meta {{ color: #666; }}
        .chart-container {{
            background: white;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .journey {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        .step-card {{
            background: white;
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            gap: 1rem;
            transition: transform 0.2s, box-shadow 0.2s;
            border-left: 4px solid #6c757d;
        }}
        .step-card:hover {{
            transform: translateX(4px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}
        .step-card.positive {{ border-left-color: #28a745; background: #f8fff8; }}
        .step-card.negative {{ border-left-color: #dc3545; background: #fff8f8; }}
        .step-number {{
            width: 40px;
            height: 40px;
            background: #333;
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            flex-shrink: 0;
        }}
        .step-content {{ flex: 1; }}
        .step-content h3 {{ color: #333; margin-bottom: 0.5rem; }}
        .action, .touchpoint, .emotion {{ margin-bottom: 0.25rem; color: #555; }}
        .details {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid #eee;
        }}
        .details h4 {{ font-size: 0.9rem; color: #666; margin-bottom: 0.5rem; }}
        .details ul {{ padding-left: 1.2rem; font-size: 0.9rem; color: #555; }}
        .pain-points h4 {{ color: #dc3545; }}
        .opportunities h4 {{ color: #28a745; }}
        @media (max-width: 768px) {{
            .details {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{journey.name}</h1>
            <p class="meta"><strong>Persona:</strong> {journey.persona}</p>
            <p class="meta"><strong>Goal:</strong> {journey.goal}</p>
        </header>

        <div class="chart-container">
            <h2>Emotional Journey</h2>
            <canvas id="emotionChart" height="100"></canvas>
        </div>

        <div class="journey">
            {steps_html}
        </div>
    </div>

    <script>
        const ctx = document.getElementById('emotionChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {step_names},
                datasets: [{{
                    label: 'Emotion Level',
                    data: {emotion_data},
                    borderColor: '#333',
                    backgroundColor: 'rgba(51, 51, 51, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 8,
                    pointBackgroundColor: {emotion_data}.map(e =>
                        e >= 2 ? '#28a745' : e <= -2 ? '#dc3545' : '#6c757d'
                    ),
                }}]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{
                        min: -3,
                        max: 3,
                        ticks: {{
                            stepSize: 1,
                            callback: function(value) {{
                                const labels = {{
                                    3: '😄 Delighted',
                                    2: '🙂 Pleased',
                                    1: '😊 Content',
                                    0: '😐 Neutral',
                                    '-1': '😕 Uncertain',
                                    '-2': '😟 Frustrated',
                                    '-3': '😤 Angry'
                                }};
                                return labels[value] || value;
                            }}
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{ display: false }}
                }}
            }}
        }});
    </script>
</body>
</html>"""

    return html


def export_figma_json(journey: UserJourney) -> str:
    """Export journey as Figma-compatible JSON."""
    figma_data = {
        "name": journey.name,
        "type": "USER_JOURNEY_MAP",
        "metadata": {
            "persona": journey.persona,
            "goal": journey.goal,
            "created": datetime.now().isoformat(),
            "tool": "UX Journey Architect",
        },
        "steps": [],
    }

    for i, step in enumerate(journey.steps):
        figma_data["steps"].append({
            "id": f"step_{i+1}",
            "order": i + 1,
            "name": step.name,
            "action": step.action,
            "touchpoint": step.touchpoint,
            "emotion": {
                "score": step.emotion,
                "label": step.emotion_label,
                "color": (
                    "#28a745" if step.emotion >= 2
                    else "#dc3545" if step.emotion <= -2
                    else "#6c757d"
                ),
            },
            "pain_points": step.pain_points,
            "opportunities": step.opportunities,
            "notes": step.notes,
            "position": {
                "x": i * 300,
                "y": 0,
            },
        })

    return json.dumps(figma_data, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Export user journey to various formats"
    )
    parser.add_argument("input", help="Input JSON file")
    parser.add_argument(
        "--format", "-f",
        choices=["mermaid", "markdown", "html", "figma"],
        default="markdown",
        help="Output format"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)"
    )

    args = parser.parse_args()

    # Load input
    with open(args.input, "r") as f:
        data = json.load(f)

    journey = parse_journey(data)

    # Export
    exporters = {
        "mermaid": export_mermaid,
        "markdown": export_markdown,
        "html": export_html,
        "figma": export_figma_json,
    }

    output = exporters[args.format](journey)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Exported to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
