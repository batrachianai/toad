#!/usr/bin/env python3
"""
Terminal Scroll Test Script
Tests CSI S (Scroll Up) and CSI T (Scroll Down) commands
"""

import sys
import time

# Escape sequences
ESC = "\x1b"
CSI = f"{ESC}["


def clear_screen():
    """Clear entire screen and move cursor to home"""
    print(f"{CSI}2J", end="")  # Clear screen
    print(f"{CSI}H", end="")  # Move to home (1,1)
    sys.stdout.flush()


def move_cursor(row, col):
    """Move cursor to row, col (1-based)"""
    print(f"{CSI}{row};{col}H", end="")
    sys.stdout.flush()


def set_scroll_region(top, bottom):
    """Set scroll region from top to bottom row"""
    print(f"{CSI}{top};{bottom}r", end="")
    sys.stdout.flush()


def reset_scroll_region():
    """Reset scroll region to full screen"""
    print(f"{CSI}r", end="")
    sys.stdout.flush()


def scroll_up(n=1):
    """Scroll up n lines (CSI n S)"""
    print(f"{CSI}{n}S", end="")
    sys.stdout.flush()


def scroll_down(n=1):
    """Scroll down n lines (CSI n T)"""
    print(f"{CSI}{n}T", end="")
    sys.stdout.flush()


def pause(message="Press Enter to continue..."):
    """Pause and wait for user input"""
    print()
    # input()
    input(message)


def test_basic_scroll_up():
    """Test 1: Basic Scroll Up (Full Screen)"""
    print("=== Test 1: Scroll Up (Full Screen) ===")
    clear_screen()
    move_cursor(1, 1)

    print("Line 1 - Top")
    print("Line 2")
    print("Line 3")
    print("Line 4")
    print("Line 5 - Bottom")

    move_cursor(7, 1)
    print("Before scroll up. Lines 1-5 visible above.")
    pause()

    move_cursor(1, 1)
    scroll_up(2)  # Scroll up 2 lines

    move_cursor(7, 1)
    print("After scrolling up 2 lines:")
    print("  - Lines 1-2 should have scrolled off")
    print("  - Lines 3-5 moved up")
    print("  - 2 blank lines added at bottom")
    pause()


def test_basic_scroll_down():
    """Test 2: Basic Scroll Down (Full Screen)"""
    print("\n=== Test 2: Scroll Down (Full Screen) ===")
    clear_screen()
    move_cursor(1, 1)

    print("Line 1 - Top")
    print("Line 2")
    print("Line 3")
    print("Line 4")
    print("Line 5 - Bottom")

    move_cursor(7, 1)
    print("Before scroll down.")
    pause()

    move_cursor(1, 1)
    scroll_down(2)  # Scroll down 2 lines

    # move_cursor(7, 1)
    # print("After scrolling down 2 lines:")
    # print("  - 2 blank lines inserted at top")
    # print("  - Lines 1-3 moved down")
    # print("  - Lines 4-5 scrolled off bottom")
    # pause()
    input()


def test_scroll_region_up():
    """Test 3: Scroll Up with Scroll Region"""
    print("\n=== Test 3: Scroll Up (With Scroll Region) ===")
    clear_screen()
    move_cursor(1, 1)

    print("Header Line (outside region)")
    print("╔═══ Scroll Region Top ═══╗")
    print("│ Line 1 in region        │")
    print("│ Line 2 in region        │")
    print("│ Line 3 in region        │")
    print("│ Line 4 in region        │")
    print("╚═══ Scroll Region Bottom ═╝")
    print("Footer Line (outside region)")

    move_cursor(10, 1)
    print("Scroll region set to rows 3-7")
    pause()

    set_scroll_region(3, 7)  # Rows 3-7

    move_cursor(10, 1)
    scroll_up(2)

    print("After scroll up 2 in region:")
    print("  - Lines 1-2 scrolled off")
    print("  - Lines 3-4 moved up")
    print("  - Blank lines at bottom of region")
    print("  - Header/Footer unchanged!")

    reset_scroll_region()
    pause()


