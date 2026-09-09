import json
import os
import pandas as pd

file_names = [
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

# Determine the base directory automatically
try:
    # Works when running as a standard Python script (.py)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Works in Jupyter / Interactive Notebook environments
    BASE_DIR = os.getcwd()


input_files = [os.path.join(BASE_DIR, fname) for fname in file_names]


def extract_spans_from_file(file_path: str) -> pd.DataFrame:
    span_records = []
    with open(file_path, "r") as f:
        json_data = json.load(f)
        for trace in json_data.get("data", []):
            for span in trace.get("spans", []):
                tags = {tag["key"]: tag["value"] for tag in span.get("tags", [])}
                span_records.append({
                    "operation": span.get("operationName"),
                    "duration_ms": span.get("duration", 0) / 1000.0,
                    "is_error": tags.get("error", False),
                    "error_msg": tags.get("otel.status_description", ""),
                    "input_tokens": tags.get("llm.usage.input_tokens", None),
                    "output_tokens": tags.get("llm.usage.output_tokens", None),
                    "model": tags.get("llm.model", None)
                })

    return pd.DataFrame(span_records)


def generate_html_summary(file_path: str):
    if not os.path.exists(file_path):
        return

    df = extract_spans_from_file(file_path)
    base_name, _ = os.path.splitext(file_path)
    output_file = f"{base_name}_summary.html"

    # Add backticks or HTML tags for code spans
    df["operation"] = df["operation"].apply(lambda x: f"<code>{x}</code>")
    df["duration_ms"] = df["duration_ms"].apply(lambda x: f"{x:,.2f}")

    span_table_html = df[["operation", "duration_ms", "is_error", "error_msg"]].to_html(
        index=False, escape=False, classes="styled-table"
    )

    # Embedded CSS to mirror dark terminal UI
    html_content = f"""
    <html>
    <head>
    <style>
        body {{ background-color: #121212; color: #e0e0e0; font-family: system-ui, sans-serif; padding: 20px; }}
        code {{ background-color: #2a2a2a; color: #a9b7c6; padding: 3px 8px; border-radius: 6px; font-family: monospace; }}
        .styled-table {{ border-collapse: collapse; margin: 25px 0; width: 100%; background-color: #1e1e1e; border-radius: 8px; overflow: hidden; }}
        .styled-table th, .styled-table td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #2d2d2d; }}
        .styled-table th {{ background-color: #252526; color: #ffffff; font-weight: 600; }}
    </style>
    </head>
    <body>
        <h2>--- SPAN SUMMARY TABLE ---</h2>
        {span_table_html}
    </body>
    </html>
    """

    with open(output_file, "w") as f:
        f.write(html_content)

def generate_markdown_summary(file_path: str):
    if not os.path.exists(file_path):
        print(f"Skipping {file_path}: File not found.")
        return

    df = extract_spans_from_file(file_path)
    
    # Save output as a Markdown file (.md)
    base_name, _ = os.path.splitext(file_path)
    output_file = f"{base_name}_summary.md"
    
    lines = [f"### Trace Summary: `{os.path.basename(file_path)}`\n"]

    if not df.empty:
        # 1. Format data for display (add code backticks and formatted numbers)
        display_df = df.copy()
        
        # Add backticks around operations to render them as inline code tags
        display_df["operation"] = display_df["operation"].apply(lambda x: f"`{x}`" if x else "")
        display_df["duration_ms"] = display_df["duration_ms"].apply(lambda x: f"{x:,.2f}")

        # 2. Span Summary Table
        lines.append("#### --- SPAN SUMMARY TABLE --- \n")
        span_cols = ["operation", "duration_ms", "is_error", "error_msg"]
        span_table = display_df[span_cols].rename(columns={
            "operation": "Operation Name",
            "duration_ms": "Duration (ms)",
            "is_error": "Error Status",
            "error_msg": "Details / Error Message"
        })
        
        # Convert to rendered Markdown table
        lines.append(span_table.to_markdown(index=False, missingval=""))
        lines.append("\n")

        # 3. LLM Token Usage Table
        lines.append("#### --- LLM TOKEN USAGE --- \n")
        llm_df = display_df.dropna(subset=["input_tokens"]).copy()
        if not llm_df.empty:
            llm_cols = ["operation", "model", "input_tokens", "output_tokens"]
            llm_table = llm_df[llm_cols].rename(columns={
                "operation": "Operation",
                "model": "Model",
                "input_tokens": "Input Tokens",
                "output_tokens": "Output Tokens"
            })
            lines.append(llm_table.to_markdown(index=False, missingval=""))
        else:
            lines.append("*No LLM token usage recorded.*")
    else:
        lines.append("No span data found.")

    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    print(f"Generated Markdown summary: {output_file}")


for full_path in input_files:
    generate_markdown_summary(full_path)
    generate_html_summary(full_path)