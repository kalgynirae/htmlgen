# htmlgen

A simple library for generating HTML from code.

## Demo

https://github.com/kalgynirae/htmlgen/blob/main/demo.py

### Output

This outputs the following HTML:
```html
<h1 class="page-title">Demo Page</h1>
<div class="demo-box">
  <h2>Demo Box</h2>
  <p>These are the things:</p>
  <ol start="2" type="a">
    <li>Minute</li>
    <li>Second</li>
    <li>Third</li>
  </ol>
</div>
```

And the following CSS:
```css
.page-title {
  font-size: 1em;
  font-weight: 700;
}
.demo-box {
  background-color: lightred;
  & > h2 {
    font-size: 1.5em;
    font-weight: 300;
  }
}
```
