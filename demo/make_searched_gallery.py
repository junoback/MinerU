import os
import json
from jinja2 import Template


def parse_keywords(keywords_file):
    """
    解析 key_words.txt 文件：
    每行必須以 '&', '|', 或 'x' 結尾，分別對應必須條件, 可選條件, 排除條件。
    """
    mandatory_keywords = []
    optional_keywords = []
    exclude_keywords = []

    with open(keywords_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rule_char = line[-1]  # 最後一個字元
            keyword = line[:-1].strip()  # 去掉最後字元後的關鍵字

            if rule_char == '&':
                mandatory_keywords.append(keyword)
            elif rule_char == '|':
                optional_keywords.append(keyword)
            elif rule_char == 'x':
                exclude_keywords.append(keyword)
            else:
                raise ValueError("每行關鍵字必須以 '&', '|', 或 'x' 結尾")

    return mandatory_keywords, optional_keywords, exclude_keywords


def sanitize_caption_for_search(captions):
    """
    將 captions (list of lines) 處理：
    在搜尋前，忽略 {From: ... Page: xx} 前的來源資訊，只保留 Page: 之後的內容。
    如果沒找到 Page: 行，則不截斷。
    """
    page_line_found = False
    search_lines = []

    for line in captions:
        if "Page:" in line:
            page_line_found = True
            continue
        if page_line_found:
            search_lines.append(line)

    if not page_line_found:
        # 沒有 Page: 行，保留全部
        search_lines = captions

    caption_text_for_search = ' '.join(search_lines)
    return caption_text_for_search


def keyword_filter(all_images, mandatory_keywords, optional_keywords, exclude_keywords):
    """
    根據關鍵字進行篩選:
    1. 若有 mandatory_keywords：所有必須關鍵字都要出現。
    2. 若無 mandatory_keywords 則至少需要一個 optional_keywords。
    3. 若有 exclude_keywords：只要出現任一排除關鍵字，就剔除該圖片。
    """
    filtered_images = []
    for image in all_images:
        captions = image.get("img_caption", [])
        caption_text_for_search = sanitize_caption_for_search(captions)

        # --- 檢查必須條件 ---
        if mandatory_keywords:
            # 有必須關鍵字，全部都要出現
            if not all(mk in caption_text_for_search for mk in mandatory_keywords):
                # 有必須關鍵字沒有出現則跳過
                continue
            # 必須關鍵字檢查通過
        else:
            # 無必須關鍵字 -> 至少一個 optional 關鍵字要出現
            if optional_keywords:
                if not any(ok in caption_text_for_search for ok in optional_keywords):
                    # 沒有任何 optional 關鍵字符合
                    continue
                # 有至少一個 optional 關鍵字符合則繼續
            else:
                # 沒有 mandatory, 沒有 optional，那就不過濾，直接通過 (即顯示全部)
                pass

        # --- 檢查排除條件 ---
        # 如果有 exclude_keywords，只要出現其中任一個，該圖片就不顯示。
        if exclude_keywords:
            if any(xk in caption_text_for_search for xk in exclude_keywords):
                # 出現排除關鍵字，剔除此圖片
                continue

        # 通過上述所有檢查則加入顯示清單
        filtered_images.append(image)

    return filtered_images


def gather_all_images(output_dir):
    all_images = []
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith('content_list.json'):
                pdf_name = os.path.basename(root)
                content_json_path = os.path.join(root, file)
                with open(content_json_path, 'r', encoding='utf-8') as f:
                    content_list = json.load(f)
                    for item in content_list:
                        if item.get("type") == "image":
                            absolute_img_path = os.path.join(root, item.get("img_path", ""))
                            relative_img_path = os.path.relpath(absolute_img_path, output_dir)

                            all_images.append({
                                "pdf_name": pdf_name,
                                "img_path": relative_img_path,
                                "img_caption": item.get("img_caption", []),
                                "page_idx": item.get("page_idx", None)
                            })
    return all_images


def generate_all_images_page(all_images, output_file):
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Filtered Images - Gallery</title>
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
            }
            header, footer {
                background: #343a40; 
                color: #fff; 
                padding: 1rem;
            }
            header h1, footer p {
                margin: 0;
            }

            .gallery {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: center;
                margin: 20px;
            }
            .gallery-item {
                width: 150px;
                max-width: 100%;
                cursor: pointer;
                overflow: hidden;
            }
            .gallery-item img {
                display: block;
                width: 100%;
                height: auto;
                border-radius: 8px;
                border: 1px solid #ccc;
            }
            .caption-container {
                margin-top: 5px;
                text-align: center;
                font-size: 0.9rem;
            }
            .pdf-name, .page-idx {
                font-size: 0.8rem;
                color: #555;
                margin: 0;
            }
            .image-caption {
                font-style: italic;
                font-size: 0.8rem;
                color: #333;
                margin: 2px 0 0 0;
            }
        </style>
    </head>
    <body>
        <header class="text-center">
            <h1>Filtered Images - Gallery</h1>
            <p class="lead">A thumbnail gallery of filtered images based on keyword rules</p>
        </header>

        <div class="gallery">
            {% for image in images %}
            <div class="gallery-item">
                <img src="{{ image.img_path }}" alt="Extracted image" />
                <div class="caption-container">
                    <p class="pdf-name">From: {{ image.pdf_name }}</p>
                    {% if image.page_idx is not none %}
                        <p class="page-idx">Page: {{ image.page_idx }}</p>
                    {% endif %}
                    {% if image.img_caption %}
                        {% for caption in image.img_caption %}
                            <p class="image-caption">{{ caption | safe }}</p>
                        {% endfor %}
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>

        <footer class="text-center">
            <p>© 2024 PDF Extraction Project</p>
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
    rendered_html = template.render(images=all_images)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(rendered_html)

    print(f"HTML file generated: {output_file}")


if __name__ == "__main__":
    output_dir = "output_results"
    keywords_file = "key_words.txt"

    # 1. 取得所有圖片清單
    all_images = gather_all_images(output_dir)

    # 2. 解析關鍵字
    mandatory_keywords, optional_keywords, exclude_keywords = parse_keywords(keywords_file)

    # 3. 根據關鍵字條件過濾圖片
    filtered_images = keyword_filter(all_images, mandatory_keywords, optional_keywords, exclude_keywords)

    # 4. 組合關鍵字並加入 HTML 檔名
    # 將所有關鍵字(必須 + 可選 + 排除)合併用底線連接
    all_keys = mandatory_keywords + optional_keywords + exclude_keywords
    if all_keys:
        joined_keys = "_".join(all_keys)
    else:
        joined_keys = "no_keyword"

    output_file = os.path.join(output_dir, f"all_imagesGallery_{joined_keys}.html")

    # 5. 產生網頁
    generate_all_images_page(filtered_images, output_file)