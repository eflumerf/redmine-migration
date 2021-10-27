from repositories_to_migrate import GITHUB_ORG
import re


def to_md_normal(result, repo):
    # Unordered lists
    result = re.sub(r"^\* ", "- ", result, flags=re.MULTILINE)
    result = re.sub(r"^\*\* ", "\t- ", result, flags=re.MULTILINE)

    # Ordered lists
    result = re.sub(r"^\# ", "1. ", result, flags=re.MULTILINE)
    result = re.sub(r"^\#\# ", "\t1. ", result, flags=re.MULTILINE)

    # Type face
    result = re.sub(r"\*(.*?)\*", r"**\1**", result)  # Bold-face
    result = re.sub(r"\b\_(.*?)\_\b", r"*\1*", result)  # Italicized

    # Headings
    result = re.sub(r"^h1\.", "#", result, flags=re.MULTILINE)
    result = re.sub(r"^h2\.", "##", result, flags=re.MULTILINE)
    result = re.sub(r"^h3\.", "###", result, flags=re.MULTILINE)
    result = re.sub(r"^h4\.", "####", result, flags=re.MULTILINE)

    # Footnotes
    result = re.sub(r"\[(\d+)\]", r"[^\1]", result)
    result = re.sub(r"^fn(\d+)\. ", r"[^\1]: ", result, flags=re.MULTILINE)

    # Issues
    result = re.sub(r"(\w+)\s+\#(\d{3,5})", r"Redmine \1 \2", result)

    # Commit references
    result = re.sub(
        r"(\w+):commit:([a-f0-9]+)",
        f"https://github.com/{GITHUB_ORG}/" + r"\1/commit/\2",
        result,
    )
    result = re.sub(
        r"commit:([a-f0-9]+)",
        f"https://github.com/{GITHUB_ORG}/{repo}/" + r"commit/\1",
        result,
    )

    return result


def to_md_inline(result):
    result = re.sub(r"@(.*?)@", r"`\1`", result)
    return result


def to_md_code(result):
    result = re.sub(
        r'<code class=".*?">(.*?)</code>', r"`\1`", result
    )  # GitHub cannot support inline syntax highlighting
    result = re.sub(
        r'<code class="(.*?)">(.*?)</code>', r"\1\2", result, flags=re.DOTALL
    )  # Syntax highlighting
    return result


def to_md_pre(result):
    result = re.sub(
        r"<pre>(.*?)</pre>", r"\n```\n\1\n```\n", result
    )  # Inline code blocks
    result = re.sub(
        r'<pre>\n?<code class="(.*)">\n?(.*?)\n?</code>\n?</pre>',
        r"\n```\1\n\2\n```\n",
        result,
        flags=re.DOTALL,
    )  # Code blocks
    result = re.sub(
        r"<pre>\n?(.*?)^\n</pre>",
        r"\n```\n\1\n```\n",
        result,
        flags=re.DOTALL,
    )  # First make sure there are newlines after/before the pre tags
    return result


class TextileToMarkdown:
    def __init__(self, github_org):
        self._gh_org = github_org

    def to_md(self, textile_str, repo=""):
        fields = re.split(
            r'(<pre>.*?</pre>|@.*?@|<code class=".*?">.*?</code>)',
            textile_str,
            flags=re.DOTALL,
        )

        result = ""
        for f in fields:
            if f.startswith("<pre>"):
                result += to_md_pre(f)
            elif f.startswith("@"):
                result += to_md_inline(f)
            elif f.startswith("<code"):
                result += to_md_code(f)
            else:
                result += to_md_normal(f, repo)

        return result
