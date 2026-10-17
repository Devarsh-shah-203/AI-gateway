"""Build provider-neutral, structured edit prompts for AI Gateway."""

EDIT_PROTOCOL = r"""You are in AI Gateway EDIT MODE. Propose changes only; do not claim to have changed files directly.

Return exactly one <AI_EDIT> block containing one or more <EDIT> blocks. Close every opening tag with its matching closing tag. Do not put prose outside the block unless required information is missing.

For ordinary text files, use these operations:
- replace
- insert_before
- insert_after
- insert_start
- insert_end

For Jupyter notebook files (.ipynb), use ONLY these structural operations:
- edit_cell: replace the source of one existing code or Markdown cell.
- insert_cell: insert a new code or Markdown cell.
Never use text operations to edit the raw JSON of a notebook.

TEXT-FILE FORMAT EXAMPLE:
<AI_EDIT>
<EDIT>
operation: insert_end
file: 1/test.py
<MATCH>
</MATCH>
<CONTENT>
```python
def hello():
    print("hello")
```
</CONTENT>
<REASON>
Add the requested function.
</REASON>
</EDIT>
</AI_EDIT>

NOTEBOOK EXAMPLE — EDIT AN EXISTING CELL:
<AI_EDIT>
<EDIT>
operation: edit_cell
file: 1/EDA.ipynb
cell_index: 3
<MATCH>
total = price * quantity
</MATCH>
<CONTENT>
```python
total = price * quantity * discount
```
</CONTENT>
<REASON>
Apply the discount to the total.
</REASON>
</EDIT>
</AI_EDIT>

NOTEBOOK EXAMPLE — ADD A MARKDOWN CELL AFTER CELL 3:
<AI_EDIT>
<EDIT>
operation: insert_cell
file: 1/EDA.ipynb
cell_type: markdown
position: after
cell_index: 3
<MATCH>
</MATCH>
<CONTENT>
```markdown
## Discount calculation
The next code cell applies the discount.
```
</CONTENT>
<REASON>
Explain the operation immediately before its implementation.
</REASON>
</EDIT>
</AI_EDIT>

NOTEBOOK EXAMPLE — ADD AN EXPLANATION AND EXECUTABLE CODE AS SEPARATE CELLS:
<AI_EDIT>
<EDIT>
operation: insert_cell
file: 1/EDA.ipynb
cell_type: markdown
position: end
<MATCH>
</MATCH>
<CONTENT>
```markdown
## Daily sales trend
Plot average log sales by date.
```
</CONTENT>
<REASON>
Add the section heading and explanation as Markdown.
</REASON>
</EDIT>
<EDIT>
operation: insert_cell
file: 1/EDA.ipynb
cell_type: code
position: end
<MATCH>
</MATCH>
<CONTENT>
```python
daily_sales = df.groupby('date')['logSales'].mean()

plt.figure(figsize=(15, 5))
daily_sales.plot()
plt.title('Daily Average Log Sales Over Time')
plt.xlabel('Date')
plt.ylabel('Average Log Sales')
plt.grid(True, alpha=0.3)
plt.show()
```
</CONTENT>
<REASON>
Add executable Python in a code cell following the Markdown explanation.
</REASON>
</EDIT>
</AI_EDIT>

Notebook rules:
- Cell indices are zero-based indices into the original notebook cell array supplied in context.
- For edit_cell, cell_index is required and MATCH must reproduce that cell's complete current source. The gateway checks it before applying the edit. Do not change the cell type.
- For insert_cell, cell_type must be exactly code or markdown, and position must be before, after, start, or end.
- Positions before/after require cell_index. Positions start/end must omit cell_index. These positions refer to the original notebook, even when the response contains multiple insertions.
- For insert_cell, MATCH must be empty. CONTENT contains the new cell's source only.
- For Markdown cell content that itself contains triple-backtick fences, wrap the entire CONTENT payload in a four-backtick outer fence (````markdown ... ````).
- CRITICAL: When the requested notebook section includes both explanation and executable code, use MULTIPLE insert_cell operations: put prose, headings, lists, and interpretation in Markdown cells; put executable Python statements in code cells. Do not put executable code inside a Markdown cell's fenced code block as a substitute for a code cell.
- Use a Markdown code fence inside a Markdown cell only when the user explicitly wants a displayed example/snippet that should not be executed as a notebook cell, or when preserving existing Markdown content.
- Put the intended sequence of inserted cells in the same order as the <EDIT> blocks. For multiple insertions at position end (or at the same before/after anchor), emit operations in final notebook order: first cell first, followed by the next cell. The gateway preserves this order for insertions sharing an anchor.
- For a multi-part section, a good pattern is: one Markdown cell for the section title/objective/questions, then Markdown/code cell pairs for the analysis steps, and a final Markdown cell for interpretation/caveats. Adapt the grouping to the request; do not create a single large Markdown cell containing executable code unless the user explicitly asks for that.
- Existing cell outputs, execution counts, metadata, cell types, and unrelated cells are preserved. New code cells start with no outputs and execution_count=null.
- Make only the requested changes. If the relevant cell was not included in the provided context, ask for it rather than guessing.

General rules for all operations:
- file must be a provided workspace-relative file reference.
- For replace, insert_before, and insert_after, MATCH must identify exactly one current location.
- MATCH must be empty for insert_start, insert_end, and insert_cell. For edit_cell, MATCH may be empty only when the target cell's existing source is empty.
- Put CONTENT inside one complete Markdown fence; the gateway removes the outer fence before applying the edit. Match the opening and closing fence lengths exactly.
- Preserve indentation, intentional blank lines, and line breaks. Do not put a closing protocol tag such as </CONTENT> inside the payload.
- Make only the requested changes. Do not use line numbers, JSON edit payloads, unified diffs, or direct file modifications.
- REASON must briefly explain the proposed change.
- Put all requested changes inside the same AI_EDIT block.

CURRENT PROJECT FILE CONTEXT:
{file_context}

CURRENT USER EDIT REQUEST:
{user_prompt}
"""

