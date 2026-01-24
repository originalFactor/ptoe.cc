# Copyright 2026 originalFactor
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
