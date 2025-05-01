"""
Formatter functions for data display in Park.
"""
import pandas as pd
from .config import PANDAS_MAX_COLWIDTH, FLOAT_PRECISION

# Special marker for null values - just a unique prefix that won't appear in normal data
NULL_MARKER = "<<NULL>>"  # A single marker that's easier to detect

def format_dataframe(df):
    """Format a DataFrame for display."""
    # If DataFrame is empty, return empty string
    if df.empty:
        return ""
    
    # Set pandas display options
    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.max_colwidth', PANDAS_MAX_COLWIDTH)
    
    # Make a copy of the dataframe to avoid modifying the original
    df = df.copy()
    
    # Replace None/NaN values with special null marker
    for col in df.columns:
        # Get the typical width of values in this column to ensure proper alignment
        # Default to the width of float formatted values (or standard string width)
        if df[col].dtype == 'float64':
            # For float columns, we'll keep the standard formatted width
            # e.g., "0.000000" is 10 characters including spaces
            width = FLOAT_PRECISION + 6  # Typically width of formatted float (decimal + leading digit + decimal point)
            # Format floats without creating unnecessary temporary objects
            df[col] = df[col].map(lambda x: f"{x:.{FLOAT_PRECISION}f}" if pd.notna(x) else NULL_MARKER, na_action='ignore')
        else:
            # For non-float columns, replace NaN/None values with special marker
            # Try to maintain the width of the column's typical values
            sample_values = df[col].dropna().astype(str)
            if not sample_values.empty:
                # Use the median length as a guideline (not mean, to avoid outliers)
                sample_lengths = sample_values.str.len()
                if len(sample_lengths) > 0:
                    width = max(4, min(20, int(sample_lengths.median())))  # 4 for "NULL", max 20 to avoid excessive padding
                else:
                    width = 10  # Default width
            else:
                width = 10  # Default width if no sample values
                
            df[col] = df[col].apply(lambda x: NULL_MARKER if pd.isna(x) else x)
    
    # Use pandas to_string with header=False to hide automatic headers
    return df.to_string(index=True, header=False)


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