#!/usr/bin/env python3
"""
Terminal Emulator Test Script
Tests various ANSI escape sequences for terminal emulator widgets
"""

import time
import sys


class TerminalTester:
    """Helper class for terminal escape sequences"""
    
    # Cursor movement
    CURSOR_UP = lambda n: f"\033[{n}A"
    CURSOR_DOWN = lambda n: f"\033[{n}B"
    CURSOR_FORWARD = lambda n: f"\033[{n}C"
    CURSOR_BACK = lambda n: f"\033[{n}D"
    CURSOR_POSITION = lambda row, col: f"\033[{row};{col}H"
    CURSOR_SAVE = "\033[s"
    CURSOR_RESTORE = "\033[u"
    CURSOR_HOME = "\033[H"
    
    # Screen operations
    CLEAR_SCREEN = "\033[2J"
    CLEAR_LINE = "\033[2K"
    CLEAR_TO_END = "\033[0J"
    CLEAR_TO_START = "\033[1J"
    
    # Alternate screen
    ALT_SCREEN_ON = "\033[?1049h"
    ALT_SCREEN_OFF = "\033[?1049l"
    
    # Text attributes
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    
    # Colors
    @staticmethod
    def fg_color(r, g, b):
        return f"\033[38;2;{r};{g};{b}m"
    
    @staticmethod
    def bg_color(r, g, b):
        return f"\033[48;2;{r};{g};{b}m"


def print_slow(text, delay=0.05):
    """Print text character by character with delay"""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)


def test_basic_cursor_movement():
    """Test basic cursor movement operations"""
    print("=== Testing Basic Cursor Movement ===\n")
    time.sleep(0.5)
    
    print("Moving cursor forward: ", end="")
    sys.stdout.write(TerminalTester.CURSOR_FORWARD(10))
    print("HERE")
    time.sleep(0.5)
    
    print("Moving cursor back: ")
    sys.stdout.write(TerminalTester.CURSOR_BACK(5))
    print("HERE")
    time.sleep(0.5)
    
    print("\nTesting cursor up/down:")
    print("Line 1")
    print("Line 2")
    print("Line 3")
    sys.stdout.write(TerminalTester.CURSOR_UP(2))
    sys.stdout.write(TerminalTester.CURSOR_FORWARD(7))
    print("<- Moved up 2 lines")
    time.sleep(1)


def test_cursor_positioning():
    """Test absolute cursor positioning"""
    print("\n=== Testing Cursor Positioning ===\n")
    time.sleep(0.5)
    
    # Draw a box using cursor positioning
    positions = [
        (5, 10, "+"), (5, 11, "-"), (5, 12, "-"), (5, 13, "-"), (5, 14, "+"),
        (6, 10, "|"), (6, 14, "|"),
        (7, 10, "|"), (7, 12, "X"), (7, 14, "|"),
        (8, 10, "|"), (8, 14, "|"),
        (9, 10, "+"), (9, 11, "-"), (9, 12, "-"), (9, 13, "-"), (9, 14, "+"),
    ]
    
    for row, col, char in positions:
        sys.stdout.write(TerminalTester.CURSOR_POSITION(row, col))
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.05)
    
    # Move cursor below the box
    sys.stdout.write(TerminalTester.CURSOR_POSITION(10, 1))
    print()
    time.sleep(1)


def test_save_restore_cursor():
    """Test save and restore cursor position"""
    print("\n=== Testing Save/Restore Cursor ===\n")
    time.sleep(0.5)
    
    print("Original position", end="")
    sys.stdout.write(TerminalTester.CURSOR_SAVE)
    print(" - cursor saved")
    
    print("Some other text...")
    print("More text on another line...")
    
    sys.stdout.write(TerminalTester.CURSOR_RESTORE)
    print(" <- Restored!")
    time.sleep(1)


def test_screen_clearing():
    """Test screen clearing operations"""
    print("\n=== Testing Screen Clearing ===\n")
    time.sleep(0.5)
    
    for i in range(10):
        print(f"Line {i+1}: " + "x" * 50)
    
    time.sleep(1)
    print("\nClearing screen in 2 seconds...")
    time.sleep(2)
    
    sys.stdout.write(TerminalTester.CLEAR_SCREEN)
    sys.stdout.write(TerminalTester.CURSOR_HOME)
    print("Screen cleared!")
    time.sleep(1)


def test_alternate_screen():
    """Test alternate screen buffer"""
    print("\n=== Testing Alternate Screen ===\n")
    time.sleep(0.5)
    
    print("This is the NORMAL screen buffer")
    print("You should see this text...")
    print("\nSwitching to alternate screen in 2 seconds...")
    time.sleep(2)
    
    # Switch to alternate screen
    sys.stdout.write(TerminalTester.ALT_SCREEN_ON)
    sys.stdout.write(TerminalTester.CLEAR_SCREEN)
    sys.stdout.write(TerminalTester.CURSOR_HOME)
    
    print("╔═══════════════════════════════════╗")
    print("║  ALTERNATE SCREEN BUFFER ACTIVE   ║")
    print("║                                   ║")
    print("║  This is a separate screen!       ║")
    print("║                                   ║")
    print("║  Drawing a simple animation...    ║")
    print("╚═══════════════════════════════════╝")
    
    # Simple animation in alternate screen
    for i in range(5):
        sys.stdout.write(TerminalTester.CURSOR_POSITION(10 + i, 5))
        print(f"{'→' * i}●{'←' * i}")
        sys.stdout.flush()
        time.sleep(0.3)
    
    sys.stdout.write(TerminalTester.CURSOR_POSITION(16, 1))
    print("\nReturning to normal screen in 2 seconds...")
    time.sleep(2)
    
    # Switch back to normal screen
    sys.stdout.write(TerminalTester.ALT_SCREEN_OFF)
    print("Back to normal screen! The previous text should still be here.")
    time.sleep(1)


