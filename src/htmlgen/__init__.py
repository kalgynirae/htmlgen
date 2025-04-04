from __future__ import annotations

import html
import logging
import re
import textwrap
import unittest
from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Self, TypeVar, cast

logger = logging.getLogger(__name__)


DATA_KEY_PATTERN = re.compile("[a-z][a-z-]*")


class HtmlRenderable(metaclass=ABCMeta):
    @abstractmethod
    def render(self, indent: str, inline: bool) -> str: ...

    @property
    @abstractmethod
    def must_be_inline(self) -> bool: ...

    def with_attribute(self: Self, **attributes: str | None) -> Self:
        logger.warning("with_attribute ignored on %r", self)
        return self

    def with_class(self: Self, *classnames: str) -> Self:
        logger.warning("with_class ignored on %r", self)
        return self


@dataclass(frozen=True)
class Element(HtmlRenderable):
    type: str
    attributes: dict[str, str | None] = field(default_factory=dict)
    children: list[HtmlRenderable] = field(default_factory=list)
    classes: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if (class_str := self.attributes.get("class")) is not None:
            logger.warning("class set as an attribute!", stack_info=True, stacklevel=3)
            for classname in class_str.split():
                self.classes.add(classname)
            del self.attributes["class"]

    @property
    def must_be_inline(self) -> bool:
        return False

    @property
    def void(self) -> bool:
        return self.type in VOID_ELEMENTS

    def containing(self, *items: Contents) -> Element:
        self.children.extend(HtmlStr(i) if isinstance(i, str) else i for i in items)
        return self

    def with_attribute(self, **attributes: str | None) -> Element:
        self.attributes.update(attributes)
        return self

    def with_class(self, *classnames: str) -> Element:
        self.classes.update(classnames)
        return self

    def with_data(self, data: dict[str, str]) -> Element:
        for key in data:
            if not DATA_KEY_PATTERN.fullmatch(key):
                raise ValueError(
                    f"data key {key!r} doesn't match /{DATA_KEY_PATTERN.pattern}/"
                )
        self.attributes.update((f"data-{key}", value) for key, value in data.items())
        return self

    def render(self, indent: str, inline: bool) -> str:
        inline = self.must_be_inline or any(c.must_be_inline for c in self.children)
        if self.void:
            contents = None
        elif inline:
            contents = "".join(c.render(indent="", inline=True) for c in self.children)
        else:
            contents = "\n".join(
                c.render(indent=indent + "  ", inline=False) for c in self.children
            )
        return render_tag(
            type=self.type,
            attrs=self.attributes,
            classes=self.classes,
            contents=contents,
            indent=indent,
            inline=inline,
        )


@dataclass(frozen=True)
class HtmlSequence(HtmlRenderable):
    children: list[Element]

    def render(self, indent: str, inline: bool) -> str:
        if inline:
            return "".join(c.render(indent="", inline=True) for c in self.children)
        else:
            return "\n".join(
                c.render(indent=indent, inline=False) for c in self.children
            )

    @property
    def must_be_inline(self) -> bool:
        return any(c.must_be_inline for c in self.children)


@dataclass(frozen=True)
class HtmlStr(HtmlRenderable):
    s: str

    @classmethod
    def escape(cls, s: str) -> HtmlStr:
        return HtmlStr(html.escape(s))

    @property
    def must_be_inline(self) -> bool:
        return True

    def render(self, indent: str, inline: bool) -> str:
        return indent + self.s


TElementFunc = TypeVar("TElementFunc", bound=Callable[..., Element])


class Registry:
    def __init__(self) -> None:
        self.styles: dict[str, str] = {}

    def render_stylesheet(self) -> str:
        return "\n".join(
            f".{name} {{\n{textwrap.indent(style, '  ')}\n}}"
            for name, style in self.styles.items()
        )

    def style(self, css: str | None = None) -> Callable[[TElementFunc], TElementFunc]:
        """
        Add a class and some styling to the returned HtmlElement.

        In the CSS, all '&' are replaced with the class selector. If classname is
        not specified, it defaults to the name of the decorated function.
        """

        def decorator(func: TElementFunc) -> TElementFunc:
            classname = func.__name__.replace("_", "-").removesuffix("-")
            if classname in self.styles:
                logger.warning(
                    "Duplicate CSS classname %r generated by @style()", classname
                )
            if css is not None:
                self.styles[classname] = textwrap.dedent(css).strip()

            @wraps(func)
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                result.with_class(classname)
                return result

            return cast(TElementFunc, wrapper)

        return decorator


Attributes = Mapping[str, str | bool | None]
Contents = HtmlRenderable | str


