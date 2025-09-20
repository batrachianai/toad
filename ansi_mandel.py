import os


def mandelbrot(c: complex, max_iter: int) -> int:
    """Determine the number of iterations for a point in the Mandelbrot set.

    Args:
        c (complex): The complex point to test.
        max_iter (int): The maximum number of iterations to test.

    Returns:
        int: Number of iterations before escape or max_iter.
    """
    z = 0 + 0j
    for n in range(max_iter):
        if abs(z) > 2:
            return n
        z = z * z + c
    return max_iter

def colorize(iter_count: int, max_iter: int) -> str:
    """Get an ANSI color code based on the iteration count.

    Args:
        iter_count (int): Number of iterations completed before escape.
        max_iter (int): Maximum number of iterations allowed.

    Returns:
        str: ANSI escape code for color.
    """
    if iter_count == max_iter:
        return "\033[48;5;0m"  # Black background for points in the set
    else:
        # Create a gradient from 17 to 231 (blue to red) for escaping points
        color_code = 17 + int((iter_count / max_iter) * 214)
        return f"\033[48;5;{color_code}m"

def draw_mandelbrot(width: int, height: int, max_iter: int) -> None:
    """Draw the Mandelbrot set in the terminal using ANSI colors.

    Args:
        width (int): Width of the output in terminal characters.
        height (int): Height of the output in terminal rows.
        max_iter (int): Maximum number of iterations for Mandelbrot calculation.
    """
    for y in range(height):
        for x in range(width):
            # Map the (x, y) pixel to a point in the complex plane
            real = (x / width) * 3.5 - 2.5
            imag = (y / height) * 2.0 - 1.0
            c = complex(real, imag)

            # Calculate the number of iterations
            iter_count = mandelbrot(c, max_iter)

            # Get the color for this point and print a space (box)
            color = colorize(iter_count, max_iter)
            print(f"{color}  ", end="")

        # Reset color and move to the next line
        print("\033[0m")

# Configuration for drawing
width = 80    # Number of characters wide
height = 40   # Number of character rows
max_iter = 100  # Maximum iterations for Mandelbrot calculation

# Draw the Mandelbrot set
draw_mandelbrot(width, height, max_iter)
