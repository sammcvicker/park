"""
Data loading functions for Park.
Handles efficient loading of parquet file data.
"""
import pandas as pd
import pyarrow.parquet as pq
from .config import DEFAULT_BATCH_SIZE, MAX_BUFFER_SIZE


def get_visible_columns(all_columns, column_offset, max_width, col_width, min_columns=1):
    """Dynamically determine how many columns will fit in the terminal width."""
    if not all_columns:
        return []
    
    # Hard limit on maximum columns to prevent excessive memory usage
    from .config import MAX_COLUMNS
    
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


def is_data_in_memory(row_start, row_end, cached_data):
    """Check if the requested data range is already in memory (using 1-indexed rows)."""
    if not cached_data:
        return False
    # All values here should already be 1-indexed
    return row_start >= cached_data['start'] and row_end <= cached_data['end']


def load_data_range(parquet_file, visible_columns, row_start, row_end, buffer_size):
    """Load a range of data with buffer for smooth scrolling."""
    # Limit buffer size to prevent excessive memory usage on large terminals
    buffer_size = min(buffer_size, MAX_BUFFER_SIZE)
    
    # Convert row indices to 0-indexed for internal processing (subtract 1)
    zero_based_start = max(0, row_start - 1)  # Ensure we don't go below 0
    zero_based_end = row_end - 1
    
    # Calculate batch size with buffer for scrolling
    batch_size = min(DEFAULT_BATCH_SIZE, buffer_size * 3)  # Limit batch size to avoid memory issues
    
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