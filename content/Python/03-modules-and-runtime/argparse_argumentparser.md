+++

date = '2026-08-18T21:17:41+08:00'
draft = false
title = 'argparse.ArgumentParser 基础教程'

+++

## 1. argparse 是什么

`argparse` 是 Python 标准库里用来解析命令行参数的模块。

所谓“命令行参数”，就是你在终端里运行脚本时，跟在脚本名后面的那些内容。

比如：

```bash
python backup.py src dist --compress --level 9
```

这里：

- `backup.py` 是要运行的 Python 文件。
- `src`、`dist`、`--compress`、`--level 9` 都是传给脚本的参数。

如果不用 `argparse`，你可以从 `sys.argv` 里手动取这些参数：

```python
import sys

print(sys.argv)
```

运行：

```bash
python demo.py hello 123
```

输出类似：

```python
['demo.py', 'hello', '123']
```

这当然能用。只是，如果你要处理参数类型、默认值、帮助信息、必填项、布尔开关、子命令，那么继续手写就不太体面了。准确地说，是很容易写出一团将来会反过来责备你的代码。

`argparse.ArgumentParser` 的作用就是：

- 定义这个命令行工具支持哪些参数。
- 自动解析用户输入。
- 自动生成 `-h` / `--help` 帮助文档。
- 自动处理缺少参数、参数类型错误等常见问题。

它是标准库，不需要安装。

```python
import argparse
```

---

## 2. 最小示例

先看一个最小版本。

新建 `hello.py`：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("name")

args = parser.parse_args()

print(f"Hello, {args.name}!")
```

运行：

```bash
python hello.py Alice
```

输出：

```text
Hello, Alice!
```

这里最重要的是三步：

```python
parser = argparse.ArgumentParser()
parser.add_argument("name")
args = parser.parse_args()
```

含义分别是：

1. 创建一个参数解析器。
2. 告诉解析器：这个程序需要一个名为 `name` 的参数。
3. 解析命令行输入，并把结果放进 `args`。

`args` 通常是一个 `Namespace` 对象。

你可以打印一下：

```python
print(args)
```

运行：

```bash
python hello.py Alice
```

输出类似：

```text
Namespace(name='Alice')
```

所以 `args.name` 就是用户传进来的 `Alice`。

---

## 3. 位置参数

像前面的 `name` 这种不带 `-` 或 `--` 的参数，叫位置参数。

它依赖位置来识别。

例如：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("src")
parser.add_argument("dst")

args = parser.parse_args()

print(f"from: {args.src}")
print(f"to: {args.dst}")
```

运行：

```bash
python copy.py a.txt b.txt
```

输出：

```text
from: a.txt
to: b.txt
```

这里 `a.txt` 会赋给 `src`，`b.txt` 会赋给 `dst`。

如果少传一个参数：

```bash
python copy.py a.txt
```

`argparse` 会自动报错：

```text
usage: copy.py [-h] src dst
copy.py: error: the following arguments are required: dst
```

也就是说，位置参数默认就是必填的。

---

## 4. help：给参数加说明

`help` 用来描述参数的用途。

```python
import argparse


parser = argparse.ArgumentParser(description="复制一个文件到指定位置")
parser.add_argument("src", help="源文件路径")
parser.add_argument("dst", help="目标文件路径")

args = parser.parse_args()

print(f"copy {args.src} -> {args.dst}")
```

运行：

```bash
python copy.py -h
```

输出类似：

```text
usage: copy.py [-h] src dst

复制一个文件到指定位置

positional arguments:
  src         源文件路径
  dst         目标文件路径

options:
  -h, --help  show this help message and exit
```

只要使用了 `ArgumentParser`，`-h` 和 `--help` 默认就会存在。

这点很重要。一个命令行工具如果没有帮助信息，就像一本没有目录的教材。不是不能看，只是没必要这么折磨后来的人。

---

## 5. 可选参数

带 `-` 或 `--` 的参数，通常叫可选参数，也叫 option。

