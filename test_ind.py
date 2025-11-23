import time
import sys

def w(s):
    sys.stdout.write(s)
    sys.stdout.flush()
    time.sleep(0.4)

# Setup: Clear and fill screen
w("\033[2J\033[H")
for i in range(1, 25):
    w(f"Line {i:02d}\n")
time.sleep(1)

# Set scroll region: lines 8-16
w("\033[8;16r")
w("\033[1;1H*** Scroll region: 8-16 ***")
time.sleep(1)

# Position at bottom of scroll region (line 16)
w("\033[16;1H")
w("\033[44m BOTTOM \033[0m")
time.sleep(1)

# IND 3 times - scrolls region UP (line 8 deleted each time)
w("\033[1;1H*** IND x3 (scroll up) ***")
for i in range(3):
    w("\033D")  # IND
    w(f"\033[44m NEW-{i+1} \033[0m")
    time.sleep(0.6)

time.sleep(1)

# Position at top of scroll region (line 8)
w("\033[8;1H")
w("\033[43m TOP \033[0m")
time.sleep(1)

# RI 3 times - scrolls region DOWN (line 16 deleted each time)
w("\033[1;1H*** RI x3 (scroll down) ***")
for i in range(3):
    w("\033M")  # RI
    w(f"\033[43m NEW-{i+1} \033[0m")
    time.sleep(0.6)

# Cleanup
time.sleep(1)
w("\033[r\033[24;1H\n")
