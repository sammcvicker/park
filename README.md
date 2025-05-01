# Park

Park is a lightweight, memory-efficient terminal-based viewer for inspecting large parquet files. It provides an interactive interface that lets you navigate through columns and rows without loading the entire file into memory.

## Features

- **Terminal-based UI**: Navigate through your data with intuitive keyboard controls
- **Memory Efficient**: Only loads the data you're viewing, with smart caching for smooth scrolling
- **Column Type Information**: Displays column data types from the parquet schema
- **Dynamic Resizing**: Automatically adapts to your terminal size
- **Resource Monitoring**: Shows current memory usage while browsing
- **Null Value Highlighting**: Visually distinguishes between string "None" and actual null values (displayed in bold red)

## Installation

```bash
# Install directly from the repository
pip install .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Usage

```bash
# Launch Park with a parquet file
park your_file.parquet
```

## Keyboard Controls

| Key  | Action |
| ---- | ------ |
| `h`  | Move one column left |
| `l`  | Move one column right |
| `j`  | Move one row down |
| `k`  | Move one row up |
| `H`  | Move one page of columns left |
| `L`  | Move one page of columns right |
| `J`  | Move one page of rows down |
| `K`  | Move one page of rows up |
| `r`  | Refresh display (clears cache) |
| `q`  | Quit |

## Memory Efficiency

Park is designed to work with extremely large parquet files by:

1. Reading metadata without loading the entire file
2. Loading only the visible portion of data
3. Implementing smart caching with buffer zones for smooth scrolling
4. Freeing memory proactively with garbage collection
5. Limiting the maximum number of columns loaded at once

## Dependencies

- `pyarrow`: For parquet file handling
- `pandas`: For data manipulation and display
- `click`: For command-line interface
- `psutil`: For memory usage monitoring
- `curses`: For terminal UI (built into Python standard library)

## Limitations

- Currently supports a single parquet file at a time
- Terminal width affects how many columns can be displayed
- Very wide columns may be truncated for display purposes