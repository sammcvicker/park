"""
Interactive viewer for displaying parquet data.
Uses curses for terminal-based user interface.
"""
import curses
import pandas as pd
from .formatter import format_dataframe, create_header_rows, NULL_MARKER
from .data_loader import get_visible_columns, is_data_in_memory, load_data_range
from .utils import get_memory_usage, force_garbage_collection
from .config import DEFAULT_COL_WIDTH, DEFAULT_ROWS_PER_PAGE, COLOR_PAIR_DEFAULT, COLOR_PAIR_NULL


def addstr_safe(stdscr, y, x, text, attr=0):
    """Safely add a string to the screen, avoiding boundary errors.
    
    Args:
        stdscr: The curses window
        y: The y position
        x: The x position
        text: The text to display
        attr: Text attributes (optional)
    """
    try:
        # Get window dimensions
        max_y, max_x = stdscr.getmaxyx()
        
        # Don't try to write if we're out of bounds
        if y >= max_y or x >= max_x:
            return
        
        # Truncate the text if it would go off screen
        if x + len(text) >= max_x:
            text = text[:max_x - x - 1]
        
        # Add the text
        if text:  # Only add if we have something to add
            stdscr.addstr(y, x, text, attr)
    except:
        # Fail silently - we're trying to prevent the error, not deal with it
        pass


