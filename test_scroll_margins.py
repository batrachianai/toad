import time
import sys

def print_slow(s):
    sys.stdout.write(s)
    sys.stdout.flush()
    time.sleep(0.1)

# Clear screen and home cursor
print_slow("\033[2J\033[H")

# Fill screen with numbered lines
for i in range(1, 25):
    sys.stdout.write(f"Line {i-1:02d}\n")
    sys.stdout.flush()

# Set scroll region to lines 5-15
print_slow("\033[5;15r")

# Move cursor to line 15 (bottom of scroll region)
print_slow("\033[15;1H")
print_slow("\033[7m[At bottom of scroll region]\033[0m")
time.sleep(1)

# Use IND (ESC D) - should scroll region UP
for i in range(3):
    print_slow("\033D")  # IND - scrolls up when at bottom
    print_slow(f"\033[7mScroll up {i+1}\033[0m")
    time.sleep(0.2)

time.sleep(1)

# Move cursor to line 5 (top of scroll region)
print_slow("\033[5;1H")
print_slow("\033[7m[At top of scroll region]\033[0m")
time.sleep(1)

# Use RI (ESC M) - should scroll region DOWN
for i in range(3):
    print_slow("\033M")  # RI - scrolls down when at top
    print_slow(f"\033[7mScroll down {i+1}\033[0m")
    time.sleep(0.2)

# Reset scroll region and move to bottom
print_slow("\033[r\033[24;1H")
