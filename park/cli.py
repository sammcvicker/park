#!/usr/bin/env python
"""
Park: A CLI for inspecting large parquet files in a memory efficient manner.
"""
import click
import pyarrow.parquet as pq
import sys
from .viewer import interactive_mode


@click.command()
@click.argument('file', type=click.Path(exists=True))
def main(file: str):
    """
    Park: A CLI for inspecting large parquet files in a memory efficient manner.
    
    Keyboard controls:
    - q: Quit
    - l/L: Scroll/page right
    - h/H: Scroll/page left
    - j/J: Scroll/page down
    - k/K: Scroll/page up
    - r: Refresh display (useful after terminal resize)
    """
    try:
        # Get file metadata without loading the entire file
        parquet_file = pq.ParquetFile(file)
        schema = parquet_file.schema
        num_rows = parquet_file.metadata.num_rows
        all_columns = [field.name for field in schema]
        
        # Launch interactive mode
        import curses
        curses.wrapper(
            interactive_mode,
            parquet_file,
            num_rows,
            all_columns
        )
    
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
