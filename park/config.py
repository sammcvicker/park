"""
Configuration settings for Park.
Contains default values and constants used throughout the application.
"""

# Default display settings
DEFAULT_COL_WIDTH = 15  # Default column width for display
MIN_COLUMNS = 1  # Minimum number of columns to display
MAX_COLUMNS = 50  # Maximum number of columns to display
MAX_BUFFER_SIZE = 100  # Maximum buffer size in rows

# Pandas display options
PANDAS_MAX_COLWIDTH = 15  # Limit column content width
FLOAT_PRECISION = 4  # Decimal precision for float values

# Default values
DEFAULT_ROWS_PER_PAGE = 20  # Default number of rows to show per page
DEFAULT_BATCH_SIZE = 1000  # Default batch size for reading parquet files 

# Color pairs for curses
COLOR_PAIR_DEFAULT = 1  # Default colors
COLOR_PAIR_NULL = 2  # Color for null values (red text) 