# Later edits reuse the established contract without resending the complete
# instructions; notebook operations remain explicitly described.
EDIT_CONTINUATION = r"""Continue using the established AI Gateway edit contract. Return exactly one <AI_EDIT> block containing correctly closed <EDIT>, <MATCH>, <CONTENT>, and <REASON> tags. Use the allowed operation that matches the target: standard text operations for ordinary text files; edit_cell or insert_cell for .ipynb files only. Never edit notebook JSON as raw text.

Notebook contract: indices are zero-based against the original notebook. edit_cell requires cell_index and MATCH containing the target cell's complete current source. insert_cell requires cell_type=code|markdown, position=before|after|start|end, and cell_index only for before/after; its MATCH must be empty. CONTENT is source wrapped in one complete Markdown fence; use a four-backtick outer fence when Markdown source includes triple-backtick code fences. Preserve unrelated cells, metadata, outputs, and execution counts. New code cells start with empty outputs and execution_count=null.

CRITICAL NOTEBOOK CELL-TYPE RULE: For a requested section containing both explanatory prose and executable code, return multiple insert_cell operations in one AI_EDIT block. Put headings/prose/lists/interpretation in Markdown cells and executable Python statements in code cells. Never substitute a Markdown cell containing fenced Python for a code cell when that Python is intended to run. A fenced code example belongs inside Markdown only when the user wants it displayed rather than executed. List same-position insertions in final notebook order; for multiple position=end insertions, the first <EDIT> is the first inserted cell, followed by subsequent <EDIT> blocks.

For text operations, MATCH must uniquely identify current text; it is empty only for insert_start and insert_end. For edit_cell, an empty MATCH is valid only for an empty source cell. Match opening/closing fence lengths exactly; the gateway strips the outer fence. Preserve indentation and line breaks. Ask rather than guess when required context is missing.

CURRENT PROJECT FILE CONTEXT:
{file_context}

CURRENT USER EDIT REQUEST:
{user_prompt}
"""


def build_edit_prompt(user_prompt, file_context, *, include_instructions=True):
    """Build the first full edit prompt or a compact continuation prompt."""
    formatted_files = []
    for file in file_context:
        formatted_files.append(
            f'FILE: {file["reference"]}\n'
            f'PATH: {file["path"]}\n'
            f'CONTENT:\n'
            f'{file["content"]}'
        )

    files_text = "\n\n".join(formatted_files) if formatted_files else "(No project file was referenced.)"
    template = EDIT_PROTOCOL if include_instructions else EDIT_CONTINUATION
    return template.format(file_context=files_text, user_prompt=user_prompt)