def test_scroll_region_down():
    """Test 4: Scroll Down with Scroll Region"""
    print("\n=== Test 4: Scroll Down (With Scroll Region) ===")
    clear_screen()
    move_cursor(1, 1)

    print("Header Line (outside region)")
    print("╔═══ Scroll Region Top ═══╗")
    print("│ Line A in region        │")
    print("│ Line B in region        │")
    print("│ Line C in region        │")
    print("│ Line D in region        │")
    print("╚═══ Scroll Region Bottom ═╝")
    print("Footer Line (outside region)")

    move_cursor(10, 1)
    print("Scroll region set to rows 3-7")
    pause()

    set_scroll_region(3, 7)
    move_cursor(10, 1)
    scroll_down(2)

    print("After scroll down 2 in region:")
    print("  - Blank lines at top of region")
    print("  - Lines A-B moved down")
    print("  - Lines C-D scrolled off")
    print("  - Header/Footer unchanged!")

    reset_scroll_region()
    pause()


def test_cursor_preservation():
    """Test 5: Cursor Position Preservation"""
    print("\n=== Test 5: Cursor Position Test ===")
    clear_screen()
    move_cursor(1, 1)

    print("Row 1")
    print("Row 2")
    print("Row 3 <-- Cursor here")
    print("Row 4")
    print("Row 5")

    move_cursor(3, 15)  # Position cursor at row 3, col 15
    print("X", end="")  # Mark cursor position

    move_cursor(7, 1)
    print("Cursor is at row 3, col 16 (after X)")
    pause("Press Enter to scroll up 2 lines...")

    scroll_up(2)

    # print("After scroll up:")
    # print("  - Content scrolled but cursor stayed at row 3, col 16")
    # print("  - (Cursor position doesn't move with scroll)")
    # pause()


def test_sequential_scrolls():
    """Test 6: Multiple Sequential Scrolls"""
    print("\n=== Test 6: Sequential Scrolls ===")
    clear_screen()
    move_cursor(1, 1)

    for i in range(1, 11):
        print(f"Line {i}")

    move_cursor(12, 1)
    print("10 lines displayed")
    pause()

    scroll_up(3)
    move_cursor(12, 1)
    print("Scrolled up 3 lines (lines 1-3 gone)")
    pause()

    scroll_up(3)
    move_cursor(12, 1)
    print("Scrolled up 3 more (lines 4-6 also gone)")
    pause()

    scroll_down(2)
    move_cursor(12, 1)
    print("Scrolled down 2 (blank lines at top)")
    pause()


def test_simple_visual():
    """Simple side-by-side visual test"""
    print("\n=== Simple Visual Test ===")
    clear_screen()

    print("Initial state:")
    print("1: AAAAA")
    print("2: BBBBB")
    print("3: CCCCC")
    print("4: DDDDD")
    print("5: EEEEE")
    print()
    pause("Press Enter, then I'll scroll up 2 lines...")

    # Redraw and scroll
    clear_screen()
    print("1: AAAAA")
    print("2: BBBBB")
    print("3: CCCCC")
    print("4: DDDDD")
    print("5: EEEEE")

    move_cursor(1, 1)
    scroll_up(2)  # Scroll up 2

    move_cursor(7, 1)
    print("After CSI 2 S (scroll up 2):")
    print("Expected result:")
    print("1: CCCCC  (was line 3)")
    print("2: DDDDD  (was line 4)")
    print("3: EEEEE  (was line 5)")
    print("4: [blank]")
    print("5: [blank]")
    pause()


def main():
    """Run all tests"""
    try:
        # Run all tests
        test_basic_scroll_up()
        test_basic_scroll_down()

        test_scroll_region_up()
        test_scroll_region_down()

        test_cursor_preservation()
        test_sequential_scrolls()
        test_simple_visual()

        # Cleanup
        # clear_screen()
        # reset_scroll_region()
        # move_cursor(1, 1)

        # print("Test complete!")
        # print()
        # print("Expected behaviors:")
        # print("  1. Scroll Up (S): Top lines disappear, bottom lines blank")
        # print("  2. Scroll Down (T): Top lines blank, bottom lines disappear")
        # print("  3. Only scroll region contents affected")
        # print("  4. Cursor position preserved")
        # print("  5. Lines outside scroll region unchanged")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        clear_screen()
        reset_scroll_region()
        move_cursor(1, 1)


if __name__ == "__main__":
    main()
