import textwrap
from htmlgen import Contents, Element, HtmlSequence, Registry


r = Registry()


@r.style("""
    font-size: 1em;
    font-weight: 700;
""")
def page_title() -> Element:
    return Element("h1").containing("Demo Page")


@r.style("""
    background-color: lightred;

    & > h2 {
      font-size: 1.5em;
      font-weight: 300;
    }
""")
def demo_box(*contents: Contents) -> Element:
    return Element("div").containing(
        Element("h2").containing("Demo Box"),
        *contents,
    )


list_of_things = [
    Element("p").containing("These are the things:"),
    Element("ol", attributes={"start": "2", "type": "a"}).containing(
        Element("li").containing("Minute"),
        Element("li").containing("Second"),
        Element("li").containing("Third"),
    ),
]


rendered_html = HtmlSequence(
    [
        page_title(),
        demo_box(*list_of_things),
    ]
).render(indent="", inline=False)

rendered_css = r.render_stylesheet()

print("HTML:")
print(textwrap.indent(rendered_html, "| ", lambda line: True))
print("CSS:")
print(textwrap.indent(rendered_css, "| ", lambda line: True))
