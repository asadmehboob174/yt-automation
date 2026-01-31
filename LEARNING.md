# LEARNING.md

Documenting key technical challenges and solutions for the AI Video Factory project.

## LLM JSON Generation & Parsing (Qwen 2.5 / Mistral)

### Usage Context
When generating complex JSON structures (like script breakdowns) with free/open-source models via HuggingFace Inference API, we encountered persistent `JSONDecodeError`s.

### Common Malformed Output Patterns

1. **Duplicate/Stuttering Quotes:**
   ```json
   "prompt": ""A high-quality 3D render..."
   ```

2. **Unescaped Internal Quotes:**
   ```json
   "dialogue": "[CHAR]: (angry) "My lord, stop!""
   ```

3. **Smart/Curly Quotes:**
   Models sometimes use unicode curly quotes (`"`, `"`) instead of ASCII (`"`).

4. **Single Quotes for Strings:**
   ```json
   "prompt": 'A high-quality 3D render...'
   ```

### Robust Repair Solution (`_clean_json_text` in script_generator.py)

#### Step 1-2: Extract JSON from markdown and find boundaries

#### Step 3: Unicode Normalization
```python
quote_chars = ['\u201c', '\u201d', '\u201e', '\u201f', '\u2033', ...]
for qc in quote_chars:
    text = text.replace(qc, '"')
```

#### Step 3.5: Single Quote Conversion
```python
def fix_single_quotes(match):
    key_part = match.group(1)
    value = match.group(2)
    value_escaped = value.replace('"', '\\"')
    return f'{key_part}"{value_escaped}"'

text = re.sub(r'("[\w_]+":\s*)\'(.+?)\'(?=\s*[,}\n])', fix_single_quotes, text, flags=re.DOTALL)
```

#### Step 4: Duplicate Quote Removal
```python
text = re.sub(r'"{2,}', '"', text)
```

#### Step 5: Newline Escaping in String Values

#### Final Repair (in except block): Internal Quote Escaping
```python
def fix_internal_quotes(match):
    prefix = match.group(1)  # e.g., '"dialogue": "'
    value = match.group(2)
    suffix = match.group(3)  # closing '"'
    value_fixed = re.sub(r'(?<!\\)"', r'\\"', value)
    return f'{prefix}{value_fixed}{suffix}'
```

### Best Practices
- Make Pydantic model fields optional with defaults for resilience
- Always implement multi-layer repair (initial clean → fallback repair)
- Add detailed error logging with line/column context for debugging
