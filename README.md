# Park

Park is a Python CLI for inspecting large parquet files in a memory efficient manner.

## Features

It provides utilities like:
- `--rows (-r) <optional list of ints>`
  - without any list of ints, just shows the count of the rows in the file, otherwise only shows the provided rows
- `--columns (-c) <optional list of ints>`
  - without any list of ints, just shows the count of the columns in the file, otherwise only shows the provided columns
- `--sample (-s) <number of rows>`
  - Controls how many sample rows to display when showing columns (default: 5)
- `--max-columns (-m) <number of columns>`
  - Limits the number of columns displayed to avoid "line too long" errors (default: auto-calculated based on terminal width)
- `--width (-w) <width in characters>`
  - Forces a specific output width instead of auto-detection (default: auto-detected terminal width)

## Installation

```bash
pip install .
```

## Usage

```bash
# Show number of rows and columns
park your-file.parquet

# Show specific rows
park your-file.parquet -r 0 10 20

# Show specific columns
park your-file.parquet -c column_name1 column_name2

# Show 10 sample rows when displaying columns
park your-file.parquet -c column_name1 -s 10

# Limit display to 10 columns
park your-file.parquet -m 10

# Set display width to 100 characters
park your-file.parquet -w 100

# Combined options
park your-file.parquet -r 5 -c column_name -m 15
```

## Memory Efficiency

Park is designed to work with large parquet files by:
1. Reading metadata without loading the entire file
2. Processing data in batches
3. Only loading the specific rows and columns requested
4. Automatically limiting displayed columns to fit your terminal
5. Truncating large values and data types to improve display