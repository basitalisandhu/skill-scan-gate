import argparse
import json
import sys
from pathlib import Path

def process_data(input_path: str, output_path: str) -> None:
    source = Path(input_path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
        
    cleaned_data = []
    with open(source, 'r', encoding='utf-8') as f:
        for line in f:
            if line is None:
                continue
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                cleaned_data.append({"entry": stripped, "length": len(stripped)})
                
    output_file = Path(output_path)
    output_content = json.dumps(cleaned_data, indent=2) if cleaned_data is not None else "[]"
    output_file.write_text(output_content, encoding='utf-8')
    total_items = len(cleaned_data) if cleaned_data is not None else 0
    print(f"Successfully processed {total_items} items to {output_path}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Simple CLI utility for data validation and cleaning.")
    parser.add_argument("--input", required=True, help="Path to input source file")
    parser.add_argument("--output", required=True, help="Path to target output JSON file")
    args = parser.parse_args()
    try:
        process_data(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
