from __future__ import annotations

import html
import logging
import re
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from functools import wraps
from itertools import chain
from typing import Callable, Iterator, Self, TypeAlias, TypeVar, cast

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


F = TypeVar("F", bound=Callable[..., HtmlRenderable])


class ComponentRegistry:
    def __init__(self) -> None:
        self.styles: dict[str, str] = {}
        self.components: dict[str, Component] = {}

    def stylesheet(self) -> str:
        return "\n".join(
            style.replace("&", f".{name}") for name, style in self.styles.items()
        )

    def style(self, css: str | None = None) -> Callable[[F], F]:
        """
        Add a class and some styling to the returned HtmlElement.

        In the CSS, all '&' are replaced with the class selector. If classname is
        not specified, it defaults to the name of the decorated function.
        """

        def decorator(func: F) -> F:
            classname = func.__name__.replace("_", "-").removesuffix("-")
            if classname in self.styles:
                logger.warning(
                    "Duplicate CSS classname %r generated by @style()", classname
                )
            if css is not None:
                self.styles[classname] = css

            @wraps(func)
            def wrapper(*args, **kwargs):  # type: ignore
                result = func(*args, **kwargs)
                result.with_class(classname)
                return result

            return cast(F, wrapper)

        return decorator

    def component(self, func: Component) -> Component:
        classname = func.__name__.replace("_", "-").removesuffix("-")
        self.components[classname] = func
        return func


def render_tag(name: str, content: str, attrs: dict[str, str | None] = {}) -> str:
    if name not in ALL_ELEMENTS:
        logger.warning("tag() called with unknown element name %r", name)
    return f"<{name}{render_attrs(attrs)}>{content}</{name}>"


def render_attrs(attrs: dict[str, str | None] = {}) -> str:
    return "".join(
        f' {key}="{html.escape(value, quote=True)}"'
        for key, value in attrs.items()
        if value is not None
    )


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

    def containing(self, *items: HtmlRenderable) -> Element:
        self.children.extend(items)
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
        if self.type in NO_INDENT_ELEMENTS:
            indent = ""
        attributes = "".join(f" {a}" for a in self.render_attributes())
        if self.void:
            return f"{indent}<{self.type}{attributes}/>"

        open_tag = f"<{self.type}{attributes}>"
        close_tag = f"</{self.type}>"
        if inline or any(c.must_be_inline for c in self.children):
            contents = "".join(c.render(indent="", inline=True) for c in self.children)
            return f"{indent}{open_tag}{contents}{close_tag}"
        else:
            contents = "\n".join(
                c.render(indent=indent + "  ", inline=False) for c in self.children
            )
            return f"{indent}{open_tag}\n{contents}\n{indent}{close_tag}"

    def render_attributes(self) -> Iterator[str]:
        if self.classes:
            yield f'class="{html.escape(" ".join(sorted(self.classes)))}"'
        for name, value in self.attributes.items():
            if value is None:
                yield name
            else:
                yield f'{name}="{html.escape(value)}"'


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
