# SPDX-License-Identifier: GPL-3.0-or-later
import json
import re
import subprocess
import urllib.parse as urlparse
import pynvim

DDG = "https://lite.duckduckgo.com/lite/"
LINK_LINE = re.compile(r"^\[(\d+)\] ")
MAX_BYTES = 4 * 1024 * 1024
STATE = "viww_state"
UA = "Mozilla/5.0 (compatible; viww/0.1)"
NESTED = {"Emph", "Strong", "Strikeout", "Superscript", "Subscript", "SmallCaps"}
WRAPPED = {"Span", "Link", "Image", "Quoted", "Cite"}

class ViwwError(RuntimeError):
    pass
def run(args, data=b"", timeout=20):
    data = data.encode() if isinstance(data, str) else data
    try:
        proc = subprocess.run(
            args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, check=False,
        )
    except FileNotFoundError as exc:
        raise ViwwError(f"{args[0]} is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ViwwError(f"{args[0]} timed out") from exc
    if proc.returncode:
        msg = proc.stderr.decode("utf-8", "replace").strip()
        raise ViwwError(msg or f"{args[0]} exited with {proc.returncode}")
    return proc.stdout

def fetch(url):
    mark = b"\n--viww-final-url--\n"
    args = "curl -LfsS --compressed --connect-timeout 10 --max-time 30 --max-filesize".split()
    args += [
        str(MAX_BYTES), "-A", UA, "-H",
        "Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        "-w", mark.decode() + "%{url_effective}", url,
    ]
    out = run(args, timeout=35)
    if mark not in out:
        raise ViwwError("curl did not return the final URL")
    body, final = out.rsplit(mark, 1)
    return final.decode("utf-8", "replace").strip() or url, body

def document(html):
    try:
        return json.loads(run(["pandoc", "-f", "html", "-t", "json"], html).decode())
    except json.JSONDecodeError as exc:
        raise ViwwError(f"pandoc returned invalid JSON: {exc}") from exc

def render(url, html):
    doc = document(html)
    plain = run(["pandoc", "-f", "json", "-t", "plain", "--wrap=none"], json.dumps(doc, ensure_ascii=False))
    links = page_links(doc, url)
    footer = ["", "Links:", *[f"[{n}] {clip(text)} -> {href}" for n, href, text in links]] if links else []
    return [f"Viww: {url}", f"URL: {url}", "", *plain_lines(plain.decode("utf-8", "replace")), *footer], links

def plain_lines(text):
    lines = []
    for line in (line.rstrip() for line in text.splitlines()):
        if line.strip() or (lines and lines[-1]):
            lines.append(line if line.strip() else "")
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines or ["(empty page)"]

def page_links(doc, base):
    links = []
    for node in walk(doc.get("blocks", [])):
        if isinstance(node, dict) and node.get("t") == "Link":
            data = node.get("c", [])
            if len(data) == 3 and data[2]:
                href = absolute(data[2][0], base)
                links.append([len(links) + 1, href, words(data[1]) or href])
    return links

def walk(value):
    if isinstance(value, dict):
        yield value
        yield from walk(value.get("c"))
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)

def words(nodes):
    text = []
    for node in nodes or []:
        tag, data = (node.get("t"), node.get("c")) if isinstance(node, dict) else (None, None)
        if tag == "Str":
            text.append(data)
        elif tag in {"Space", "SoftBreak", "LineBreak"}:
            text.append(" ")
        elif tag in {"Code", "Math"}:
            text.append(data[-1])
        elif tag in NESTED:
            text.append(words(data))
        elif tag in WRAPPED:
            text.append(words(data[1]))
    return re.sub(r"\s+", " ", "".join(text)).strip()

def absolute(href, base):
    href = urlparse.urljoin(base, href)
    parsed = urlparse.urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        values = urlparse.parse_qs(parsed.query).get("uddg")
        if values:
            return urlparse.unquote(values[0])
    return href

def clip(text, size=90):
    return text if len(text) <= size else text[: size - 1].rstrip() + "..."

def target(text):
    parsed = urlparse.urlparse(text)
    if parsed.scheme in {"http", "https"}:
        return text
    if parsed.netloc:
        return "https:" + text
    return "https://" + text if "." in text and " " not in text else DDG + "?" + urlparse.urlencode({"q": text})

@pynvim.plugin
class Viww:
    def __init__(self, nvim):
        self.nvim = nvim
    @pynvim.command("Viww", nargs="*")
    def viww(self, args):
        query = " ".join(args).strip()
        self.go(target(query)) if query else self.err("usage: :Viww search terms or URL")
    @pynvim.command("ViwwFollow", nargs="?")
    def follow(self, args):
        state = self.state()
        if not state:
            return self.err("ViwwFollow only works in a Viww buffer")
        index = self.link_index(args[0] if args else self.cursor_link())
        if index is None:
            return
        for _n, href, _text in state.get("links", []):
            if int(_n) == index:
                if urlparse.urlparse(href).scheme not in {"http", "https"}:
                    return self.err(f"unsupported URL: {href}")
                return self.go(href, [*state.get("history", []), state["url"]])
        self.err(f"no link {index}")
    @pynvim.command("ViwwBack", nargs="0")
    def back(self, _args):
        state = self.state()
        self.go(state["history"][-1], state["history"][:-1]) if state and state.get("history") else self.err("no Viww history")
    @pynvim.command("ViwwReload", nargs="0")
    def reload(self, _args):
        state = self.state()
        self.go(state["url"], state.get("history", [])) if state else self.err("not a Viww buffer")
    def go(self, url, history=()):
        self.prepare()
        try:
            final, html = fetch(url)
            lines, links = render(final, html)
            state = {"url": final, "history": list(history), "links": links}
        except (OSError, UnicodeError, ViwwError, subprocess.SubprocessError) as exc:
            lines = ["Viww: error", f"URL: {url}", "", str(exc)]
            state = {"url": url, "history": list(history), "links": []}
        self.write(lines, state)
    def prepare(self):
        if not self.state():
            self.nvim.command("silent keepalt hide enew")
        for cmd in (
            "setlocal buftype=nofile bufhidden=hide noswapfile filetype=viww wrap linebreak",
            "nnoremap <silent> <buffer> <CR> :ViwwFollow<CR>",
            "nnoremap <silent> <buffer> H :ViwwBack<CR>",
            "nnoremap <silent> <buffer> R :ViwwReload<CR>",
        ):
            self.nvim.command(cmd)
    def write(self, lines, state):
        self.nvim.command("setlocal noreadonly modifiable")
        self.nvim.current.buffer[:] = lines
        self.nvim.current.buffer.vars[STATE] = state
        self.nvim.command("setlocal nomodified nomodifiable readonly")
        self.nvim.current.window.cursor = (1, 0)
    def state(self):
        try:
            return self.nvim.current.buffer.vars[STATE]
        except KeyError:
            return None
    def cursor_link(self):
        row, _col = self.nvim.current.window.cursor
        match = LINK_LINE.match(self.nvim.current.buffer[row - 1])
        return match.group(1) if match else None
    def link_index(self, raw):
        if not raw:
            return self.err("no link under cursor")
        try:
            return int(raw)
        except ValueError:
            return self.err(f"invalid link: {raw}")
    def err(self, message):
        self.nvim.err_write(message + "\n")