比如：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--name")

args = parser.parse_args()

print(args)
```

运行：

```bash
python hello.py --name Alice
```

输出：

```text
Namespace(name='Alice')
```

如果不传：

```bash
python hello.py
```

输出：

```text
Namespace(name=None)
```

可选参数默认不是必填的。

你也可以同时提供短参数和长参数：

```python
parser.add_argument("-n", "--name")
```

这样下面两种写法都可以：

```bash
python hello.py -n Alice
python hello.py --name Alice
```

通常：

- 短参数适合常用命令，比如 `-v`。
- 长参数适合可读性更高的命令，比如 `--verbose`。

---

## 6. default：默认值

可选参数经常需要默认值。

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("-n", "--name", default="world")

args = parser.parse_args()

print(f"Hello, {args.name}!")
```

运行：

```bash
python hello.py
```

输出：

```text
Hello, world!
```

运行：

```bash
python hello.py --name Alice
```

输出：

```text
Hello, Alice!
```

`default` 的意思是：用户没有提供这个参数时，使用这个值。

---

## 7. type：类型转换

命令行传进来的内容本质上都是字符串。

比如：

```bash
python add.py 1 2
```

这里的 `1` 和 `2` 一开始都是字符串，不是整数。

如果你要做加法，需要用 `type=int` 转换：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("a", type=int)
parser.add_argument("b", type=int)

args = parser.parse_args()

print(args.a + args.b)
```

运行：

```bash
python add.py 1 2
```

输出：

```text
3
```

如果用户输入的不是整数：

```bash
python add.py 1 abc
```

`argparse` 会自动报错：

```text
add.py: error: argument b: invalid int value: 'abc'
```

常见的 `type`：

```python
parser.add_argument("--count", type=int)
parser.add_argument("--price", type=float)
parser.add_argument("--path", type=str)
```

如果不写 `type`，默认就是字符串。

---

## 8. required：让可选参数变成必填

位置参数默认必填，可选参数默认不必填。

如果你想让某个可选参数必填，可以写：

```python
parser.add_argument("--token", required=True)
```

完整示例：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--token", required=True, help="访问 API 时使用的 token")

args = parser.parse_args()

print(f"token = {args.token}")
```

运行：

```bash
python api.py
```

会报错：

```text
api.py: error: the following arguments are required: --token
```

不过要注意：`required=True` 虽然能用，但不要滥用。

如果一个参数从业务含义上就是必须提供的，很多时候写成位置参数更自然：

```bash
python upload.py report.pdf
```

比下面这种更简洁：

```bash
python upload.py --file report.pdf
```

当然，如果参数很多，或者你希望命令更清晰，`--file report.pdf` 也不是错误。只是设计命令行时要考虑使用者，不要把所有东西都塞成必填 option，然后装作自己设计了一个高级接口。

---

## 9. action：布尔开关

命令行里经常有这种参数：

```bash
python app.py --verbose
```

它后面不需要跟值。只要出现，就表示打开某个开关。

这种参数用 `action="store_true"`：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("-v", "--verbose", action="store_true")

args = parser.parse_args()

print(args.verbose)
```

运行：

```bash
python app.py
```

输出：

```text
False
```

运行：

```bash
python app.py --verbose
```

输出：

```text
True
```

`store_true` 的含义是：

- 用户没有传这个参数时，值是 `False`。
- 用户传了这个参数时，值是 `True`。

还有一个相反的 `store_false`：

```python
parser.add_argument("--no-cache", action="store_false", dest="cache")
```

例子：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--no-cache", action="store_false", dest="cache")

args = parser.parse_args()

print(args.cache)
```

运行：

```bash
python app.py
```

输出：

```text
True
```

运行：

```bash
python app.py --no-cache
```

输出：

```text
False
```

这里的 `dest="cache"` 表示：解析后的属性名叫 `cache`，不是 `no_cache`。

---

## 10. choices：限制可选值