def test_colors_and_attributes():
    """Test text colors and attributes"""
    print("\n=== Testing Colors and Attributes ===\n")
    time.sleep(0.5)
    
    print(f"{TerminalTester.BOLD}Bold text{TerminalTester.RESET}")
    print(f"{TerminalTester.UNDERLINE}Underlined text{TerminalTester.RESET}")
    print(f"{TerminalTester.REVERSE}Reversed text{TerminalTester.RESET}")
    
    print(f"\n{TerminalTester.fg_color(255, 0, 0)}Red text{TerminalTester.RESET}")
    print(f"{TerminalTester.fg_color(0, 255, 0)}Green text{TerminalTester.RESET}")
    print(f"{TerminalTester.fg_color(0, 0, 255)}Blue text{TerminalTester.RESET}")
    
    print(f"\n{TerminalTester.bg_color(255, 255, 0)}{TerminalTester.fg_color(0, 0, 0)}Black on Yellow{TerminalTester.RESET}")
    
    time.sleep(1)


def test_complex_animation():
    """Test a more complex animation using alternate screen"""
    print("\n=== Complex Animation Test ===\n")
    print("Starting animation in alternate screen in 2 seconds...")
    time.sleep(2)
    
    sys.stdout.write(TerminalTester.ALT_SCREEN_ON)
    sys.stdout.write(TerminalTester.CLEAR_SCREEN)
    
    # Draw border
    width, height = 60, 15
    for col in range(1, width + 1):
        sys.stdout.write(TerminalTester.CURSOR_POSITION(1, col))
        sys.stdout.write("═")
        sys.stdout.write(TerminalTester.CURSOR_POSITION(height, col))
        sys.stdout.write("═")
    
    for row in range(2, height):
        sys.stdout.write(TerminalTester.CURSOR_POSITION(row, 1))
        sys.stdout.write("║")
        sys.stdout.write(TerminalTester.CURSOR_POSITION(row, width))
        sys.stdout.write("║")
    
    sys.stdout.write(TerminalTester.CURSOR_POSITION(1, 1))
    sys.stdout.write("╔")
    sys.stdout.write(TerminalTester.CURSOR_POSITION(1, width))
    sys.stdout.write("╗")
    sys.stdout.write(TerminalTester.CURSOR_POSITION(height, 1))
    sys.stdout.write("╚")
    sys.stdout.write(TerminalTester.CURSOR_POSITION(height, width))
    sys.stdout.write("╝")
    
    # Animate a bouncing ball
    ball_x, ball_y = 30, 7
    dx, dy = 1, 1
    
    for _ in range(50):
        # Clear previous position
        sys.stdout.write(TerminalTester.CURSOR_POSITION(ball_y, ball_x))
        sys.stdout.write(" ")
        
        # Update position
        ball_x += dx
        ball_y += dy
        
        # Bounce off walls
        if ball_x <= 2 or ball_x >= width - 1:
            dx = -dx
        if ball_y <= 2 or ball_y >= height - 1:
            dy = -dy
        
        # Draw ball
        sys.stdout.write(TerminalTester.CURSOR_POSITION(ball_y, ball_x))
        sys.stdout.write(f"{TerminalTester.fg_color(255, 100, 100)}●{TerminalTester.RESET}")
        sys.stdout.flush()
        time.sleep(0.05)
    
    sys.stdout.write(TerminalTester.CURSOR_POSITION(height + 1, 1))
    print("\nAnimation complete! Returning to normal screen...")
    time.sleep(2)
    sys.stdout.write(TerminalTester.ALT_SCREEN_OFF)


def main():
    """Run all tests"""
    print("╔════════════════════════════════════════╗")
    print("║  Terminal Emulator Test Script        ║")
    print("║  Testing various ANSI escape sequences ║")
    print("╚════════════════════════════════════════╝\n")
    time.sleep(1)
    
    try:
        test_basic_cursor_movement()
        test_cursor_positioning()
        test_save_restore_cursor()
        test_colors_and_attributes()
        test_screen_clearing()
        test_alternate_screen()
        test_complex_animation()
        
        print("\n✓ All tests completed!")
        
    except KeyboardInterrupt:
        sys.stdout.write(TerminalTester.ALT_SCREEN_OFF)
        sys.stdout.write(TerminalTester.RESET)
        print("\n\nTests interrupted by user.")
    except Exception as e:
        sys.stdout.write(TerminalTester.ALT_SCREEN_OFF)
        sys.stdout.write(TerminalTester.RESET)
        print(f"\n\nError during tests: {e}")


if __name__ == "__main__":
    main()
