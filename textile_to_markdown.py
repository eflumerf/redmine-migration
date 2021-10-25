import re


def to_md_normal(result):
    # Type face
    result = re.sub(r"\*(.*?)\*", r"**\1**", result)  # Bold-face
    result = re.sub(r"\b\_(.*?)\_\b", r"*\1*", result)  # Italicized

    # Lists
    result = re.sub(r"^\* ", "- ", result, flags=re.MULTILINE)  # Un-numbered lists
    result = re.sub(r"^\# ", "1. ", result, flags=re.MULTILINE)  # Numbered lists

    # Headings
    result = re.sub(r"^h1\.", "#", result, flags=re.MULTILINE)
    result = re.sub(r"^h2\.", "##", result, flags=re.MULTILINE)
    result = re.sub(r"^h3\.", "###", result, flags=re.MULTILINE)
    result = re.sub(r"^h4\.", "####", result, flags=re.MULTILINE)

    # Issues
    result = re.sub(r"\s+\#(\d{3,5})", r"Redmine issue \1", result)

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
        r"<pre>(.*?)</pre>", r"```\1```", result, flags=re.DOTALL
    )  # Code blocks
    result = re.sub(
        r'<code class="(.*?)">(.*?)</code>', r"\1\2", result, flags=re.DOTALL
    )  # Syntax highlighting
    return result


def to_md(textile_str):
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
            result += to_md_normal(f)

    return result
