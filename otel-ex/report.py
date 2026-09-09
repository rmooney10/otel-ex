import json
import os
import pandas as pd
# Determine the base directory automatically
try:
    # Works when running as a standard Python script (.py)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Works in Jupyter / Interactive Notebook environments
    BASE_DIR = os.getcwd()





# Print current path to verify where Python is searching
print(f"Searching for files in: {BASE_DIR}")

file_names = [
    'calulator_server.txt',
    "single_tool_call1.txt",
    "single_tool_call2.txt",
    "single_tool_call3.txt",
    "multi_hop1.txt",
    "multi_hop2.txt",
    "multi_hop3.txt",
    "deliberate_error1.txt",
    "deliberate_error2.txt",
    "deliberate_error3.txt"
]

# Convert relative file names to full absolute paths
input_files = [os.path.join(BASE_DIR, fname) for fname in file_names]

def extract_spans_from_file(file_path: str) -> pd.DataFrame:
    """
    Read a single JSON trace file and extract all spans into a DataFrame.
    """
    span_records = []
    with open(file_path, "r") as f:
        json_data = json.load(f)
        for trace in json_data.get("data", []):
            for span in trace.get("spans", []):
                tags = {tag["key"]: tag["value"] for tag in span.get("tags", [])}
                # Appending inside the inner loop to collect every span
                span_records.append({
                    "operation": span.get("operationName"),
                    "duration_ms": span.get("duration", 0) / 1000.0,
                    "is_error": tags.get("error", False),
                    "error_msg": tags.get("otel.status_description", None),
                    "input_tokens": tags.get("llm.usage.input_tokens", None),
                    "output_tokens": tags.get("llm.usage.output_tokens", None),
                    "model": tags.get("llm.model", None)
                })

    return pd.DataFrame(span_records)


def generate_file_summary(in_file: str):
    """
    Process an input trace file and write its Span Summary and 
    LLM Token Usage tables to an output text file.
    """
    input_file = os.path.join(BASE_DIR, in_file)
    if not os.path.exists(input_file):
        print(f"Skipping {input_file}: File not found.")
        return

    df = extract_spans_from_file(input_file)
    
    # Define output file name (e.g., single_tool_call1.txt -> single_tool_call1_summary.txt)
    base_name, _ = os.path.splitext(input_file)
    print(f"Base name: {base_name}")
    output_file = f"{base_name}_summary.txt"
    print(f"Generating summary for {input_file} -> {output_file}")
    lines = [f"=== TRACE SUMMARY FOR {in_file}===\n"]

    # 1. Span Summary Table
    lines.append(f"=== SPAN SUMMARY === ")
    if not df.empty and "operation" in df.columns:
        span_summary = df[["operation", "duration_ms", "is_error"]]
        lines.append(span_summary.to_string(index=False))
    else:
        lines.append("No span data found.")

    # 2. LLM Token Usage Table
    lines.append("\n=== LLM USAGE ===")
    if not df.empty and "input_tokens" in df.columns:
        llm_df = df.dropna(subset=["input_tokens"])
        if not llm_df.empty:
            llm_summary = llm_df[["operation", "model", "input_tokens", "output_tokens"]]
            lines.append(llm_summary.to_string(index=False))
        else:
            lines.append("No LLM token usage found.")
    else:
        lines.append("No LLM token usage found.")

    # Write results to output file
    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    print(f"Generated summary: {output_file}")


# Run processing against each input file
for file in file_names:
    generate_file_summary(file)
    