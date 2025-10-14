import os

print("Hello, World")

def get_terminal_size():
    """Gets the current size of the terminal."""
    try:
        columns, rows = os.get_terminal_size()
        return columns, rows
    except OSError:
        # Return a default size if running in an environment without a TTY
        return 80, 24

def mandelbrot():
    """Generates and prints a Mandelbrot set scaled to the terminal size."""
    WIDTH, HEIGHT = get_terminal_size()
    # Adjust for character aspect ratio (characters are taller than they are wide)
    HEIGHT = int(HEIGHT * 0.5) - 1

    # Region of the complex plane to render
    X_MIN, X_MAX = -2.0, 1.0
    Y_MIN, Y_MAX = -1.0, 1.0
    MAX_ITER = 256

    # Characters used to draw the set, from densest to sparsest
    chars = '@%#*+=-:. '

    for y in range(HEIGHT):
        line = ""
        for x in range(WIDTH):
            # Convert pixel coordinate to a complex number
            c = complex(
                X_MIN + (x / WIDTH) * (X_MAX - X_MIN),
                Y_MIN + (y / HEIGHT) * (Y_MAX - Y_MIN)
            )
            z = 0
            i = 0
            while abs(z) < 2 and i < MAX_ITER:
                z = z*z + c
                i += 1

            if i == MAX_ITER:
                # Point is inside the set
                line += ' '
            else:
                # Point is outside the set; color depends on how quickly it escaped
                line += chars[i % len(chars)]
        print(line)

if __name__ == "__main__":
    mandelbrot()
