#!/usr/bin/env python3
"""Simple scroll test - compare with real terminal"""

import sys

ESC = '\x1b'
CSI = f'{ESC}['

def test_scroll_up():
    """Quick scroll up test"""
    # Clear and setup
    print(f'{CSI}2J{CSI}H', end='')  # Clear screen, home cursor
    
    # Draw initial content
    print("BEFORE SCROLL UP:")
    print("Line 1: AAAAA")
    print("Line 2: BBBBB")
    print("Line 3: CCCCC")
    print("Line 4: DDDDD")
    print("Line 5: EEEEE")
    print("\nPress Enter to scroll up 2 lines...")
    input()
    
    # Position to top and scroll
    print(f'{CSI}1;1H', end='')  # Move to row 1, col 1
    print(f'{CSI}2S', end='')     # Scroll up 2 lines
    sys.stdout.flush()
    
    # Show result
    print(f'{CSI}8;1H', end='')  # Move below the content
    print("\nAFTER SCROLL UP 2:")
    print("Line 1 should be: CCCCC")
    print("Line 2 should be: DDDDD")
    print("Line 3 should be: EEEEE")
    print("Line 4 should be: [blank]")
    print("Line 5 should be: [blank]")
    print("\n(Lines AAAAA and BBBBB scrolled off the top)")

def test_scroll_down():
    """Quick scroll down test"""
    input("\n\nPress Enter for scroll down test...")
    
    # Clear and setup
    print(f'{CSI}2J{CSI}H', end='')
    
    # Draw initial content
    print("BEFORE SCROLL DOWN:")
    print("Line 1: AAAAA")
    print("Line 2: BBBBB")
    print("Line 3: CCCCC")
    print("Line 4: DDDDD")
    print("Line 5: EEEEE")
    print("\nPress Enter to scroll down 2 lines...")
    input()
    
    # Position to top and scroll
    print(f'{CSI}1;1H', end='')  # Move to row 1, col 1
    print(f'{CSI}2T', end='')     # Scroll down 2 lines
    sys.stdout.flush()
    
    # Show result
    print(f'{CSI}8;1H', end='')
    print("\nAFTER SCROLL DOWN 2:")
    print("Line 1 should be: [blank]")
    print("Line 2 should be: [blank]")
    print("Line 3 should be: AAAAA")
    print("Line 4 should be: BBBBB")
    print("Line 5 should be: CCCCC")
    print("\n(Lines DDDDD and EEEEE scrolled off the bottom)")

if __name__ == '__main__':
    try:
        test_scroll_up()
        test_scroll_down()
        
        # Cleanup
        print(f'\n{CSI}2J{CSI}H', end='')
        print("Tests complete!")
        
    except KeyboardInterrupt:
        print(f'\n{CSI}2J{CSI}H')
        print("Interrupted")