如果一个参数只能从几个值里选，可以使用 `choices`。

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--mode", choices=["dev", "test", "prod"], default="dev")

args = parser.parse_args()

print(args.mode)
```

合法：

```bash
python app.py --mode prod
```

不合法：

```bash
python app.py --mode local
```

会报错：

```text
app.py: error: argument --mode: invalid choice: 'local' (choose from 'dev', 'test', 'prod')
```

`choices` 很适合表达“只能从这些值里选一个”的场景。

比如：

```python
parser.add_argument("--format", choices=["json", "yaml", "toml"])
parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"])
```

---

## 11. nargs：接收多个值

默认情况下，一个参数只接收一个值。

如果你想让一个参数接收多个值，可以使用 `nargs`。

### 固定数量

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--point", nargs=2, type=float)

args = parser.parse_args()

print(args.point)
```

运行：

```bash
python draw.py --point 3.5 4.2
```

输出：

```text
[3.5, 4.2]
```

`nargs=2` 表示这个参数后面必须跟两个值。

### 一个或多个

```python
parser.add_argument("files", nargs="+")
```

`+` 表示至少一个。

例子：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("files", nargs="+")

args = parser.parse_args()

for file in args.files:
    print(file)
```

运行：

```bash
python show.py a.txt b.txt c.txt
```

输出：

```text
a.txt
b.txt
c.txt
```

### 零个或多个

```python
parser.add_argument("files", nargs="*")
```

`*` 表示零个或多个。

如果用户没有传，得到空列表：

```text
[]
```

### 零个或一个

```python
parser.add_argument("--output", nargs="?")
```

`?` 表示零个或一个。

这个用得不如 `+` 和 `*` 多。初学时先知道有它即可，不必急着把所有语法都背下来。参数解析不是背诵比赛，虽然很多教程写得像。

---

## 12. append：同一个参数出现多次

有时你希望用户可以多次传同一个参数。

比如：

```bash
python app.py --tag python --tag cli --tag argparse
```

可以使用 `action="append"`：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--tag", action="append", default=[])

args = parser.parse_args()

print(args.tag)
```

输出：

```text
['python', 'cli', 'argparse']
```

这个很适合标签、过滤条件、多个配置项等场景。

---

## 13. dest：指定解析后的属性名

默认情况下，参数名会变成 `args` 里的属性名。

比如：

```python
parser.add_argument("--log-level")
```

解析后访问：

```python
args.log_level
```

注意，`--log-level` 里的 `-` 会被转换成 `_`。

如果你想自己指定属性名，可以用 `dest`：

```python
parser.add_argument("--log-level", dest="level")
```

之后访问：

```python
args.level
```

完整示例：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--log-level", dest="level", default="info")

args = parser.parse_args()

print(args.level)
```

---

## 14. metavar：修改帮助信息里的参数名

`metavar` 用来控制帮助信息里显示的占位名称。

例如：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--output", metavar="FILE", help="输出文件路径")

args = parser.parse_args()
```

运行：

```bash
python app.py -h
```

会看到类似：

```text
--output FILE  输出文件路径
```

如果不写 `metavar`，可能显示成：

```text
--output OUTPUT
```

`metavar` 只影响帮助信息，不影响代码里访问的属性名。

也就是说，仍然是：

```python
args.output
```

---

## 15. description 和 epilog

创建 `ArgumentParser` 时，可以传入：

- `description`：帮助信息开头的说明。
- `epilog`：帮助信息结尾的补充说明。

例子：

```python
import argparse


parser = argparse.ArgumentParser(
    description="一个简单的文件搜索工具",
    epilog="示例：python find_file.py . --name report.txt",
)
parser.add_argument("path", help="要搜索的目录")
parser.add_argument("--name", required=True, help="要搜索的文件名")

args = parser.parse_args()

print(args)
```

运行：

```bash
python find_file.py -h
```

会看到更完整的帮助信息。

如果你的脚本会交给别人使用，`description` 和 `help` 最好认真写。命令行工具的界面就是帮助文档，它没有按钮可以让用户猜。