def render_tag(
    type: str,
    attrs: Attributes,
    classes: Iterable[str],
    contents: str | None,
    indent: str,
    inline: bool,
) -> str:
    if type not in ALL_ELEMENTS:
        logger.warning("render_tag() called with unknown tag type %r", type)
    if type in NO_INDENT_ELEMENTS:
        indent = ""
        inline = True
    rendered_attrs = render_attributes(attrs, classes)
    if contents is None:
        return f"{indent}<{type}{rendered_attrs}/>"
    open_tag = f"<{type}{rendered_attrs}>"
    close_tag = f"</{type}>"
    if inline:
        return f"{indent}{open_tag}{contents}{close_tag}"
    else:
        return f"{indent}{open_tag}\n{contents}\n{indent}{close_tag}"


def render_attributes(attrs: Attributes = {}, classes: Iterable[str] = []) -> str:
    rendered_attrs = []
    if classes:
        class_value = " ".join(html.escape(c) for c in classes)
        rendered_attrs.append(f'class="{class_value}"')
    for name, value in attrs.items():
        if value is False or value is None:
            pass
        elif value is True:
            rendered_attrs.append(name)
        else:
            rendered_attrs.append(f'{name}="{html.escape(value)}"')
    return "".join(f" {r}" for r in rendered_attrs)


NO_INDENT_ELEMENTS = {
    "pre",
}

VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}

ALL_ELEMENTS = {
    "article",
    "section",
    "nav",
    "aside",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hgroup",
    "header",
    "footer",
    "address",
    "p",
    "hr",
    "pre",
    "blockquote",
    "ol",
    "ul",
    "menu",
    "li",
    "dl",
    "dt",
    "dd",
    "figure",
    "figcaption",
    "main",
    "div",
    "a",
    "em",
    "strong",
    "small",
    "s",
    "cite",
    "q",
    "dfn",
    "abbr",
    "ruby",
    "rt",
    "rp",
    "data",
    "time",
    "code",
    "var",
    "samp",
    "kbd",
    "sub",
    "sup",
    "i",
    "b",
    "u",
    "mark",
    "bdi",
    "bdo",
    "span",
    "br",
    "wbr",
    "ins",
    "del",
    "picture",
    "source",
    "img",
    "iframe",
    "embed",
    "object",
    "video",
    "audio",
    "track",
    "map",
    "area",
    "table",
    "caption",
    "colgroup",
    "col",
    "tbody",
    "thead",
    "tfoot",
    "tr",
    "td",
    "th",
    "form",
    "label",
    "input",
    "button",
    "select",
    "datalist",
    "optgroup",
    "option",
    "textarea",
    "output",
    "progress",
    "meter",
    "fieldset",
    "legend",
    "details",
    "summary",
    "dialog",
    "script",
    "noscript",
    "template",
    "slot",
    "canvas",
}


class Tests(unittest.TestCase):
    def test_render_attributes(self) -> None:
        result = render_attributes(
            {"disabled": True, "href": 'https://www.example.com/?s=test"test'},
            classes=["a-b", "c"],
        )
        self.assertEqual(
            result,
            ' class="a-b c" disabled href="https://www.example.com/?s=test&quot;test"',
        )

    def test_render_tag(self) -> None:
        with self.subTest("regular div"):
            result = render_tag(
                type="div",
                attrs={"foo": "bar"},
                classes=["test"],
                contents="  <a href=test>test</a>",
                indent="",
                inline=False,
            )
            self.assertMultiLineEqual(
                result,
                '<div class="test" foo="bar">\n  <a href=test>test</a>\n</div>',
            )
        with self.subTest("inline div"):
            result = render_tag(
                type="div",
                attrs={"foo": "bar"},
                classes=["test"],
                contents="<a href=test>test</a>",
                indent="",
                inline=True,
            )
            self.assertEqual(
                result,
                '<div class="test" foo="bar"><a href=test>test</a></div>',
            )
        with self.subTest("indented div"):
            result = render_tag(
                type="div",
                attrs={"foo": "bar"},
                classes=["test"],
                contents="    <a href=test>test</a>",
                indent="  ",
                inline=False,
            )
            self.assertMultiLineEqual(
                result,
                '  <div class="test" foo="bar">\n    <a href=test>test</a>\n  </div>',
            )
        with self.subTest("indented pre"):
            result = render_tag(
                type="pre",
                attrs={},
                classes=[],
                contents="  2\n 1\n0",
                indent="  ",
                inline=False,
            )
            self.assertMultiLineEqual(
                result,
                "<pre>  2\n 1\n0</pre>",
            )

    def test_nested_elements(self) -> None:
        result = (
            Element("div")
            .containing(
                Element("p").containing(HtmlStr("foo")),
                Element("p").containing(HtmlStr("bar")),
            )
            .render(indent="", inline=False)
        )
        self.assertMultiLineEqual(result, "<div>\n  <p>foo</p>\n  <p>bar</p>\n</div>")
