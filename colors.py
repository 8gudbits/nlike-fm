import curses

def init_colors():
    curses.init_pair(1, curses.COLOR_GREEN, -1)   # Header/info text color
    curses.init_pair(2, curses.COLOR_BLUE, -1)    # Directory names color
    curses.init_pair(3, curses.COLOR_WHITE, -1)   # File names color
    curses.init_pair(4, curses.COLOR_YELLOW, -1)  # Empty directory message color
    curses.init_pair(5, curses.COLOR_RED, -1)     # Error messages color
