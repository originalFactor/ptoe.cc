# ------------------------
# Imports
# ------------------------

from hmac import new
from yaml import safe_load, YAMLError, safe_dump
from os import walk, getenv
from os.path import join as pathjoin, isfile
from openai import OpenAI
from json import loads
from typing import cast

# ------------------------
# Global variables
# ------------------------

waiting_translate: set[str] = set()
exist_tags: set[str] = set()
exist_categories: set[str] = set()
exist_category_paths: set[str] = set()
need_analyze: set[str] = set()


# ------------------------
# Pre-check required files
# ------------------------

if not isfile("_config.before.yml"):
    raise FileNotFoundError("_config.before.yml not found.")


# ------------------------
# Load known tags
# ------------------------

print("Loading known_tags.yaml")

known_translate: dict[str, str]  # name: url_friendly

if isfile("known_tags.yaml"):
    with open("known_tags.yaml", encoding="utf-8") as f:
        known_translate = safe_load(f)
else:
    known_translate = {}

# ------------------------
# Load LLM config
# ------------------------

# 优先从环境变量读取，用于 GitHub Actions
_endpoint = getenv("LLM_ENDPOINT")
_model = getenv("LLM_MODEL")
_api_key = getenv("LLM_API_KEY")

# 如果环境变量不存在，尝试从本地文件读取
if not all([_endpoint, _model, _api_key]):
    if isfile("llm.txt"):
        with open("llm.txt", encoding="utf-8") as f:
            parts = f.read().split()
            _endpoint, _model, _api_key = parts[0], parts[1], parts[2]
    else:
        raise ValueError(
            "LLM configuration not found. Set LLM_ENDPOINT, LLM_MODEL, LLM_API_KEY environment variables or create llm.txt file."
        )

if not _endpoint or not _model or not _api_key:
    raise ValueError("LLM configuration incomplete.")

endpoint: str = _endpoint
model: str = _model
api_key: str = _api_key

client = OpenAI(api_key=api_key, base_url=endpoint)


# ------------------------
# Get all tags and categories from posts
# ------------------------

print("Loading posts...")

for root, dirs, files in walk("source/_posts"):
    for file in files:
        if not file.endswith(".md"):
            continue

        filepath = pathjoin(root, file)
        print(f"Loading {filepath}")

        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        try:
            data = safe_load(content.split("---")[1])
        except YAMLError as e:
            print(f"Error loading {file}: {e}")
            continue

        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = [tags]
        exist_tags.update(tags)

        categories = data.get("categories") or []
        if not isinstance(categories, list):
            categories = [categories]
        exist_categories.update(categories)
        exist_category_paths.add("/".join(categories))

        if not data.get("ai_analyzed"):
            need_analyze.add(filepath)

print()
print(f"Gathered {len(exist_tags)} tags and {len(exist_categories)} categories. ")


# ------------------------
# Analyze posts
# ------------------------