def interactive_mode(stdscr, parquet_file, num_rows, all_columns):
    """Interactive mode using curses for better terminal handling."""
    # Configure curses
    curses.curs_set(0)  # Hide cursor
    stdscr.clear()
    stdscr.refresh()
    
    # Initialize colors
    if curses.has_colors():
        curses.use_default_colors()
        curses.init_pair(COLOR_PAIR_DEFAULT, -1, -1)  # Default colors
        curses.init_pair(COLOR_PAIR_NULL, curses.COLOR_RED, -1)  # Red text for null values
    
    # Initialize state - use 1-indexed for row_offset
    column_offset = 0
    row_offset = 1  # Start at row 1 (not 0)
    rows_per_page = DEFAULT_ROWS_PER_PAGE
    cached_data = None
    col_width = DEFAULT_COL_WIDTH
    
    # Main interaction loop
    running = True
    while running:
        try:
            # Get current terminal size
            max_y, max_x = stdscr.getmaxyx()
            
            # Adjust rows_per_page based on terminal height
            rows_per_page = max(5, max_y - 5)  # Allow space for header and footer
            
            # Dynamically determine visible columns based on terminal width
            visible_columns = get_visible_columns(
                all_columns, 
                column_offset, 
                max_width=max_x-1, 
                col_width=col_width, 
                min_columns=1
            )
            
            # Calculate row range to display (1-indexed)
            row_start = row_offset
            row_end = min(row_start + rows_per_page, num_rows + 1)  # +1 because 1-indexed
            
            # Check if we need to load data
            if (not cached_data or 
                set(cached_data['columns']) != set(visible_columns) or 
                not is_data_in_memory(row_start, row_end, cached_data)):
                
                # Clear previous cached data before loading new data to free memory
                if cached_data:
                    del cached_data
                    force_garbage_collection()
                
                # Load new data range
                cached_data = load_data_range(
                    parquet_file,
                    visible_columns,
                    row_start,
                    row_end,
                    rows_per_page  # Use rows_per_page as buffer size
                )
            
            # Extract the data for the current view
            view_data = pd.DataFrame(columns=visible_columns)
            if cached_data and not cached_data['table'].empty:
                # Get the overlap between cached data and desired view
                cache_start = max(row_start, cached_data['start'])
                cache_end = min(row_end, cached_data['end'])
                
                if cache_end > cache_start:
                    # Filter rows in the desired range - use .loc without copy() to reduce memory usage
                    view_data = cached_data['table'].loc[cache_start:cache_end-1]
            
            # Create header rows
            header_rows = create_header_rows(
                parquet_file.schema_arrow,
                visible_columns,
                column_offset,
                all_columns,
                col_width
            )
            view_data = pd.concat([header_rows, view_data])
            
            # Format the DataFrame for display
            formatted_output = format_dataframe(view_data)
            
            # Free memory by clearing view_data
            del view_data
            
            # Clear the screen
            stdscr.clear()
            
            # Display the formatted data with special handling for null values
            lines = formatted_output.split('\n')
            for i, line in enumerate(lines):
                if i < max_y - 2:  # Leave space for status bar
                    # Check if the line contains NULL markers
                    if NULL_MARKER in line:
                        # Find all NULL markers in the line
                        positions = []
                        start_idx = 0
                        while True:
                            idx = line.find(NULL_MARKER, start_idx)
                            if idx == -1:
                                break
                            positions.append(idx)
                            start_idx = idx + len(NULL_MARKER)
                        
                        # Process the line with NULL markers
                        last_pos = 0
                        for pos in positions:
                            # Display the text before the NULL marker
                            if pos > last_pos:
                                addstr_safe(stdscr, i, last_pos, line[last_pos:pos])
                            
                            # Display "NULL" in red bold
                            addstr_safe(stdscr, i, pos, "NULL", curses.color_pair(COLOR_PAIR_NULL) | curses.A_BOLD)
                            
                            # Calculate space needed for padding
                            padding_needed = len(NULL_MARKER) - 4  # "NULL" is 4 chars
                            if padding_needed > 0:
                                # Add padding spaces after "NULL" to maintain alignment
                                addstr_safe(stdscr, i, pos + 4, " " * padding_needed)
                            
                            # Update last position for next iteration
                            last_pos = pos + len(NULL_MARKER)
                        
                        # Display any remaining text after the last NULL
                        if last_pos < len(line):
                            addstr_safe(stdscr, i, last_pos, line[last_pos:])
                    else:
                        # No NULL markers, display the line normally
                        addstr_safe(stdscr, i, 0, line)
            
            # Free memory by clearing formatted_output and lines
            del formatted_output
            del lines
            
            # Get current memory usage
            memory_mb = get_memory_usage()
            
            # Display status bar - use 1-indexed row numbers
            status_line = f" Rows: {row_start}-{row_end-1} of {num_rows} | "
            status_line += f"Cols: {column_offset+1}-{column_offset+len(visible_columns)} of {len(all_columns)} | "
            status_line += f"Mem: {memory_mb:.1f} MB"
            help_line = " h/l: columns, j/k: rows, H/L: page columns, J/K: page rows, q: quit, r: refresh"
            
            # Add status text
            addstr_safe(stdscr, max_y-2, 0, status_line)
            addstr_safe(stdscr, max_y-1, 0, help_line)
            
            stdscr.refresh()
            
            # Get user input (with timeout to allow for resize events)
            stdscr.timeout(100)  # 100ms timeout
            key = stdscr.getch()
            
            # Process keypress
            if key == ord('q'):
                running = False
            elif key == ord('h'):
                # Previous columns
                column_offset = max(0, column_offset - 1)
            elif key == ord('l'):
                # Next columns - ensure we don't go past the end
                if column_offset + len(visible_columns) < len(all_columns):
                    column_offset += 1
            elif key == ord('j'):
                # Next rows (1-indexed)
                row_offset = min(num_rows, row_offset + 1)
            elif key == ord('k'):
                # Previous rows (1-indexed)
                row_offset = max(1, row_offset - 1)  # Don't go below row 1
            elif key == ord('J'):  # Capital J for page down
                # Next page of rows
                row_offset = min(num_rows - rows_per_page + 1, row_offset + rows_per_page)
            elif key == ord('K'):  # Capital K for page up
                # Previous page of rows
                row_offset = max(1, row_offset - rows_per_page)  # Don't go below row 1
            elif key == ord('L'):  # Capital L for page right
                # Next page of columns
                new_offset = column_offset + len(visible_columns)
                if new_offset < len(all_columns):
                    column_offset = new_offset
            elif key == ord('H'):  # Capital H for page left
                # Previous page of columns
                column_offset = max(0, column_offset - len(visible_columns))
            elif key == ord('r'):
                # Force refresh
                if cached_data:
                    del cached_data
                    force_garbage_collection()
                cached_data = None
            elif key == curses.KEY_RESIZE:
                # Terminal was resized
                stdscr.clear()
        
        except Exception as e:
            # Show error
            stdscr.clear()
            stdscr.addstr(0, 0, f"Error: {str(e)}")
            stdscr.addstr(1, 0, "Press 'q' to quit or 'r' to retry")
            stdscr.refresh()
            
            # Wait for input
            stdscr.timeout(-1)  # Wait indefinitely
            key = stdscr.getch()
            if key == ord('q'):
                running = False
            elif key == ord('r'):
                if cached_data:
                    del cached_data
                    force_garbage_collection()
                cached_data = None
                
            # Reset timeout
            stdscr.timeout(100) 