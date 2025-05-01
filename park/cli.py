#!/usr/bin/env python
import click
import pandas as pd
import pyarrow.parquet as pq
import sys
import os
from typing import List
import curses
import psutil  # For memory usage tracking


@click.command()
@click.argument('file', type=click.Path(exists=True))
def main(file: str):
    """
    Park: A CLI for inspecting large parquet files in a memory efficient manner.
    
    Keyboard controls:
    - q: Quit
    - l: Next set of columns
    - h: Previous set of columns
    - j: Next set of rows
    - k: Previous set of rows
    - r: Refresh display (useful after terminal resize)
    """
    try:
        # Get file metadata without loading the entire file
        parquet_file = pq.ParquetFile(file)
        schema = parquet_file.schema
        num_rows = parquet_file.metadata.num_rows
        all_columns = [field.name for field in schema]
        
        # Launch interactive mode
        curses.wrapper(
            interactive_mode,
            parquet_file,
            num_rows,
            all_columns
        )
    
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


def format_dataframe(df):
    """Format a DataFrame for display."""
    # If DataFrame is empty, return empty string
    if df.empty:
        return ""
    
    # Set pandas display options
    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.max_colwidth', 15)   # Limit column content width
    
    # Convert float columns to truncated strings to avoid scientific notation
    # Use inplace operations where possible to reduce memory usage
    for col in df.columns:
        if df[col].dtype == 'float64':
            # Format floats without creating unnecessary temporary objects
            df[col] = df[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "", na_action='ignore')
    
    # Use pandas to_string with header=False to hide automatic headers
    return df.to_string(index=True, header=False)


def is_data_in_memory(row_start, row_end, cached_data):
    """Check if the requested data range is already in memory (using 1-indexed rows)."""
    if not cached_data:
        return False
    # All values here should already be 1-indexed
    return row_start >= cached_data['start'] and row_end <= cached_data['end']


def load_data_range(parquet_file, visible_columns, row_start, row_end, buffer_size):
    """Load a range of data with buffer for smooth scrolling."""
    # Limit buffer size to prevent excessive memory usage on large terminals
    buffer_size = min(buffer_size, 100)  # Cap buffer at 100 rows
    
    # Convert row indices to 0-indexed for internal processing (subtract 1)
    zero_based_start = max(0, row_start - 1)  # Ensure we don't go below 0
    zero_based_end = row_end - 1
    
    # Calculate batch size with buffer for scrolling
    batch_size = min(1000, buffer_size * 3)  # Limit batch size to avoid memory issues
    
    # Calculate batch start and end with buffering
    batch_start = max(0, zero_based_start - buffer_size)
    batch_end = min(parquet_file.metadata.num_rows, zero_based_end + buffer_size)
    
    # Read the data
    table = pd.DataFrame()
    current_row = 0
    
    for batch in parquet_file.iter_batches(batch_size=batch_size, columns=visible_columns):
        df_batch = batch.to_pandas()
        batch_size = len(df_batch)
        
        # Calculate row indices for this batch
        iter_batch_start = current_row
        iter_batch_end = iter_batch_start + batch_size
        current_row += batch_size
        
        # Check if this batch overlaps with our desired range
        if iter_batch_end > batch_start and iter_batch_start < batch_end:
            # Add row indices with 1-indexing (add 1 to each index)
            df_batch.index = range(iter_batch_start + 1, iter_batch_end + 1)
            
            # Append to result
            table = pd.concat([table, df_batch])
        
        # Early exit if we've read past our desired range
        if iter_batch_start >= batch_end:
            break
    
    # Return cache information - note that we store the 1-indexed values
    if not table.empty:
        return {
            'table': table,
            'start': table.index.min(),
            'end': table.index.max() + 1,
            'columns': visible_columns
        }
    else:
        # Create an empty DataFrame with the right columns
        empty_df = pd.DataFrame(columns=visible_columns)
        return {
            'table': empty_df,
            'start': row_start,
            'end': row_end,
            'columns': visible_columns
        }


def create_header_rows(arrow_schema, visible_columns, column_offset, all_columns, col_width):
    """Create header rows with column metadata."""
    # Create DataFrames for metadata rows
    col_indices = {col: i + column_offset for i, col in enumerate(visible_columns) if col in all_columns}
    
    # For columns that don't exist, use the index in the list
    for i, col in enumerate(visible_columns):
        if col not in all_columns:
            col_indices[col] = i + column_offset
    
    index_row = pd.Series({col: col_indices[col] for col in visible_columns}, name="index")
    
    # Get data types for each column
    type_dict = {}
    for col in visible_columns:
        if col in all_columns:
            # Truncate long type names
            type_str = str(arrow_schema.field(col).type)
            if len(type_str) > col_width - 2:  # Leave some margin
                type_str = type_str[:col_width-5] + "..."
            type_dict[col] = type_str
        else:
            type_dict[col] = "unknown"
            
    type_row = pd.Series(type_dict, name="type")
    name_row = pd.Series({col: col for col in visible_columns}, name="name")
    
    return pd.DataFrame([index_row, type_row, name_row])


def get_visible_columns(all_columns, column_offset, max_width, col_width, min_columns=1):
    """Dynamically determine how many columns will fit in the terminal width."""
    if not all_columns:
        return []
    
    # Hard limit on maximum columns to prevent excessive memory usage
    MAX_COLUMNS = 50
    
    # Start with just the index column width (typically around 5-8 chars)
    current_width = 8
    
    # Add columns until we exceed available width
    columns_to_show = []
    for i, col in enumerate(all_columns[column_offset:]):
        # Break if we hit the hard column limit
        if len(columns_to_show) >= MAX_COLUMNS:
            break
            
        # Estimate this column's width (column name or column width, whichever is larger)
        estimated_width = max(len(col), col_width)
        
        # Check if adding this column would exceed available width
        if current_width + estimated_width > max_width and len(columns_to_show) >= min_columns:
            break
        
        columns_to_show.append(col)
        current_width += estimated_width
    
    return columns_to_show


def get_memory_usage():
    """Get current memory usage in MB."""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return memory_info.rss / 1024 / 1024  # Convert to MB


def interactive_mode(stdscr, parquet_file, num_rows, all_columns):
    """Interactive mode using curses for better terminal handling."""
    # Configure curses
    curses.curs_set(0)  # Hide cursor
    stdscr.clear()
    stdscr.refresh()
    
    # Initialize colors
    if curses.has_colors():
        curses.use_default_colors()
        curses.init_pair(1, -1, -1)  # Default colors
    
    # Initialize state - use 1-indexed for row_offset
    column_offset = 0
    row_offset = 1  # Start at row 1 (not 0)
    rows_per_page = 20
    cached_data = None
    col_width = 15  # Default column width
    
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
                    import gc
                    gc.collect()  # Encourage garbage collection
                
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
            
            # Display the formatted data
            lines = formatted_output.split('\n')
            for i, line in enumerate(lines):
                if i < max_y - 2:  # Leave space for status bar
                    stdscr.addstr(i, 0, line[:max_x-1])
            
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
            stdscr.addstr(max_y-2, 0, status_line[:max_x-1])
            stdscr.addstr(max_y-1, 0, help_line[:max_x-1])
            
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
                    import gc
                    gc.collect()  # Encourage garbage collection
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
                    import gc
                    gc.collect()
                cached_data = None
                
            # Reset timeout
            stdscr.timeout(100)


if __name__ == "__main__":
    main()
