import sys
import tty
import termios

def get_cursor_position():
    # Save terminal settings
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    
    try:
        # Set terminal to raw mode
        tty.setraw(fd)
        
        # Send cursor position request
        sys.stdout.write("\x1B[6n")
        sys.stdout.flush()
        
        # Read response
        response = ""
        while True:
            char = sys.stdin.read(1)
            response += char
            if char == 'R':
                break
        
        # Parse response: ESC[row;colR
        import re
        match = re.search(r'\[(\d+);(\d+)R', response)
        if match:
            row = int(match.group(1))
            col = int(match.group(2))
            return (row, col)
    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


print("\nHello World")
print(get_cursor_position())
