import os
import json
import re # Import regular expressions module
import argparse # Import argparse for command-line arguments
from jinja2 import Template
import datetime # For year in footer


def parse_keywords(keywords_file):
    """
    解析 option_and_key_words.txt 文件：
    - Lines starting with '@' define configuration options (e.g., @ignore_case = true).
    - Other non-empty lines must end with '&', '|', or 'x' for keywords.
    Returns:
        tuple: (mandatory_keywords, optional_keywords, exclude_keywords, file_config)
               where file_config is a dict of options found in the file.
    """
    mandatory_keywords = []
    optional_keywords = []
    exclude_keywords = []
    file_config = {} # Dictionary to store config from file

    # Define valid config keys and their expected types (boolean/string)
    valid_config_keys = {
        'ignore_case': 'boolean',
        'handle_plurals': 'boolean',
        'whole_word': 'boolean',
        'output_html_name': 'string'
    }

    try:
        with open(keywords_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'): # Skip empty lines and comments
                    continue

                if line.startswith('@'):
                    # --- Parse Configuration Line ---
                    if '=' not in line:
                        print(f"Warning: Invalid config format in {keywords_file} (line {line_num}): '{line}'. Expected '@key = value'. Skipping.")
                        continue
                    key_part, value_part = line[1:].split('=', 1) # Split only on the first '='
                    key = key_part.strip().lower()
                    value_str = value_part.strip().lower()

                    if key not in valid_config_keys:
                        print(f"Warning: Unknown config key '{key}' in {keywords_file} (line {line_num}). Skipping.")
                        continue

                    config_type = valid_config_keys[key]
                    parsed_value = None

                    if config_type == 'boolean':
                        if value_str == 'true':
                            parsed_value = True
                        elif value_str == 'false':
                            parsed_value = False
                        else:
                             print(f"Warning: Invalid boolean value '{value_str}' for key '{key}' in {keywords_file} (line {line_num}). Expected 'true' or 'false'. Skipping.")
                             continue
                    elif config_type == 'string':
                        parsed_value = value_part.strip() # Keep original case for filenames etc.
                    else:
                         # Should not happen if valid_config_keys is correct
                         print(f"Internal Warning: Unhandled config type '{config_type}' for key '{key}'. Skipping.")
                         continue

                    if parsed_value is not None:
                        file_config[key] = parsed_value
                        print(f"  Config from file: {key} = {parsed_value}")


                else:
                    # --- Parse Keyword Line ---
                    if len(line) < 2 or line[-1] not in ['&', '|', 'x']:
                        raise ValueError(f"Invalid keyword line format in {keywords_file} (line {line_num}): '{line}'. Each keyword line must end with '&', '|', or 'x'.")

                    rule_char = line[-1]
                    keyword = line[:-1].strip()
                    if not keyword:
                        raise ValueError(f"Empty keyword found in {keywords_file} (line {line_num}) for rule '{rule_char}'.")

                    if rule_char == '&':
                        mandatory_keywords.append(keyword)
                    elif rule_char == '|':
                        optional_keywords.append(keyword)
                    elif rule_char == 'x':
                        exclude_keywords.append(keyword)

    except FileNotFoundError:
        print(f"Error: Keywords file not found at '{keywords_file}'")
        # Return empty lists and config, allows running without a keywords file (shows all images)
        return [], [], [], {}
    except ValueError as e:
        print(f"Error parsing {keywords_file}: {e}")
        # Exit or return empty lists if parsing fails critically
        return [], [], [], {} # Return empty on critical parse error

    print(f"\nParsed keywords from '{keywords_file}':")
    print(f"  Mandatory (&): {mandatory_keywords}")
    print(f"  Optional (|):  {optional_keywords}")
    print(f"  Exclude (x):   {exclude_keywords}")
    return mandatory_keywords, optional_keywords, exclude_keywords, file_config

# --- Functions sanitize_caption_for_search, check_keyword_match, keyword_filter, gather_all_images remain unchanged ---
# (Copy them from the previous good version)

def sanitize_caption_for_search(captions):
    """
    將 captions (list of lines) 處理：
    在搜尋前，忽略 {From: ... Page: xx} 前的來源資訊，只保留 Page: 之後的內容。
    如果沒找到 Page: 行，則不截斷。
    """
    page_line_found = False
    search_lines = []
    header_lines = [] # Store header lines separately if needed later

    for line in captions:
        # Improved check to handle variations like "Page: N" or "Page: None"
        is_page_line = "Page:" in line and line.strip().startswith("Page:")
        is_from_line = "From:" in line and line.strip().startswith("From:")

        if is_from_line:
            header_lines.append(line)
            continue # Skip From line
        if is_page_line:
            header_lines.append(line)
            page_line_found = True
            continue # Skip Page line itself for search

        if page_line_found:
            search_lines.append(line)
        elif not is_from_line and not is_page_line:
            # If we haven't found Page: yet, and it's not From:, keep it for search
            # This handles cases where captions appear before From:/Page: or if From:/Page: are missing
             search_lines.append(line)

    caption_text_for_search = ' '.join(search_lines)
    return caption_text_for_search

def check_keyword_match(keyword, text, ignore_case=False, handle_plurals=False, whole_word=False):
    """
    Checks if a keyword exists in the text based on matching options.
    """
    kw = keyword.strip()
    if not kw:
        return False

    search_text = text
    flags = 0
    if ignore_case:
        flags |= re.IGNORECASE

    patterns = []
    kw_escaped = re.escape(kw)

    if whole_word:
        base_pattern = r'\b' + kw_escaped + r'\b'
        patterns.append(base_pattern)
        # Improved plural check: only add 's' if handle_plurals is true AND the word doesn't already end in 's' (case-insensitive check)
        if handle_plurals and not (kw.lower().endswith('s') if ignore_case else kw.endswith('s')):
            plural_pattern = r'\b' + kw_escaped + r's\b'
            patterns.append(plural_pattern)
            # Optional: consider 'es' for words ending in s, x, z, ch, sh? More complex. Sticking to simple 's'.
    else: # Substring matching
        patterns.append(kw_escaped)
        if handle_plurals and not (kw.lower().endswith('s') if ignore_case else kw.endswith('s')):
            patterns.append(kw_escaped + 's')

    for pattern in patterns:
        try:
            if re.search(pattern, search_text, flags):
                return True
        except re.error as e:
            print(f"Regex error for keyword '{keyword}' with pattern '{pattern}': {e}")
            return False
    return False

def keyword_filter(all_images, mandatory_keywords, optional_keywords, exclude_keywords,
                   ignore_case=False, handle_plurals=False, whole_word=False):
    """
    根據關鍵字進行篩選, 包含大小寫忽略、複數處理、全字匹配選項:
    1. 若有 mandatory_keywords：所有必須關鍵字都要出現。
    2. 若無 mandatory_keywords 則至少需要一個 optional_keywords (若有)。
    3. 若有 exclude_keywords：只要出現任一排除關鍵字，就剔除該圖片。
    """
    filtered_images = []
    for image in all_images:
        captions = image.get("img_caption", [])
        caption_text_for_search = sanitize_caption_for_search(captions)

        # --- 檢查排除條件 (優先檢查，效率較高) ---
        excluded = False
        if exclude_keywords:
            for xk in exclude_keywords:
                if check_keyword_match(xk, caption_text_for_search, ignore_case, handle_plurals, whole_word):
                    excluded = True
                    break
        if excluded:
            continue

        # --- 檢查必須條件 ---
        passes_mandatory = True
        if mandatory_keywords:
            for mk in mandatory_keywords:
                if not check_keyword_match(mk, caption_text_for_search, ignore_case, handle_plurals, whole_word):
                    passes_mandatory = False
                    break
            if not passes_mandatory:
                continue
        else:
            # --- 無必須關鍵字 -> 檢查可選條件 ---
            if optional_keywords:
                passes_optional = False
                for ok in optional_keywords:
                    if check_keyword_match(ok, caption_text_for_search, ignore_case, handle_plurals, whole_word):
                        passes_optional = True
                        break
                if not passes_optional:
                    continue
            # else: No mandatory AND no optional keywords - image passes (shows all non-excluded)

        filtered_images.append(image)
    return filtered_images

def gather_all_images(output_dir):
    all_images = []
    if not os.path.isdir(output_dir):
        print(f"Error: Output directory '{output_dir}' not found.")
        return []

    print(f"Scanning for images in '{output_dir}'...")
    count = 0
    json_files_found = 0
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith('content_list.json'):
                json_files_found += 1
                pdf_name = os.path.basename(root)
                content_json_path = os.path.join(root, file)
                try:
                    with open(content_json_path, 'r', encoding='utf-8') as f:
                        content_list = json.load(f)
                        for item in content_list:
                            if item.get("type") == "image":
                                img_rel_path = item.get("img_path")
                                if not img_rel_path:
                                    print(f"Warning: Image item in {content_json_path} has no 'img_path'. Skipping.")
                                    continue
                                absolute_img_path = os.path.normpath(os.path.join(root, img_rel_path))
                                final_relative_img_path = os.path.relpath(absolute_img_path, output_dir)
                                all_images.append({
                                    "pdf_name": pdf_name,
                                    "img_path": final_relative_img_path.replace("\\", "/"),
                                    "img_caption": item.get("img_caption", []),
                                    "page_idx": item.get("page_idx", None)
                                })
                                count += 1
                except json.JSONDecodeError:
                    print(f"Error: Could not decode JSON from '{content_json_path}'. Skipping file.")
                except Exception as e:
                    print(f"Error processing file '{content_json_path}': {e}")

    print(f"Found {json_files_found} JSON files and gathered {count} images.")
    return all_images


# --- generate_all_images_page needs a slight update for the year ---
def generate_all_images_page(images, output_file, keyword_summary):
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Filtered Images - {{ keyword_summary.title }}</title>
        <!-- Bootstrap CSS -->
        <link
            rel="stylesheet"
            href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css"
            integrity="sha384-rbsA2VBKQ7LdU+Ju81tP3SjJbfM2P2nv/QDnh0D6tYp7VSpm6La7N5M51ek36tJr"
            crossorigin="anonymous"
        >

        <!-- MathJax Configuration -->
        <script>
        window.MathJax = {
          tex: {
            inlineMath: [['$', '$'], ['\\(', '\\)']],
            displayMath: [['$$','$$'], ['\\[','\\]']]
          },
          startup: {
            pageReady: function() {
               return MathJax.typesetPromise();
            }
          }
        };
        </script>
        <script id="MathJax-script" async
            src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml-full.js"></script>

        <style>
            body {
                background-color: #f8f9fa;
                padding-top: 20px;  /* 原本是 80px，現在 header 不固定了就可以減少 */
                padding-bottom: 60px;
            }
            
            header {
                background: #343a40;
                color: #fff;
                padding: 1rem;
                width: 100%;
                box-shadow: 0 2px 4px rgba(0,0,0,.1);
                position: static; /* 或乾脆拿掉 position 整行 */
            }
            footer {
                background: #343a40;
                color: #fff;
                padding: 1rem;
                position: fixed;
                bottom: 0;
                left: 0;
                width: 100%;
                z-index: 1000;
                box-shadow: 0 -2px 4px rgba(0,0,0,.1);
                font-size: 0.9rem;
            }
            header h1, footer p {
                margin: 0;
            }
            .search-details {
                font-size: 0.85rem; /* Slightly smaller */
                color: #adb5bd;
                margin-top: 5px;
                line-height: 1.6; /* Improve readability */
            }
            .search-details strong {
                color: #dee2e6; /* Lighter strong text */
            }
            .keyword {
                 display: inline-block;
                 padding: 0.1em 0.4em;
                 margin: 0 2px;
                 font-size: 0.85em;
                 font-weight: bold;
                 line-height: 1;
                 color: #fff;
                 text-align: center;
                 white-space: nowrap;
                 vertical-align: baseline;
                 border-radius: 0.25rem;
                 margin-bottom: 3px; /* Space between keywords if wrapped */
            }
            .kw-mandatory { background-color: #dc3545; } /* Red */
            .kw-optional { background-color: #198754; } /* Green */
            .kw-exclude { background-color: #6c757d; } /* Grey */
            .opt-label { font-weight: bold; color: #ffc107; } /* Yellow for option labels */
            .opt-value { font-style: italic; color: #e9ecef; } /* Italic value */

            .gallery {
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                justify-content: center;
                margin: 20px auto;
                padding: 0 15px;
                max-width: 1600px;
            }
            .gallery-item {
                width: 200px;
                background-color: #fff;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                overflow: hidden;
                display: flex;
                flex-direction: column;
                 padding-bottom: 10px;
            }
            .gallery-item img {
                display: block;
                width: 100%;
                height: 150px;
                object-fit: contain;
                border-bottom: 1px solid #eee;
                 background-color: #f0f0f0;
            }
            .caption-container {
                padding: 10px;
                text-align: left;
                font-size: 0.85rem;
                overflow-y: auto;
                max-height: 150px;
                flex-grow: 1;
            }
            .pdf-name, .page-idx {
                font-size: 0.75rem;
                color: #555;
                margin: 0 0 2px 0;
                font-weight: bold;
            }
             .page-idx { color: #007bff; }
            .image-caption {
                font-style: italic;
                font-size: 0.8rem;
                color: #333;
                margin: 4px 0 0 0;
                word-wrap: break-word;
            }
             .no-images {
                text-align: center;
                font-size: 1.2rem;
                color: #6c757d;
                margin-top: 50px;
            }
        </style>
    </head>
    <body>
        <header class="text-center">
            <h1>{{ keyword_summary.title }}</h1>
            <div class="search-details">
                <strong>{{ images | length }}</strong> image(s) found. &nbsp;
                {% if keyword_summary.mandatory %}
                    <strong>Mandatory:</strong> {% for kw in keyword_summary.mandatory %}<span class="keyword kw-mandatory">{{ kw }}</span>{% endfor %} &nbsp;
                {% endif %}
                {% if keyword_summary.optional %}
                    <strong>Optional:</strong> {% for kw in keyword_summary.optional %}<span class="keyword kw-optional">{{ kw }}</span>{% endfor %} &nbsp;
                {% endif %}
                {% if keyword_summary.exclude %}
                    <strong>Exclude:</strong> {% for kw in keyword_summary.exclude %}<span class="keyword kw-exclude">{{ kw }}</span>{% endfor %} &nbsp;
                {% endif %}
                 <br> <!-- New line for options -->
                 <strong>Options:</strong>
                 <span class="opt-label">IgnoreCase:</span> <span class="opt-value">{{ 'Yes' if keyword_summary.ignore_case else 'No' }}</span> <span class="opt-source">({{ keyword_summary.sources.ignore_case }})</span> &nbsp;
                 <span class="opt-label">Plurals(+s):</span> <span class="opt-value">{{ 'Yes' if keyword_summary.handle_plurals else 'No' }}</span> <span class="opt-source">({{ keyword_summary.sources.handle_plurals }})</span> &nbsp;
                 <span class="opt-label">WholeWord:</span> <span class="opt-value">{{ 'Yes' if keyword_summary.whole_word else 'No' }}</span> <span class="opt-source">({{ keyword_summary.sources.whole_word }})</span> &nbsp;
                 {% if keyword_summary.output_html_name %}
                    <span class="opt-label">Output Name:</span> <span class="opt-value">{{ keyword_summary.output_html_name }}</span> <span class="opt-source">({{ keyword_summary.sources.output_html_name }})</span>
                 {% endif %}
            </div>
        </header>

        {% if images %}
        <div class="gallery">
            {% for image in images %}
            <div class="gallery-item">
                <img src="{{ image.img_path }}" alt="Extracted from {{ image.pdf_name }} page {{ image.page_idx }}" loading="lazy" />
                <div class="caption-container">
                    <p class="pdf-name">From: {{ image.pdf_name }}</p>
                    {% if image.page_idx is not none %}
                        <p class="page-idx">Page: {{ image.page_idx }}</p>
                    {% endif %}
                    {% if image.img_caption %}
                        {% set page_found = false %}
                        {% for caption_line in image.img_caption %}
                             {% if 'Page:' in caption_line and caption_line.strip().startswith("Page:") %}
                                 {% set page_found = true %}
                              {% elif page_found %}
                                  <p class="image-caption">{{ caption_line | safe }}</p>
                             {% endif %}
                        {% endfor %}
                         {% if not page_found %}
                            {% for caption_line in image.img_caption %}
                                {% if not ('From:' in caption_line and caption_line.strip().startswith("From:")) %}
                                    <p class="image-caption">{{ caption_line | safe }}</p>
                                {% endif %}
                            {% endfor %}
                         {% endif %}
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
            <p class="no-images">No images found matching the specified criteria.</p>
        {% endif %}

        <footer class="text-center">
            <p>© {{ keyword_summary.year }} PDF Extraction Project. Generated on {{ keyword_summary.generation_time }}</p>
        </footer>

        <!-- Bootstrap JS -->
        <script
            src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"
            integrity="sha384-kenU1KFdBIe4zVF0s0G1M5b4hcpxyD9F7jL+7H8q7EILv6G7Z3whsmXKp4yh3YNa"
            crossorigin="anonymous"></script>
    </body>
    </html>
    """

    template = Template(html_template)
    rendered_html = template.render(images=images, keyword_summary=keyword_summary)

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(rendered_html)
        print(f"HTML gallery generated: {output_file}")
    except IOError as e:
        print(f"Error writing HTML file '{output_file}': {e}")


if __name__ == "__main__":
    # --- 1. Setup Argument Parser (Define defaults) ---
    parser = argparse.ArgumentParser(description="Generate an HTML gallery of images based on keyword filtering. Options can be set in option_and_key_words.txt (prefixed with '@') and overridden by command-line arguments.")
    parser.add_argument(
        "-o", "--output-dir",
        default="output_results",
        help="Directory containing the extracted PDF results."
    )
    parser.add_argument(
        "-k", "--keywords-file",
        default="option_and_key_words.txt",
        help="Path to the file containing keywords and optionally '@' config lines."
    )
    # Flags: default is False, presence of flag sets it to True
    parser.add_argument(
        "-i", "--ignore-case",
        action="store_true",
        help="Perform case-insensitive matching (overrides file config)."
    )
    parser.add_argument(
        "-p", "--handle-plurals",
        action="store_true",
        help="Also match simple plural forms (+s) (overrides file config)."
    )
    parser.add_argument(
        "-w", "--whole-word",
        action="store_true",
        help="Match whole words only (overrides file config)."
    )
    # String argument: default is empty string
    parser.add_argument(
        "--output-html-name",
        default=None, # Use None to easily check if user provided it
        help="Specify a base name for the output HTML file (overrides file config)."
    )

    args = parser.parse_args()

    # --- 2. Parse Keywords and File Configuration ---
    print(f"Parsing keywords and config from: {args.keywords_file}")
    mandatory_keywords, optional_keywords, exclude_keywords, file_config = parse_keywords(args.keywords_file)

    # --- 3. Determine Final Configuration (CLI > File > Default) ---
    config_sources = {} # Track where each final config value came from

    # Default values
    final_ignore_case = False
    final_handle_plurals = False
    final_whole_word = False
    final_output_html_name = "" # Default base name is empty (will use keywords)

    # Apply file config first
    if 'ignore_case' in file_config:
        final_ignore_case = file_config['ignore_case']
        config_sources['ignore_case'] = 'File'
    else:
        config_sources['ignore_case'] = 'Default'

    if 'handle_plurals' in file_config:
        final_handle_plurals = file_config['handle_plurals']
        config_sources['handle_plurals'] = 'File'
    else:
        config_sources['handle_plurals'] = 'Default'

    if 'whole_word' in file_config:
        final_whole_word = file_config['whole_word']
        config_sources['whole_word'] = 'File'
    else:
        config_sources['whole_word'] = 'Default'

    if 'output_html_name' in file_config:
         final_output_html_name = file_config['output_html_name']
         config_sources['output_html_name'] = 'File'
    else:
         config_sources['output_html_name'] = 'Default'


    # Apply CLI overrides (if flag is set for booleans, or value is not None for string)
    if args.ignore_case: # If -i flag was used
        final_ignore_case = True
        config_sources['ignore_case'] = 'CLI'
    if args.handle_plurals: # If -p flag was used
        final_handle_plurals = True
        config_sources['handle_plurals'] = 'CLI'
    if args.whole_word: # If -w flag was used
        final_whole_word = True
        config_sources['whole_word'] = 'CLI'
    if args.output_html_name is not None: # If --output-html-name was used
        final_output_html_name = args.output_html_name
        config_sources['output_html_name'] = 'CLI'


    print("\n--- Final Script Configuration ---")
    print(f"Output Directory: {args.output_dir}")
    print(f"Keywords File: {args.keywords_file}")
    print(f"Ignore Case: {final_ignore_case} (Source: {config_sources['ignore_case']})")
    print(f"Handle Plurals (+s): {final_handle_plurals} (Source: {config_sources['handle_plurals']})")
    print(f"Whole Word Match: {final_whole_word} (Source: {config_sources['whole_word']})")
    print(f"Output HTML Base Name: '{final_output_html_name}' (Source: {config_sources['output_html_name']})")
    print("--------------------------------\n")


    # --- 4. Gather Images ---
    all_images = gather_all_images(args.output_dir)
    if not all_images:
        print("No images found or error gathering images. Exiting.")
        exit()


    # --- 5. Filter Images using Final Config ---
    print("Filtering images based on keywords and final options...")
    filtered_images = keyword_filter(
        all_images,
        mandatory_keywords,
        optional_keywords,
        exclude_keywords,
        ignore_case=final_ignore_case,
        handle_plurals=final_handle_plurals,
        whole_word=final_whole_word
    )
    print(f"Filtering complete. Found {len(filtered_images)} matching images.")

    # --- 6. Determine Output HTML Filename ---
    if final_output_html_name:
         base_html_name = final_output_html_name
         # Sanitize provided name just in case
         base_html_name = re.sub(r'[^\w\-]+', '_', base_html_name) # Replace non-alphanumeric/- characters with _
    else:
        # Use keywords for the filename if no specific name is given
        all_keys = mandatory_keywords + optional_keywords + exclude_keywords
        sanitized_keys = [re.sub(r'[^\w\-]+', '', k) for k in all_keys]
        joined_keys = "_".join(sanitized_keys)[:50]
        if not joined_keys:
            joined_keys = "all_images" if not mandatory_keywords and not optional_keywords and not exclude_keywords else "filtered"
        base_html_name = f"gallery_{joined_keys}"

    # Add options indicators to filename for clarity, unless a specific name was given
    options_suffix = ""
    # Only add suffix if a specific name wasn't given, or maybe always add it? Let's always add it for consistency.
    if final_ignore_case: options_suffix += "_i"
    if final_handle_plurals: options_suffix += "_p"
    if final_whole_word: options_suffix += "_w"

    output_html_file = os.path.join(args.output_dir, f"{base_html_name}{options_suffix}.html")

    # --- 7. Prepare Summary for HTML Page ---
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    keyword_summary = {
        "title": f"Filtered Gallery ({base_html_name}{options_suffix})",
        "mandatory": mandatory_keywords,
        "optional": optional_keywords,
        "exclude": exclude_keywords,
        "ignore_case": final_ignore_case,
        "handle_plurals": final_handle_plurals,
        "whole_word": final_whole_word,
        "output_html_name": final_output_html_name, # Store the base name used
        "sources": config_sources, # Show where settings came from
        "year": datetime.datetime.now().year,
        "generation_time": current_time
    }

    # --- 8. Generate HTML Page ---
    generate_all_images_page(filtered_images, output_html_file, keyword_summary)

    print("\nScript finished.")