def analyze():
    global exist_tags, exist_categories

    print()
    print(f"Need to analyze {len(need_analyze)} posts.")

    SYSTEM_PROMPT = """
    系统会给出现有标签和分类，以及一个Markdown文档。
    请分析文档内容，并根据现有标签和分类，对文档进行合理分类，并使用JSON格式返回。
    若现有标签无法对文档进行合理分类和标注，或有不全面的地方，可以适当新增标签和分类。

    示例输入：
    ```txt
    Tags: C++, GESP, Python, 数据结构, LeetCode, Android, Windows, Linux, MacOS, iOS
    Categories: 编程/算法, 编程/应用, 日志, 软件, 数学, 哲学（*2）
    Document:
    ```md
    # 题目描述
    给你一个整数数组 `nums` 和一个整数 `k`。

    每一步操作中，你需要从数组中选出并删除一个元素。

    返回使数组中剩余元素的总和等于 `k` 所需的最少操作数。
    ```
    ```

    示例返回：
    ```json
    {
        "tags": ["C++", ...],
        "categories": ["编程", "算法"]（*1）
    }
    ```

    *: 标注*的地方为注释，实际返回中无需返回。
    *1: 返回的categories中的内容由左至右为层级关系，如 `["编程", "算法"]` 即表示 `编程/算法` 这个分类。而tags中的内容为平级关系。
    *2：此处的categories表示在整个知识库范围内已存在的层级关系列表，但你也可以灵活运用，比如直接使用 `编程` 这个父分类或 `日志/日常` 这种子分类。
        需要注意的是你应该尽量避免在两个地方出现同一个分类名，比如 `编程/算法` 和 `算法`、`数学/算法`...
    """

    added_tags: set[str] = set()
    added_categories: set[str] = set()
    added_category_paths: set[str] = set()

    for filepath in need_analyze:
        print(f"Analyzing {filepath}")

        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Tags: {', '.join(exist_tags | added_tags)}\n"
                    f"Categories: {', '.join(exist_category_paths | added_category_paths)}\n"
                    f"Document:\n```md\n{content}\n```",
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        json_obj: dict[str, list[str]] = loads(
            response.choices[0].message.content or "{}"
        )
        new_tags: set[str] = set(json_obj.get("tags") or [])
        new_categories: list[str] = json_obj.get("categories") or []
        category_path = "/".join(new_categories)
        added_tags |= new_tags - exist_tags
        added_categories |= set(new_categories) - exist_categories

        if category_path not in exist_category_paths:
            added_category_paths.add(category_path)

        splitted = content.split("---")
        has_frontmatter = False
        try:
            frontmatter = safe_load(splitted[1])
        except YAMLError as e:
            print(f"Error loading frontmatter of {file}: {e}")
            frontmatter = {}
        else:
            has_frontmatter = True

        frontmatter["tags"] = list(new_tags)
        frontmatter["categories"] = list(new_categories)
        frontmatter["ai_analyzed"] = True

        print(f"New tags: {new_tags}")
        print(f"New categories: {new_categories}")

        frontmatter_str = safe_dump(frontmatter, allow_unicode=True)
        if has_frontmatter:
            splitted[1] = f"\n{frontmatter_str}\n"
        else:
            splitted.insert(0, f"---\n{frontmatter_str}\n")
        content = "---".join(splitted)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    print(
        f"Totally added {len(added_tags)} tags and {len(added_categories)} categories: \n{', '.join(added_tags | added_categories)}"
    )
    exist_tags |= added_tags
    exist_categories |= added_categories


if need_analyze:
    analyze()


# ------------------------
# Check tags and categories
# ------------------------

print()
print(f"Total {len(exist_tags)} tags and {len(exist_categories)} categories. ")

merged = exist_tags | exist_categories
for tag in merged:
    print(
        f"{tag}: Tag: {tag in exist_tags}, Category: {tag in exist_categories}, Known: {known_translate.get(tag)}"
    )
    if tag not in known_translate:
        waiting_translate.add(tag)


# ------------------------
# Translate tags
# ------------------------


def translate():

    print(f"Waiting to translate {len(waiting_translate)} tags.")

    SYSTEM_PROMPT = """
    系统会给出标签的中文名称，用英文逗号隔开，你需要返回一个 JSON 格式的字符串，包含标签的中文名称和 URL 友好的名称。

    示例：

    Input
    ```txt
    编程, C++, GESP, Python, 算法, 数据结构, LeetCode, 力扣
    ```

    Output
    ```json
    {
        "编程": "programming",
        "C++": "cpp",
        "GESP": "gesp",
        "Python": "python",
        "算法": "algorithm",
        "数据结构": "data-structure",
        "LeetCode": "leetcode",
        "力扣": "leetcode"
    }
    ```
    """

    print()
    print("Sending request to LLM...")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ", ".join(waiting_translate)},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    json_obj: dict[str, str] = loads(response.choices[0].message.content or "{}")

    print("New knowledge get:")
    for tag, url_friendly in json_obj.items():
        known_translate[tag] = url_friendly
        print(f"{tag}: {url_friendly}")

    known_translate.update(json_obj)
    with open("known_tags.yaml", "w", encoding="utf-8") as f:
        safe_dump(known_translate, f, allow_unicode=True)

    print(f"Updated {len(json_obj)} tags.")


if waiting_translate:
    translate()


# ------------------------
# Generate _config.yml
# ------------------------

print()
print("Generating _config.yml...")

with open("_config.before.yml", encoding="utf-8") as f:
    config = safe_load(f)

config["tag_map"] = {
    tag: known_translate[tag] for tag in exist_tags if tag in known_translate
}

config["category_map"] = {
    category: known_translate[category]
    for category in exist_categories
    if category in known_translate
}

with open("_config.yml", "w", encoding="utf-8") as f:
    safe_dump(config, f, allow_unicode=True)

print(
    f"Generated _config.yml with {len(config['tag_map'])} tags and {len(config['category_map'])} categories."
)
