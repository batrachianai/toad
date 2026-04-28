#!/usr/bin/env python3
"""
Package the Textual TUI Skill

Usage:
    python scripts/package.py [output_dir]

Creates textual-tui.skill in the specified directory (default: current directory)
"""

import sys
import subprocess
from pathlib import Path

def main():
    # Get repository root
    repo_root = Path(__file__).parent.parent
    skill_dir = repo_root / "skill"
    
    # Get output directory
    output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root
    output_dir = output_dir.resolve()
    
    # Check if skill directory exists
    if not skill_dir.exists():
        print(f"❌ Error: skill directory not found at {skill_dir}")
        sys.exit(1)
    
    # Check if package_skill.py exists (from skill-creator)
    # If not, provide fallback instructions
    package_script = Path("/mnt/skills/public/skill-creator/scripts/package_skill.py")
    
    if package_script.exists():
        print(f"📦 Packaging skill from {skill_dir}")
        print(f"📍 Output: {output_dir}")
        
        # Run the packaging script
        result = subprocess.run(
            [sys.executable, str(package_script), str(skill_dir), str(output_dir)],
            capture_output=True,
            text=True
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        if result.returncode == 0:
            skill_file = output_dir / "textual-tui.skill"
            print(f"\n✅ Success! Created {skill_file}")
            print(f"📊 Size: {skill_file.stat().st_size / 1024:.1f} KB")
        else:
            print("\n❌ Packaging failed")
            sys.exit(1)
    else:
        print("ℹ️  Package script not found. Manual packaging required:")
        print("\n1. Install skill-creator tools")
        print("2. Run: python /path/to/package_skill.py skill/ .")
        print("\nOr create a .skill file (zip archive) manually:")
        print(f"   cd {skill_dir.parent}")
        print(f"   zip -r textual-tui.skill skill/")

if __name__ == "__main__":
    main()
