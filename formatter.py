from os import walk
from yaml import safe_load, safe_dump

for root, _, files in walk("source/_posts"):
    for file in files:
        if not file.endswith(".md"):
            continue

        with open(f"{root}/{file}", encoding="utf-8") as f:
            content = f.read()

        splitted = content.split("---")
        frontmatter = safe_load(splitted[1])

        if "$" in content:
            frontmatter["mathjax"] = True

        splitted[1] = f"\n{safe_dump(frontmatter, allow_unicode=True)}---\n\n*xx*x"
        content = "---".join(splitted).replace("*xx*x---", "")

        with open(f"{root}/{file}", "w", encoding="utf-8") as f:
            f.write(content)
