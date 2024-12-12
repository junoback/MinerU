import os
import json
from jinja2 import Template


def gather_all_images(output_dir):
    """
    遞迴搜尋 output_dir 下所有 content_list.json，整理出所有圖片資訊，以相對於 output_dir 的路徑儲存。
    """
    all_images = []
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith('content_list.json'):
                # 假設 content_list.json 所在的資料夾名稱作為 pdf_name
                pdf_name = os.path.basename(root)
                content_json_path = os.path.join(root, file)
                with open(content_json_path, 'r', encoding='utf-8') as f:
                    content_list = json.load(f)
                    for item in content_list:
                        if item.get("type") == "image":
                            # 將圖片完整路徑轉為相對於 output_dir 的路徑
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
    """
    根據 all_images 產生 HTML 頁面：
    - 使用 Bootstrap 作為樣式框架
    - 引入 MathJax，支援 LaTeX 公式顯示
    - 顯示每張圖片及其說明
    """
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>All Extracted Images</title>
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
            .pdf-name {
                font-size: 0.9rem; 
                color: #555;
            }
            .image-caption {
                font-style: italic;
                font-size: 0.95rem;
                color: #333;
                margin-top: 0.5rem;
            }
            .card {
                margin-bottom: 20px;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.05);
                overflow: hidden;
            }
            .card img {
                border-bottom: 1px solid #dee2e6;
                max-width: 100%;
                height: auto;
            }
            .page-idx {
                font-size: 0.8rem;
                color: #888;
            }
            header, footer {
                background: #343a40; 
                color: #fff; 
                padding: 1rem;
            }
            header h1 {
                margin: 0;
            }
            footer p {
                margin: 0;
            }
            .card-title {
                margin-bottom: 0.5rem;
            }
        </style>
    </head>
    <body>
        <header class="text-center">
            <h1>All Extracted Images</h1>
            <p class="lead">A collection of images extracted from all processed PDFs</p>
        </header>
        <div class="container my-4">
            <div class="row row-cols-1 row-cols-md-2 g-4">
            {% for image in images %}
                <div class="col">
                    <div class="card h-100">
                        <img src="{{ image.img_path }}" class="card-img-top" alt="Extracted image" />
                        <div class="card-body">
                            <h5 class="card-title pdf-name">From: {{ image.pdf_name }}</h5>
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
                </div>
            {% endfor %}
            </div>
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
    output_dir = "output_results"  # 根據實際情況調整
    all_images = gather_all_images(output_dir)
    generate_all_images_page(all_images, os.path.join(output_dir, "all_images.html"))