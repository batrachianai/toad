TERMINAL_KEY_MAP = {
    # ============================================================================
    # FUNCTION KEYS (F1-F12)
    # ============================================================================
    # Unmodified function keys
    "f1": "\x1bOP",  # ESC O P (SS3 P)
    "f2": "\x1bOQ",  # ESC O Q (SS3 Q)
    "f3": "\x1bOR",  # ESC O R (SS3 R)
    "f4": "\x1bOS",  # ESC O S (SS3 S)
    "f5": "\x1b[15~",  # CSI 15 ~
    "f6": "\x1b[17~",  # CSI 17 ~
    "f7": "\x1b[18~",  # CSI 18 ~
    "f8": "\x1b[19~",  # CSI 19 ~
    "f9": "\x1b[20~",  # CSI 20 ~
    "f10": "\x1b[21~",  # CSI 21 ~
    "f11": "\x1b[23~",  # CSI 23 ~
    "f12": "\x1b[24~",  # CSI 24 ~
    # Shift+Function keys
    "shift+f1": "\x1b[1;2P",  # CSI 1 ; 2 P
    "shift+f2": "\x1b[1;2Q",  # CSI 1 ; 2 Q
    "shift+f3": "\x1b[1;2R",  # CSI 1 ; 2 R
    "shift+f4": "\x1b[1;2S",  # CSI 1 ; 2 S
    "shift+f5": "\x1b[15;2~",  # CSI 15 ; 2 ~
    "shift+f6": "\x1b[17;2~",  # CSI 17 ; 2 ~
    "shift+f7": "\x1b[18;2~",  # CSI 18 ; 2 ~
    "shift+f8": "\x1b[19;2~",  # CSI 19 ; 2 ~
    "shift+f9": "\x1b[20;2~",  # CSI 20 ; 2 ~
    "shift+f10": "\x1b[21;2~",  # CSI 21 ; 2 ~
    "shift+f11": "\x1b[23;2~",  # CSI 23 ; 2 ~
    "shift+f12": "\x1b[24;2~",  # CSI 24 ; 2 ~
    # Ctrl+Function keys
    "ctrl+f1": "\x1b[1;5P",  # CSI 1 ; 5 P
    "ctrl+f2": "\x1b[1;5Q",  # CSI 1 ; 5 Q
    "ctrl+f3": "\x1b[1;5R",  # CSI 1 ; 5 R
    "ctrl+f4": "\x1b[1;5S",  # CSI 1 ; 5 S
    "ctrl+f5": "\x1b[15;5~",  # CSI 15 ; 5 ~
    "ctrl+f6": "\x1b[17;5~",  # CSI 17 ; 5 ~
    "ctrl+f7": "\x1b[18;5~",  # CSI 18 ; 5 ~
    "ctrl+f8": "\x1b[19;5~",  # CSI 19 ; 5 ~
    "ctrl+f9": "\x1b[20;5~",  # CSI 20 ; 5 ~
    "ctrl+f10": "\x1b[21;5~",  # CSI 21 ; 5 ~
    "ctrl+f11": "\x1b[23;5~",  # CSI 23 ; 5 ~
    "ctrl+f12": "\x1b[24;5~",  # CSI 24 ; 5 ~
    # Ctrl+Shift+Function keys
    "ctrl+shift+f1": "\x1b[1;6P",  # CSI 1 ; 6 P
    "ctrl+shift+f2": "\x1b[1;6Q",  # CSI 1 ; 6 Q
    "ctrl+shift+f3": "\x1b[1;6R",  # CSI 1 ; 6 R
    "ctrl+shift+f4": "\x1b[1;6S",  # CSI 1 ; 6 S
    "ctrl+shift+f5": "\x1b[15;6~",  # CSI 15 ; 6 ~
    "ctrl+shift+f6": "\x1b[17;6~",  # CSI 17 ; 6 ~
    "ctrl+shift+f7": "\x1b[18;6~",  # CSI 18 ; 6 ~
    "ctrl+shift+f8": "\x1b[19;6~",  # CSI 19 ; 6 ~
    "ctrl+shift+f9": "\x1b[20;6~",  # CSI 20 ; 6 ~
    "ctrl+shift+f10": "\x1b[21;6~",  # CSI 21 ; 6 ~
    "ctrl+shift+f11": "\x1b[23;6~",  # CSI 23 ; 6 ~
    "ctrl+shift+f12": "\x1b[24;6~",  # CSI 24 ; 6 ~
    # ============================================================================
    # ARROW KEYS
    # ============================================================================
    # Unmodified arrow keys (Normal mode - CSI format)
    "up": "\x1b[A",  # CSI A
    "down": "\x1b[B",  # CSI B
    "right": "\x1b[C",  # CSI C
    "left": "\x1b[D",  # CSI D
    # Shift+Arrow keys
    "shift+up": "\x1b[1;2A",  # CSI 1 ; 2 A
    "shift+down": "\x1b[1;2B",  # CSI 1 ; 2 B
    "shift+right": "\x1b[1;2C",  # CSI 1 ; 2 C
    "shift+left": "\x1b[1;2D",  # CSI 1 ; 2 D
    # Ctrl+Arrow keys
    "ctrl+up": "\x1b[1;5A",  # CSI 1 ; 5 A
    "ctrl+down": "\x1b[1;5B",  # CSI 1 ; 5 B
    "ctrl+right": "\x1b[1;5C",  # CSI 1 ; 5 C
    "ctrl+left": "\x1b[1;5D",  # CSI 1 ; 5 D
    # Ctrl+Shift+Arrow keys
    "ctrl+shift+up": "\x1b[1;6A",  # CSI 1 ; 6 A
    "ctrl+shift+down": "\x1b[1;6B",  # CSI 1 ; 6 B
    "ctrl+shift+right": "\x1b[1;6C",  # CSI 1 ; 6 C
    "ctrl+shift+left": "\x1b[1;6D",  # CSI 1 ; 6 D
    # ============================================================================
    # NAVIGATION KEYS
    # ============================================================================
    # Home
    "home": "\x1b[H",  # CSI H (or \x1b[1~)
    "shift+home": "\x1b[1;2H",  # CSI 1 ; 2 H
    "ctrl+home": "\x1b[1;5H",  # CSI 1 ; 5 H
    "ctrl+shift+home": "\x1b[1;6H",  # CSI 1 ; 6 H
    # End
    "end": "\x1b[F",  # CSI F (or \x1b[4~)
    "shift+end": "\x1b[1;2F",  # CSI 1 ; 2 F
    "ctrl+end": "\x1b[1;5F",  # CSI 1 ; 5 F
    "ctrl+shift+end": "\x1b[1;6F",  # CSI 1 ; 6 F
    # Page Up
    "pageup": "\x1b[5~",  # CSI 5 ~
    "shift+pageup": "\x1b[5;2~",  # CSI 5 ; 2 ~
    "ctrl+pageup": "\x1b[5;5~",  # CSI 5 ; 5 ~
    "ctrl+shift+pageup": "\x1b[5;6~",  # CSI 5 ; 6 ~
    # Page Down
    "pagedown": "\x1b[6~",  # CSI 6 ~
    "shift+pagedown": "\x1b[6;2~",  # CSI 6 ; 2 ~
    "ctrl+pagedown": "\x1b[6;5~",  # CSI 6 ; 5 ~
    "ctrl+shift+pagedown": "\x1b[6;6~",  # CSI 6 ; 6 ~
    # Insert
    "insert": "\x1b[2~",  # CSI 2 ~
    "shift+insert": "\x1b[2;2~",  # CSI 2 ; 2 ~
    "ctrl+insert": "\x1b[2;5~",  # CSI 2 ; 5 ~
    "ctrl+shift+insert": "\x1b[2;6~",  # CSI 2 ; 6 ~
    # Delete
    "delete": "\x1b[3~",  # CSI 3 ~
    "shift+delete": "\x1b[3;2~",  # CSI 3 ; 2 ~
    "ctrl+delete": "\x1b[3;5~",  # CSI 3 ; 5 ~
    "ctrl+shift+delete": "\x1b[3;6~",  # CSI 3 ; 6 ~
    # ============================================================================
    # SPECIAL KEYS
    # ============================================================================
    # Tab
    "tab": "\t",  # Horizontal tab (0x09)
    "shift+tab": "\x1b[Z",  # CSI Z (Back tab)
    "ctrl+tab": "\x1b[27;5;9~",  # Modified tab (some terminals)
    "ctrl+shift+tab": "\x1b[27;6;9~",  # Modified back tab
    # Enter/Return
    "enter": "\r",  # Carriage return (0x0D)
    "ctrl+enter": "\x1b[27;5;13~",  # Modified enter (some terminals)
    "shift+enter": "\x1b[27;2;13~",  # Modified enter (some terminals)
    "ctrl+shift+enter": "\x1b[27;6;13~",
    # Backspace
    "backspace": "\x7f",  # Delete (0x7F) - most common
    "ctrl+backspace": "\x08",  # Ctrl+H (0x08)
    "shift+backspace": "\x7f",  # Usually same as backspace
    "ctrl+shift+backspace": "\x08",
    # Escape
    "escape": "\x1b",  # ESC (0x1B)
    # Space (for completeness with modifiers)
    "ctrl+space": "\x00",  # Ctrl+Space = NUL
    "shift+space": " ",  # Just space
    # ============================================================================
    # CTRL+LETTER COMBINATIONS (C0 controls)
    # ============================================================================
    # These are traditional C0 control characters
    "ctrl+a": "\x01",  # SOH
    "ctrl+b": "\x02",  # STX
    "ctrl+c": "\x03",  # ETX (interrupt)
    "ctrl+d": "\x04",  # EOT (EOF)
    "ctrl+e": "\x05",  # ENQ
    "ctrl+f": "\x06",  # ACK
    "ctrl+g": "\x07",  # BEL (bell)
    "ctrl+h": "\x08",  # BS (backspace)
    "ctrl+i": "\t",  # HT (tab) - same as tab
    "ctrl+j": "\n",  # LF (line feed)
    "ctrl+k": "\x0b",  # VT (vertical tab)
    "ctrl+l": "\x0c",  # FF (form feed)
    "ctrl+m": "\r",  # CR (carriage return) - same as enter
    "ctrl+n": "\x0e",  # SO
    "ctrl+o": "\x0f",  # SI
    "ctrl+p": "\x10",  # DLE
    "ctrl+q": "\x11",  # DC1 (XON)
    "ctrl+r": "\x12",  # DC2
    "ctrl+s": "\x13",  # DC3 (XOFF)
    "ctrl+t": "\x14",  # DC4
    "ctrl+u": "\x15",  # NAK
    "ctrl+v": "\x16",  # SYN
    "ctrl+w": "\x17",  # ETB
    "ctrl+x": "\x18",  # CAN
    "ctrl+y": "\x19",  # EM
    "ctrl+z": "\x1a",  # SUB
    "ctrl+[": "\x1b",  # ESC (escape) - alternative
    "ctrl+\\": "\x1c",  # FS
    "ctrl+]": "\x1d",  # GS
    "ctrl+^": "\x1e",  # RS (Ctrl+Shift+6)
    "ctrl+_": "\x1f",  # US (Ctrl+Shift+-)
    # ============================================================================
    # CTRL+SHIFT+LETTER COMBINATIONS (where distinct)
    # ============================================================================
    # Modern terminals often send different sequences for Ctrl+Shift+Letter
    # These use the CSI 27 ; modifier ; ascii format
    "ctrl+shift+a": "\x1b[27;6;65~",  # CSI 27 ; 6 ; 65 ~ (ASCII A=65)
    "ctrl+shift+b": "\x1b[27;6;66~",
    "ctrl+shift+c": "\x1b[27;6;67~",
    "ctrl+shift+d": "\x1b[27;6;68~",
    "ctrl+shift+e": "\x1b[27;6;69~",
    "ctrl+shift+f": "\x1b[27;6;70~",
    "ctrl+shift+g": "\x1b[27;6;71~",
    "ctrl+shift+h": "\x1b[27;6;72~",
    "ctrl+shift+i": "\x1b[27;6;73~",
    "ctrl+shift+j": "\x1b[27;6;74~",
    "ctrl+shift+k": "\x1b[27;6;75~",
    "ctrl+shift+l": "\x1b[27;6;76~",
    "ctrl+shift+m": "\x1b[27;6;77~",
    "ctrl+shift+n": "\x1b[27;6;78~",
    "ctrl+shift+o": "\x1b[27;6;79~",
    "ctrl+shift+p": "\x1b[27;6;80~",
    "ctrl+shift+q": "\x1b[27;6;81~",
    "ctrl+shift+r": "\x1b[27;6;82~",
    "ctrl+shift+s": "\x1b[27;6;83~",
    "ctrl+shift+t": "\x1b[27;6;84~",
    "ctrl+shift+u": "\x1b[27;6;85~",
    "ctrl+shift+v": "\x1b[27;6;86~",
    "ctrl+shift+w": "\x1b[27;6;87~",
    "ctrl+shift+x": "\x1b[27;6;88~",
    "ctrl+shift+y": "\x1b[27;6;89~",
    "ctrl+shift+z": "\x1b[27;6;90~",
    # ============================================================================
    # CTRL+DIGIT COMBINATIONS
    # ============================================================================
    "ctrl+0": "\x1b[27;5;48~",  # CSI 27 ; 5 ; 48 ~ (ASCII 0=48)
    "ctrl+1": "\x1b[27;5;49~",
    "ctrl+2": "\x00",  # Ctrl+2 = NUL (traditional)
    "ctrl+3": "\x1b",  # Ctrl+3 = ESC (traditional)
    "ctrl+4": "\x1c",  # Ctrl+4 = FS (traditional)
    "ctrl+5": "\x1d",  # Ctrl+5 = GS (traditional)
    "ctrl+6": "\x1e",  # Ctrl+6 = RS (traditional)
    "ctrl+7": "\x1f",  # Ctrl+7 = US (traditional)
    "ctrl+8": "\x7f",  # Ctrl+8 = DEL (traditional)
    "ctrl+9": "\x1b[27;5;57~",
    # ============================================================================
    # CTRL+SYMBOL COMBINATIONS
    # ============================================================================
    "ctrl+`": "\x00",  # Ctrl+` = NUL (same as Ctrl+Space)
    "ctrl+-": "\x1f",  # Ctrl+- = US
    "ctrl+=": "\x1b[27;5;61~",  # CSI 27 ; 5 ; 61 ~
    "ctrl+[": "\x1b",  # ESC (same as escape)
    "ctrl+]": "\x1d",  # GS
    "ctrl+\\": "\x1c",  # FS
    "ctrl+;": "\x1b[27;5;59~",
    "ctrl+'": "\x1b[27;5;39~",
    "ctrl+,": "\x1b[27;5;44~",
    "ctrl+.": "\x1b[27;5;46~",
    "ctrl+/": "\x1f",  # US (Ctrl+/ = Ctrl+_ on many terminals)
    # ============================================================================
    # SHIFT+FUNCTION KEYS (F13-F24 mappings)
    # ============================================================================
    # Some terminals map Shift+F1-F12 to F13-F24
    "f13": "\x1b[25~",  # Shift+F1 alternative
    "f14": "\x1b[26~",  # Shift+F2 alternative
    "f15": "\x1b[28~",  # Shift+F3 alternative
    "f16": "\x1b[29~",  # Shift+F4 alternative
    "f17": "\x1b[31~",  # Shift+F5 alternative
    "f18": "\x1b[32~",  # Shift+F6 alternative
    "f19": "\x1b[33~",  # Shift+F7 alternative
    "f20": "\x1b[34~",  # Shift+F8 alternative
}


CURSOR_KEYS_APPLICATION = {
    "up": "\x1bOA",
    "down": "\x1bOB",
    "right": "\x1bOC",
    "left": "\x1bOD",
    "home": "\x1bOH",
    "end": "\x1bOF",
}
