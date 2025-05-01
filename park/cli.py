#!/usr/bin/env python
import click
import pandas as pd
import pyarrow.parquet as pq
import sys
import subprocess
import tempfile
import os
import shutil
from typing import List, Optional


@click.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('--rows', '-r', type=int, multiple=True, help='Show specific rows. If none provided, shows row count.')
@click.option('--columns', '-c', type=str, multiple=True, help='Show specific columns. If none provided, shows column count.')
@click.option('--hide-headers', '-h', is_flag=True, help='Hide column headers in output.')
@click.option('--sample', '-s', type=int, default=5, help='Number of sample rows to display when showing columns.')
@click.option('--max-columns', '-m', type=int, default=0, help='Maximum number of columns to display. Default (0) auto-detects based on terminal width.')
@click.option('--width', '-w', type=int, default=0, help='Force specific output width. Default (0) auto-detects terminal width.')
@click.option('--col-width', '-cw', type=int, default=15, help='Average width per column in characters. Default: 15')
def main(file: str, rows: List[int], columns: List[str], hide_headers: bool, sample: int, 
         max_columns: int, width: int, col_width: int):
    """
    Park: A CLI for inspecting large parquet files in a memory efficient manner.
    """
    try:
        # Get file metadata without loading the entire file
        parquet_file = pq.ParquetFile(file)
        schema = parquet_file.schema
        num_rows = parquet_file.metadata.num_rows
        all_columns = [field.name for field in schema]
        
        # Handle rows option - just show count if no specific rows requested
        if not rows:
            click.echo(f"Number of rows: {num_rows}")
        
        # Handle columns option - just show count if no specific columns requested
        if not columns:
            click.echo(f"Number of columns: {len(all_columns)}")
        
        # Determine columns to read
        columns_to_read = list(columns) if columns else all_columns
        
        # Determine terminal width if not specified
        if width <= 0:
            # Get terminal size
            terminal_size = shutil.get_terminal_size((80, 20))
            terminal_width = terminal_size.columns
        else:
            terminal_width = width
        
        # If max_columns is not set, calculate a reasonable number based on terminal width
        # and the average column width
        if max_columns <= 0:
            # Allow space for the index column and some margin
            # Use the col_width parameter to determine how much space per column
            max_columns = max(1, (terminal_width - 10) // col_width)
        
        # Limit columns_to_read to max_columns if needed
        if len(columns_to_read) > max_columns:
            click.echo(f"Limiting display to {max_columns} out of {len(columns_to_read)} columns")
            # If columns were explicitly specified, respect that selection up to max_columns
            if columns:
                columns_to_read = list(columns)[:max_columns]
            else:
                columns_to_read = all_columns[:max_columns]
        
        # If specific rows were requested or we're showing a sample
        if rows or not hide_headers or columns:
            # Get PyArrow schema to access data types
            arrow_schema = parquet_file.schema_arrow
            
            # Create header rows with column metadata
            if not hide_headers:
                # Create DataFrames for metadata rows
                col_indices = {col: i for i, col in enumerate(columns_to_read) if col in all_columns}
                
                # For columns specified that don't exist, use the index in the list
                for i, col in enumerate(columns_to_read):
                    if col not in all_columns:
                        col_indices[col] = i
                
                index_row = pd.Series({col: col_indices[col] for col in columns_to_read}, name="index")
                
                # Get data types for each column
                type_dict = {}
                for col in columns_to_read:
                    if col in all_columns:
                        # Truncate long type names
                        type_str = str(arrow_schema.field(col).type)
                        if len(type_str) > col_width - 2:  # Leave some margin
                            type_str = type_str[:col_width-5] + "..."
                        type_dict[col] = type_str
                    else:
                        type_dict[col] = "unknown"
                        
                type_row = pd.Series(type_dict, name="type")
                name_row = pd.Series({col: col for col in columns_to_read}, name="name")
            
            # If specific rows were requested
            if rows:
                # Find the max row to read to avoid loading too much data
                max_row = max(rows)
                if max_row >= num_rows:
                    click.echo(f"Warning: Requested row {max_row} exceeds file size ({num_rows} rows)")
                    max_row = min(max_row, num_rows - 1)
                
                # Read data in chunks to avoid memory issues
                table = pd.DataFrame()
                chunk_size = 1000  # Adjust based on your memory constraints
                current_row = 0
                
                for batch in parquet_file.iter_batches(batch_size=chunk_size, columns=columns_to_read):
                    df_batch = batch.to_pandas()
                    batch_size = len(df_batch)
                    
                    # Calculate row indices for this batch
                    batch_start = current_row
                    batch_end = batch_start + batch_size
                    current_row += batch_size
                    
                    # Check if any requested rows are in this batch
                    batch_rows = [r for r in rows if batch_start <= r < batch_end]
                    if batch_rows:
                        # Extract only the requested rows from this batch
                        rows_to_extract = [r - batch_start for r in batch_rows]
                        df_selected = df_batch.iloc[rows_to_extract]
                        
                        # Add row indices for clarity
                        df_selected.index = batch_rows
                        
                        # Append to result
                        table = pd.concat([table, df_selected])
                    
                    # Early exit if we've read past our max needed row
                    if batch_end > max_row:
                        break
                
                # Add header rows if requested
                if not hide_headers and not table.empty:
                    # Prepend the metadata rows in the desired order: index, type, name
                    header_rows = pd.DataFrame([index_row, type_row, name_row])
                    table = pd.concat([header_rows, table])
                
                # Process the data with pandas first
                formatted_output = format_dataframe(table, terminal_width)
                click.echo(formatted_output)
            else:
                # Just read a sample to show column structure
                sample_size = min(sample, num_rows)  # Ensure we don't try to read more rows than exist
                df_sample = next(parquet_file.iter_batches(batch_size=sample_size, columns=columns_to_read)).to_pandas()
                
                # Add header rows if requested
                if not hide_headers:
                    # Prepend the metadata rows in the desired order: index, type, name
                    header_rows = pd.DataFrame([index_row, type_row, name_row])
                    df_sample = pd.concat([header_rows, df_sample])
                
                # Process the data with pandas first
                formatted_output = format_dataframe(df_sample, terminal_width)
                click.echo(formatted_output)
    
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


def format_dataframe(df, width=0):
    """Format a DataFrame for display, ensuring it fits within the terminal width."""
    # If width not specified or too small, use reasonable default
    if width <= 20:
        width = 80
    
    # Set pandas display options
    pd.set_option('display.max_columns', None)  # Show all columns
    pd.set_option('display.width', width)       # Set width
    pd.set_option('display.max_colwidth', 15)   # Limit column content width
    
    # Convert string representation of float columns to truncated strings 
    # to avoid scientific notation and long decimals
    for col in df.columns:
        if df[col].dtype == 'float64':
            df[col] = df[col].apply(lambda x: f"{x:.4f}" if not pd.isna(x) else "")
    
    # Use pandas to_string for formatting
    return df.to_string(index=True)


if __name__ == "__main__":
    main()