---

## 16. 一个稍微完整的例子：文件统计工具

下面写一个小工具：统计文本文件的行数、单词数和字符数。

文件名：`word_count.py`

```python
import argparse
from pathlib import Path


def count_file(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    words = text.split()

    return {
        "lines": len(lines),
        "words": len(words),
        "chars": len(text),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="统计文本文件的行数、单词数和字符数")
    parser.add_argument("file", type=Path, help="要统计的文本文件")
    parser.add_argument("-l", "--lines", action="store_true", help="只显示行数")
    parser.add_argument("-w", "--words", action="store_true", help="只显示单词数")
    parser.add_argument("-c", "--chars", action="store_true", help="只显示字符数")

    args = parser.parse_args()

    if not args.file.exists():
        parser.error(f"文件不存在：{args.file}")

    if not args.file.is_file():
        parser.error(f"不是普通文件：{args.file}")

    result = count_file(args.file)

    selected = []
    if args.lines:
        selected.append("lines")
    if args.words:
        selected.append("words")
    if args.chars:
        selected.append("chars")

    if not selected:
        selected = ["lines", "words", "chars"]

    for key in selected:
        print(f"{key}: {result[key]}")


if __name__ == "__main__":
    main()
```

运行：

```bash
python word_count.py article.txt
```

输出：

```text
lines: 10
words: 120
chars: 680
```

只看行数：

```bash
python word_count.py article.txt --lines
```

输出：

```text
lines: 10
```

这个例子里有几个值得注意的点。

第一，`type=Path` 很方便：

```python
parser.add_argument("file", type=Path)
```

这样 `args.file` 会直接是一个 `Path` 对象，而不是普通字符串。

第二，参数校验可以用 `parser.error()`：

```python
parser.error(f"文件不存在：{args.file}")
```

它会用 `argparse` 的风格打印错误并退出程序。

第三，把主要逻辑放进 `main()`：

```python
def main() -> None:
    ...


if __name__ == "__main__":
    main()
```

这是写命令行脚本的常见结构。别把所有逻辑都堆在文件顶层，除非你确实想让以后维护的人怀疑人生。

---

## 17. 自定义类型转换函数

`type` 不一定只能是 `int`、`float`、`str`。

它可以是任何接收一个字符串并返回转换结果的函数。

例如，我们想解析正整数：

```python
import argparse


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return number


parser = argparse.ArgumentParser()
parser.add_argument("--limit", type=positive_int, default=10)

args = parser.parse_args()

print(args.limit)
```

运行：

```bash
python app.py --limit 5
```

输出：

```text
5
```

运行：

```bash
python app.py --limit -1
```

报错：

```text
app.py: error: argument --limit: 必须是正整数
```

如果自定义转换失败，推荐抛出 `argparse.ArgumentTypeError`。

也可以处理 `ValueError`：

```python
def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是整数") from exc

    if number <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return number
```

这样错误信息会更友好。

---

## 18. parse_args() 和 parse_known_args()

最常用的是：

```python
args = parser.parse_args()
```

它要求所有参数都必须是当前 parser 认识的。

如果用户传了未知参数：

```bash
python app.py --unknown
```

会报错。

有时你希望只解析自己认识的参数，把不认识的留下来，可以使用：

```python
args, unknown = parser.parse_known_args()
```

示例：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true")

args, unknown = parser.parse_known_args()

print(args)
print(unknown)
```

运行：

```bash
python app.py --debug --other 123
```

输出：

```text
Namespace(debug=True)
['--other', '123']
```

`parse_known_args()` 常用于包装其他命令行工具、插件系统、测试框架等场景。

初学时先用 `parse_args()`。只有确实需要保留未知参数时，再用 `parse_known_args()`。

---

## 19. 子命令：subparsers

有些命令行工具有多个子命令。

比如：

```bash
git add .
git commit -m "message"
git status
```

这里 `add`、`commit`、`status` 就是子命令。

`argparse` 可以用 `add_subparsers()` 实现类似结构。

示例：`todo.py`

```python
import argparse


