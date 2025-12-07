import sys
ESC = '\x1b'
CSI = f'{ESC}['

print("Hello")
top =5
bottom = 10
print(f'{CSI}{top};{bottom}r', end='')
print("World")
sys.stdout.flush()
