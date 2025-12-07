print('\x1b(0')    # Switch to DEC Special Graphics (line drawing characters)
print('lqqqk')     # Draws: ┌───┐ (box corners and lines)
print('\x1b(B')    # Switch back to ASCII
print('Hello')     # Normal text again