def handle_add(args: argparse.Namespace) -> None:
    print(f"add todo: {args.text}")


def handle_list(args: argparse.Namespace) -> None:
    print(f"list todos, done={args.done}")


def main() -> None:
    parser = argparse.ArgumentParser(description="一个简单的 todo 命令")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="添加一条 todo")
    add_parser.add_argument("text", help="todo 内容")
    add_parser.set_defaults(func=handle_add)

    list_parser = subparsers.add_parser("list", help="列出 todo")
    list_parser.add_argument("--done", action="store_true", help="只显示已完成 todo")
    list_parser.set_defaults(func=handle_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

运行：

```bash
python todo.py add "learn argparse"
```

输出：

```text
add todo: learn argparse
```

运行：

```bash
python todo.py list --done
```

输出：

```text
list todos, done=True
```

关键代码是：

```python
subparsers = parser.add_subparsers(dest="command", required=True)
```

然后给每个子命令单独创建 parser：

```python
add_parser = subparsers.add_parser("add", help="添加一条 todo")
list_parser = subparsers.add_parser("list", help="列出 todo")
```

`set_defaults(func=...)` 是一个常见写法：

```python
add_parser.set_defaults(func=handle_add)
```

解析完成后：

```python
args.func(args)
```

就会调用对应子命令的处理函数。

这个结构很适合稍微复杂一点的命令行程序。比起写一堆 `if args.command == "..."`，它更清晰，也更容易扩展。

---

## 20. BooleanOptionalAction：自动生成 --foo 和 --no-foo

从 Python 3.9 开始，`argparse` 提供了 `BooleanOptionalAction`。

它可以自动生成一对布尔参数：

```python
import argparse


parser = argparse.ArgumentParser()
parser.add_argument("--cache", action=argparse.BooleanOptionalAction, default=True)

args = parser.parse_args()

print(args.cache)
```

运行：

```bash
python app.py --cache
```

输出：

```text
True
```

运行：

```bash
python app.py --no-cache
```

输出：

```text
False
```

如果你使用的是 Python 3.9 或更高版本，这个写法比手动写 `--no-cache` 更自然。

---

## 21. 常用参数汇总

`ArgumentParser()` 常用参数：

```python
parser = argparse.ArgumentParser(
    prog="mytool",
    description="工具说明",
    epilog="额外说明",
)
```

含义：

- `prog`：帮助信息里显示的程序名。
- `description`：帮助信息开头的说明。
- `epilog`：帮助信息结尾的说明。

`add_argument()` 常用参数：

```python
parser.add_argument(
    "-o",
    "--output",
    type=str,
    default="result.txt",
    required=False,
    choices=None,
    nargs=None,
    action=None,
    dest=None,
    metavar="FILE",
    help="输出文件路径",
)
```

含义：

- `name or flags`：参数名，比如 `"file"`、`"-o"`、`"--output"`。
- `type`：类型转换函数，比如 `int`、`float`、`Path`。
- `default`：默认值。
- `required`：是否必填，主要用于可选参数。
- `choices`：限制可选值。
- `nargs`：接收几个值。
- `action`：参数触发时执行什么动作，比如 `store_true`、`append`。
- `dest`：解析后保存到 `args` 里的属性名。
- `metavar`：帮助信息里显示的占位名。
- `help`：帮助说明。

---

## 22. 常见错误

### 错误一：忘记命令行传入的都是字符串

错误写法：

```python
parser.add_argument("count")

args = parser.parse_args()
print(args.count + 1)
```

如果运行：

```bash
python app.py 3
```

会报错，因为 `args.count` 是字符串 `"3"`。

正确写法：

```python
parser.add_argument("count", type=int)
```

### 错误二：布尔参数使用 type=bool

这是初学者很容易踩的坑。

错误写法：

```python
parser.add_argument("--debug", type=bool)
```

你可能以为：

```bash
python app.py --debug False
```

会得到 `False`。

但实际上：

```python
bool("False")
```

结果是：

```python
True
```

因为非空字符串转换成布尔值都是 `True`。

正确写法通常是：

```python
parser.add_argument("--debug", action="store_true")
```

或者 Python 3.9+：

```python
parser.add_argument("--debug", action=argparse.BooleanOptionalAction)
```

### 错误三：把业务逻辑写在参数定义中

参数定义应该描述命令行接口，而不是塞满业务逻辑。

比较好的结构是：

```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # 这里写主要业务逻辑


if __name__ == "__main__":
    main()
```

这样以后写测试、扩展参数、拆分功能都会轻松一些。

### 错误四：参数名和变量名不一致

比如：

```python
parser.add_argument("--output-file")

args = parser.parse_args()
print(args.output-file)
```

这当然不行。

`--output-file` 会变成：

```python
args.output_file
```

因为 Python 属性名不能包含 `-`。

---

## 23. 推荐写法模板

一个比较舒服的基础模板如下：

```python
import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="这里写脚本说明")

    parser.add_argument("input", type=Path, help="输入文件路径")
    parser.add_argument("-o", "--output", type=Path, default=Path("out.txt"), help="输出文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细日志")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.verbose:
        print(f"input: {args.input}")
        print(f"output: {args.output}")

    # 在这里写真正的业务逻辑


if __name__ == "__main__":
    main()
```

这个模板的优点：

- 参数解析集中在 `parse_args()`。
- 主逻辑从 `main()` 开始。
- 程序入口使用 `if __name__ == "__main__"`。
- 文件路径用 `Path`，比到处传字符串更好维护。

---

## 24. 一个练习

写一个 `rename.py`，实现下面的命令：

```bash
python rename.py old.txt new.txt --dry-run
```

要求：

- `old.txt` 是原文件路径，位置参数。
- `new.txt` 是新文件路径，位置参数。
- `--dry-run` 是布尔开关，传了以后只打印要做什么，不真正重命名。
- 如果原文件不存在，用 `parser.error()` 报错。
- 使用 `pathlib.Path`。

参考答案：

```python
import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="重命名文件")
    parser.add_argument("old", type=Path, help="原文件路径")
    parser.add_argument("new", type=Path, help="新文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只显示操作，不真正执行")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.old.exists():
        parser.error(f"文件不存在：{args.old}")

    if args.dry_run:
        print(f"将重命名：{args.old} -> {args.new}")
        return

    args.old.rename(args.new)
    print(f"已重命名：{args.old} -> {args.new}")


if __name__ == "__main__":
    main()
```

这里把创建 parser 的逻辑放到 `build_parser()`，是为了在 `main()` 里还能调用 `parser.error()`。这样错误输出会保持 `argparse` 的统一格式。

---

## 25. 小结

使用 `argparse.ArgumentParser` 的基本流程是：

```python
import argparse

parser = argparse.ArgumentParser(description="程序说明")
parser.add_argument("name", help="位置参数")
parser.add_argument("-v", "--verbose", action="store_true", help="布尔开关")

args = parser.parse_args()
```

你需要记住的核心点：

- `ArgumentParser()` 创建解析器。
- `add_argument()` 定义参数。
- `parse_args()` 解析命令行输入。
- 不带 `-` 的是位置参数，默认必填。
- 带 `-` 或 `--` 的是可选参数，默认可省略。
- 命令行输入默认都是字符串，需要时用 `type` 转换。
- 布尔开关不要写 `type=bool`，优先用 `action="store_true"`。
- 参数名里的 `-` 会在 `args` 属性里变成 `_`。
- 写给别人用的脚本一定要认真写 `help`。

掌握这些，日常写脚本已经够用了。剩下的高级功能，比如互斥参数组、从文件读取参数、自定义 formatter，可以等你真的需要时再学。工具应该为问题服务，而不是反过来让你为了炫耀工具而制造问题。
