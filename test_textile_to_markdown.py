from textile_to_markdown import TextileToMarkdown

translator = TextileToMarkdown(github_org=None)
to_md = translator.to_md


def test_pre_code():
    text = "<pre>int j = 4;</pre>"
    assert to_md(text) == "\n```\nint j = 4;\n```\n"


def test_code_only():
    text = '<code class="cpp">int j = 4;</code>'
    assert to_md(text) == "`int j = 4;`"


def test_pre_code_class_1():
    text = """<pre><code class="cpp">
int i = 2;
</code></pre>"""
    assert to_md(text) == "\n```cpp\nint i = 2;\n```\n"


def test_pre_code_class_2():
    text = """<pre><code class="cpp">int i = 2;
</code></pre>"""
    assert to_md(text) == "\n```cpp\nint i = 2;\n```\n"


def test_pre_code_class_3():
    text = """<pre>
<code class="cpp">
int i = 2;
</code>
</pre>"""
    assert to_md(text) == "\n```cpp\nint i = 2;\n```\n"


def test_nested_unordered_list():
    text = """
* Item 1
** Nested item 2
"""
    assert to_md(text) == "\n- Item 1\n\t- Nested item 2\n"


def test_nested_ordered_list():
    text = """
# Item 1
## Nested item 2
"""
    assert to_md(text) == "\n1. Item 1\n\t1. Nested item 2\n"


def test_footnote_translation():
    text = """As shown in [12], x = y.

fn12. My reference"""
    assert to_md(text) == "As shown in [^12], x = y.\n\n[^12]: My reference"


def test_commit_hash():
    text = "commit:abcdefg"
    print(to_md(text, ""))
